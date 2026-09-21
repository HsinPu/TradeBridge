"""Verified, bounded official 1m archives, scoped to one historical job.

Only missing archives (404) fall back to smaller archives or REST. Corrupt or
unreachable archives fail the durable job and retain its committed checkpoint.
"""
from bisect import bisect_left, bisect_right
import csv
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, TextIOWrapper
import json
import re
from time import time
from zipfile import ZipFile

import httpx

from app.application.services.execution_control import check_execution, interruptible_wait
from app.domain.value_objects.market_pair import MarketPair
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle


ARCHIVE_ORIGIN = "https://data.binance.vision"
MAX_ZIP_BYTES = 32 * 1024 ** 2
MAX_CSV_BYTES = 128 * 1024 ** 2


class BinanceArchiveClient:
    def __init__(self, rest, *, transport=None, clock=time, limiter=None):
        self.rest = rest
        self.transport = transport
        self.clock = clock
        self.limiter = limiter
        self._cache_key = None
        self._candles = []
        self._times = []
        self._missing = set()

    def __getattr__(self, name):
        return getattr(self.rest, name)

    def fetch_klines(self, query):
        if query.interval != "1m" or query.market_type != "spot":
            return self.rest.fetch_klines(query)
        pair = MarketPair.parse(query.market_pair)
        symbol = pair.exchange_symbol_for("binance")
        # Catalog assets can include Unicode; allow it, but never path separators.
        if not symbol or any(c in symbol for c in "/\\.?#%"):
            raise ValueError("Invalid archive symbol")
        date = datetime.fromtimestamp(query.start_time_ms / 1000, timezone.utc)
        now = datetime.fromtimestamp(self.clock(), timezone.utc)
        choices = []
        if (date.year, date.month) < (now.year, now.month):
            choices.append(("monthly", date.strftime("%Y-%m")))
        if date.date() < now.date():
            choices.append(("daily", date.strftime("%Y-%m-%d")))
        for kind, stamp in choices:
            filename = f"{symbol}-1m-{stamp}.zip"
            path = f"/data/spot/{kind}/klines/{symbol}/1m/{filename}"
            if path in self._missing:
                continue
            if self._cache_key != path:
                checksum = self._download(path + ".CHECKSUM", maximum=1024)
                if checksum is None:
                    self._missing.add(path)
                    continue
                parts = checksum.decode("ascii").strip().split()
                if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]) or parts[1].lstrip("*") != filename:
                    raise ValueError("Invalid official archive checksum document")
                data = self._download(path, maximum=MAX_ZIP_BYTES)
                if data is None:
                    self._missing.add(path)
                    continue
                digest = sha256(data).hexdigest()
                if digest != parts[0].lower():
                    raise ValueError("Official archive checksum mismatch")
                # Drop the previous file before parsing the next to bound memory.
                self._candles, self._times, self._cache_key = [], [], None
                self._candles = parse_archive(data, symbol=symbol, pair=pair.display,
                    stamp=stamp, source_uri=ARCHIVE_ORIGIN + path, digest=digest)
                self._times = [c.open_time_ms for c in self._candles]
                self._cache_key = path
            check_execution()
            left = bisect_left(self._times, query.start_time_ms)
            right = bisect_right(self._times, query.end_time_ms)
            result = self._candles[left:min(right, left + query.limit)]
            # REST fills archive holes and partial archive boundaries. It does not
            # convert an empty archive response into invented zero-volume rows.
            expected = min(query.limit, (query.end_time_ms - query.start_time_ms) // 60000 + 1)
            if len(result) == expected and result and result[0].open_time_ms == query.start_time_ms:
                return result
            return self.rest.fetch_klines(query)
        return self.rest.fetch_klines(query)

    def _download(self, path, *, maximum):
        for attempt in range(3):
            check_execution()
            if self.limiter:
                self.limiter.acquire(1)
            try:
                with httpx.Client(base_url=ARCHIVE_ORIGIN, timeout=20, transport=self.transport,
                    follow_redirects=False) as client, client.stream("GET", path) as response:
                    if response.status_code == 404:
                        return None
                    if response.status_code in {418, 429} or response.status_code >= 500:
                        retry_after = response.headers.get("Retry-After", "")
                        delay = max(1, int(retry_after)) if retry_after.isdigit() else (120 if response.status_code == 418 else 2 ** attempt)
                        if self.limiter:
                            self.limiter.defer(delay)
                        if attempt < 2:
                            interruptible_wait(delay)
                            continue
                    response.raise_for_status()
                    chunks, length = [], 0
                    for chunk in response.iter_bytes():
                        check_execution()
                        length += len(chunk)
                        if length > maximum:
                            raise ValueError("Official archive exceeds size limit")
                        chunks.append(chunk)
                    return b"".join(chunks)
            except httpx.TransportError:
                if attempt == 2:
                    raise
                interruptible_wait(2 ** attempt)
        raise RuntimeError("Archive download failed")


def parse_archive(data, *, symbol, pair, stamp, source_uri, digest):
    result = []
    unit = "us" if stamp >= "2025-01" else "ms"
    divisor = 1000 if unit == "us" else 1
    previous = -1
    with ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        expected_name = f"{symbol}-1m-{stamp}.csv"
        if len(members) != 1 or members[0].filename != expected_name or members[0].file_size > MAX_CSV_BYTES:
            raise ValueError("Invalid official archive members")
        with archive.open(members[0]) as binary, TextIOWrapper(binary, encoding="utf-8", newline="") as stream:
            for index, row in enumerate(csv.reader(stream)):
                if index % 1000 == 0:
                    check_execution()
                if index >= 44640 or len(row) != 12:
                    raise ValueError("Invalid archive row count or shape")
                try:
                    raw_open, raw_close, trades = int(row[0]), int(row[6]), int(row[8])
                    open_ms, close_ms = raw_open // divisor, raw_close // divisor
                    if raw_open % divisor or open_ms % 60000 or close_ms != open_ms + 59999 or open_ms <= previous or trades < 0:
                        raise ValueError("Invalid archive candle time or ordering")
                    actual_stamp = datetime.fromtimestamp(open_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
                    if not actual_stamp.startswith(stamp):
                        raise ValueError("Archive candle outside file period")
                    numbers = [Decimal(row[i]) for i in (1, 2, 3, 4, 5, 7, 9, 10)]
                    if any(not v.is_finite() or v < 0 for v in numbers):
                        raise ValueError("Invalid archive numeric data")
                    op, hi, lo, cl = numbers[:4]
                    if lo > min(op, cl) or hi < max(op, cl) or lo > hi:
                        raise ValueError("Invalid archive OHLC")
                    normalized = [*row]
                    normalized[0], normalized[6], normalized[8] = open_ms, close_ms, trades
                    candle = map_provider_kline_to_candle(provider="binance", market_type="spot",
                        market_pair=pair, interval="1m", payload=normalized)
                    result.append(replace(candle, raw_payload_json=json.dumps(row, separators=(",", ":")),
                        source_uri=source_uri, source_sha256=digest, source_timestamp_unit=unit))
                    previous = open_ms
                except (InvalidOperation, OverflowError) as exc:
                    raise ValueError("Invalid archive numeric data") from exc
    return result
