from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone
from decimal import Decimal, localcontext, InvalidOperation
from hashlib import sha256
import json
from time import time

from app.application.ports.candle_series_repository import CandleSeriesRepository
from app.domain.value_objects.market_pair import MarketPair
from app.domain.value_objects.series_interval import MINUTE_MS, SeriesInterval


MAX_SOURCE_MINUTES = 44640  # One maximum calendar month per response.
BOUNDARY_VERSION = "binance-utc-v1"


class CandleSeriesService:
    def __init__(self, repository: CandleSeriesRepository, clock=time):
        self.repository = repository
        self.clock = clock

    def coverage(self, market_pair: str):
        pair = MarketPair.parse(market_pair)
        return {"provider": "binance", "market_type": "spot", "market_pair": pair.display,
            "source_interval": "1m", **self.repository.bounds(pair.exchange_symbol_for("binance")),
            **self.repository.context(pair.exchange_symbol_for("binance")),
            "completeness": "not_evaluated", "boundary_version": BOUNDARY_VERSION}

    def query(self, *, market_pair="BTC/USDT", interval="1m", start_ms=None, end_ms=None,
              limit=1000, cursor=None, complete_only=True, include_open=False):
        pair = MarketPair.parse(market_pair)
        symbol = pair.exchange_symbol_for("binance")
        period = SeriesInterval(interval)
        if not 1 <= limit <= 1000 or any(v is not None and (v < 0 or v > 253402214400000) for v in (start_ms, end_ms)):
            raise ValueError("Invalid series bounds or limit")
        if start_ms is not None and end_ms is not None and end_ms <= start_ms:
            raise ValueError("end_ms must be greater than start_ms (exclusive)")
        now_ms = int(self.clock() * 1000)
        context = self.repository.context(symbol)
        first_available = (context["collection"] or {}).get("first_open_time_ms")
        fingerprint = sha256(json.dumps([symbol, interval, start_ms, end_ms, limit, complete_only, include_open]).encode()).hexdigest()
        if cursor:
            try:
                state = json.loads(urlsafe_b64decode(cursor.encode()))
                if state["query"] != fingerprint or any(type(state[k]) is not int for k in ("next", "end", "as_of")):
                    raise ValueError()
                opening, requested_end, as_of = state["next"], state["end"], state["as_of"]
                if not 0 <= opening < requested_end <= 253402214400000 or not 0 <= as_of <= now_ms or period.floor(opening) != opening:
                    raise ValueError()
            except (ValueError, KeyError, TypeError, OverflowError) as exc:
                raise ValueError("Invalid cursor or cursor does not match this query") from exc
        else:
            as_of = now_ms
            last_allowed_end = period.shift(period.floor(as_of)) if include_open else period.floor(as_of)
            if end_ms is None:
                last = self.repository.bounds(symbol)["last_open_time_ms"]
                requested_end = min(last_allowed_end, period.shift(period.floor(last))) if last is not None else last_allowed_end
            else:
                requested_end = min(end_ms, last_allowed_end)
            opening = period.floor(start_ms) if start_ms is not None else period.floor(max(0, requested_end - 1))
            if start_ms is None:
                for _ in range(limit - 1):
                    previous = period.shift(opening, -1)
                    if previous < 0 or period.shift(period.floor(max(0, requested_end - 1))) - previous > MAX_SOURCE_MINUTES * MINUTE_MS:
                        break
                    opening = previous
            if start_ms is not None and opening < start_ms:
                opening = period.shift(opening)
            opening = max(0, opening)
        page_end, bucket_starts = opening, []
        while page_end < requested_end and len(bucket_starts) < limit:
            following = period.shift(page_end)
            if following - opening > MAX_SOURCE_MINUTES * MINUTE_MS:
                break
            bucket_starts.append(page_end)
            page_end = following
        if not bucket_starts:
            return self._response(pair.display, interval, [], None, as_of, 0, opening, opening, 0, 0, [])
        revision, source = self.repository.snapshot(symbol=symbol, start_ms=opening, end_ms=page_end)
        # Every query fixes its as-of time. Never use an unfinished source minute.
        minute_end = max(0, (as_of - 2000) // MINUTE_MS * MINUTE_MS)
        valid = [r for r in source if r["open_time_ms"] % MINUTE_MS == 0
            and r["close_time_ms"] == r["open_time_ms"] + MINUTE_MS - 1 and r["open_time_ms"] < minute_end]
        cached = self.repository.cached(symbol=symbol, interval=interval, revision=revision, start_ms=opening, end_ms=page_end)
        groups = {}
        for row in valid:
            groups.setdefault(period.floor(row["open_time_ms"]), []).append(row)
        items, to_cache = [], []
        for bucket in bucket_starts:
            rows = groups.get(bucket, [])
            if not rows:
                continue
            closing = period.shift(bucket)
            # Cache only fully elapsed buckets; closed is independent of complete.
            item = cached.get(bucket) if closing <= minute_end else None
            if item is None:
                item = aggregate(rows, bucket=bucket, end=closing, as_of=as_of)
                if closing <= minute_end:
                    to_cache.append(item)
            # Availability metadata can change independently of candle revisions.
            # Do not bake these contextual reasons into the aggregate cache.
            if not item["complete"]:
                reason = "awaiting_close" if closing > minute_end else "partial_first_bucket" if first_available is not None and bucket < first_available < closing else "missing_source_minutes"
                item = {**item, "quality_reason": reason}
            if not complete_only or item["complete"]:
                items.append(item)
        self.repository.cache(symbol=symbol, interval=interval, revision=revision, items=to_cache)
        next_cursor = None
        if page_end < requested_end:
            next_cursor = urlsafe_b64encode(json.dumps({"query": fingerprint, "next": page_end,
                "end": requested_end, "as_of": as_of}, separators=(",", ":")).encode()).decode()
        # Same bounded source window powers chart, API quality and gap repair.
        from app.application.services.candle_continuity import missing_open_ranges
        quality_end = min(page_end, minute_end)
        quality_start = max(opening, first_available) if first_available is not None else opening
        gaps = [{"start_ms": a, "end_ms": b + MINUTE_MS, "missing_minutes": (b - a) // MINUTE_MS + 1}
            for a, b in missing_open_ranges((r["open_time_ms"] for r in valid), start=quality_start, end=quality_end - MINUTE_MS, step=MINUTE_MS)] if quality_end > quality_start else []
        expected = max(0, (quality_end - quality_start) // MINUTE_MS)
        return self._response(pair.display, interval, items, next_cursor, as_of, revision,
            opening, page_end, len(valid), expected, gaps)

    @staticmethod
    def _response(pair, interval, items, cursor, as_of, revision, start, end, observed, expected, gaps):
        return {"provider": "binance", "market_type": "spot", "market_pair": pair, "interval": interval,
            "origin": "minute_derived", "source_interval": "1m", "boundary_version": BOUNDARY_VERSION,
            "candles": items, "next_cursor": cursor, "as_of_ms": as_of, "source_revision": revision,
            "window_start_ms": start, "window_end_ms": end, "count": len(items),
            "quality": {"observed_minutes": observed, "expected_closed_minutes": expected,
                "missing_minutes": max(0, expected - observed), "gaps": gaps}}


def aggregate(rows, *, bucket, end, as_of):
    columns = ("open_price", "high_price", "low_price", "close_price", "base_volume", "quote_volume",
        "taker_buy_base_volume", "taker_buy_quote_volume")
    try:
        with localcontext() as context:
            # Decimal addition gets enough precision for all source digits plus carry.
            context.prec = max(80, max(len(r[c]) for r in rows for c in columns) + len(str(len(rows))) + 5)
            numbers = [{c: Decimal(r[c]) for c in columns} for r in rows]
            if any(not value.is_finite() or value < 0 for r in numbers for value in r.values()):
                raise ValueError("Invalid source minute numeric value")
            result = {"open_price": rows[0]["open_price"], "close_price": rows[-1]["close_price"],
                "high_price": format(max(r["high_price"] for r in numbers), "f"),
                "low_price": format(min(r["low_price"] for r in numbers), "f")}
            for c in columns[4:]:
                result[c] = format(sum((r[c] for r in numbers), Decimal(0)), "f")
    except InvalidOperation as exc:
        raise ValueError("Invalid source minute numeric value") from exc
    expected = (end - bucket) // MINUTE_MS
    complete = len(rows) == expected
    closed = end <= as_of
    return {**result, "open_time_ms": bucket, "close_time_ms": end - 1,
        "open_time": datetime.fromtimestamp(bucket / 1000, timezone.utc).isoformat(),
        "close_time": datetime.fromtimestamp((end - 1) / 1000, timezone.utc).isoformat(),
        "trade_count": sum(r["trade_count"] for r in rows), "observed_minutes": len(rows),
        "expected_minutes": expected, "complete": complete, "closed": closed,
        "quality_reason": None if complete else "missing_source_minutes"}
