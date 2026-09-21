from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from app.infrastructure.external.provider_limiter import ProviderLimiter
from app.application.services.execution_control import interruptible_wait, check_execution
import logging
import time

import httpx

from app.application.models.candle_query import CandleAvailabilityQuery, CandleBatchQuery
from app.application.models.provider_market import ProviderMarket
from app.application.models.market_catalog import CatalogSnapshot, CatalogSymbol
from app.domain.entities.candle import Candle
from app.domain.value_objects.market_pair import MarketPair
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle

logger = logging.getLogger(__name__)


class BinanceMarketDataClient:
    def __init__(self, *, base_url: str, timeout_seconds: float, limiter=None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._limiter = limiter or ProviderLimiter()

    def ping(self) -> bool:
        logger.info("Checking Binance API health base_url=%s", self._base_url)
        self._get_json_with_retry(fetch_id="ping", batch_index=0, path="/api/v3/ping",
                                  params={}, retry_attempts=0, retry_delay_seconds=0)
        return True

    def market_catalog(self) -> CatalogSnapshot:
        # Do not restrict status or truncate: absence is meaningful only in a
        # validated complete snapshot. The interactive search stays unchanged.
        payload = self._get_json_with_retry(
            fetch_id="market-catalog", batch_index=0, path="/api/v3/exchangeInfo",
            params={"permissions": "SPOT"}, retry_attempts=2, retry_delay_seconds=0.25,
        )
        return _map_catalog_snapshot(payload)


    def discover_markets(
        self,
        *,
        market_type: str,
        quote_asset: str | None,
        search: str | None,
        limit: int,
    ) -> list[ProviderMarket]:
        selected_market_type = market_type.strip().lower()
        if selected_market_type != "spot":
            raise ValueError("Binance market discovery currently supports spot markets only.")

        logger.info(
            "binance market discovery request started market_type=%s quote_asset=%s search=%s limit=%s",
            selected_market_type,
            quote_asset,
            search,
            limit,
        )
        request_started_at = time.perf_counter()
        payload = self._get_json_with_retry(
            fetch_id="provider-market-discovery",
            batch_index=0,
            path="/api/v3/exchangeInfo",
            params={"symbolStatus": "TRADING"},
            retry_attempts=2,
            retry_delay_seconds=0.25,
        )
        if not isinstance(payload, dict):
            raise ValueError("Binance exchangeInfo response must be an object.")
        symbols = payload.get("symbols")
        if not isinstance(symbols, list):
            raise ValueError("Binance exchangeInfo response must include a symbols list.")

        discovered = _map_exchange_info_symbols(
            symbols=symbols,
            quote_asset=quote_asset,
            search=search,
            limit=limit,
        )
        logger.info(
            "binance market discovery request completed market_type=%s quote_asset=%s search=%s discovered_count=%s duration_ms=%s",
            selected_market_type,
            quote_asset,
            search,
            len(discovered),
            int((time.perf_counter() - request_started_at) * 1000),
        )
        return discovered

    def first_available_open_time_ms(self, query: CandleAvailabilityQuery) -> int | None:
        pair = MarketPair.parse(query.market_pair)
        exchange_symbol = pair.exchange_symbol_for(query.provider)
        params: dict[str, str | int] = {
            "symbol": exchange_symbol,
            "interval": query.interval,
            "limit": 1,
            "startTime": query.start_time_ms,
            "endTime": query.end_time_ms,
        }

        logger.info(
            "binance first available kline request started fetch_id=%s symbol=%s interval=%s start_time_ms=%s end_time_ms=%s retry_attempts=%s",
            query.fetch_id,
            exchange_symbol,
            query.interval,
            query.start_time_ms,
            query.end_time_ms,
            query.retry_attempts,
        )
        request_started_at = time.perf_counter()
        payload = self._get_json_with_retry(
            fetch_id=query.fetch_id,
            batch_index=0,
            path="/api/v3/klines",
            params=params,
            retry_attempts=query.retry_attempts,
            retry_delay_seconds=query.retry_delay_seconds,
        )
        if not isinstance(payload, list):
            logger.error(
                "binance first available kline payload invalid fetch_id=%s payload_type=%s",
                query.fetch_id,
                type(payload).__name__,
            )
            raise ValueError("Binance klines response must be a list.")

        first_open_time_ms = _first_kline_open_time_ms(payload)
        logger.info(
            "binance first available kline request completed fetch_id=%s symbol=%s interval=%s provider_count=%s first_open_time_ms=%s duration_ms=%s",
            query.fetch_id,
            exchange_symbol,
            query.interval,
            len(payload),
            first_open_time_ms,
            int((time.perf_counter() - request_started_at) * 1000),
        )
        return first_open_time_ms

    def fetch_klines(self, query: CandleBatchQuery) -> list[Candle]:
        pair = MarketPair.parse(query.market_pair)
        exchange_symbol = pair.exchange_symbol_for(query.provider)
        params: dict[str, str | int] = {
            "symbol": exchange_symbol,
            "interval": query.interval,
            "limit": query.limit,
            "startTime": query.start_time_ms,
            "endTime": query.end_time_ms,
        }

        logger.info(
            "binance klines request started fetch_id=%s batch_index=%s batch_count=%s symbol=%s interval=%s start_time_ms=%s end_time_ms=%s limit=%s retry_attempts=%s",
            query.fetch_id,
            query.batch_index,
            query.batch_count,
            exchange_symbol,
            query.interval,
            query.start_time_ms,
            query.end_time_ms,
            query.limit,
            query.retry_attempts,
        )
        request_started_at = time.perf_counter()
        payload = self._get_json_with_retry(
            fetch_id=query.fetch_id,
            batch_index=query.batch_index,
            path="/api/v3/klines",
            params=params,
            retry_attempts=query.retry_attempts,
            retry_delay_seconds=query.retry_delay_seconds,
        )
        if not isinstance(payload, list):
            logger.error(
                "binance klines payload invalid fetch_id=%s batch_index=%s payload_type=%s",
                query.fetch_id,
                query.batch_index,
                type(payload).__name__,
            )
            raise ValueError("Binance klines response must be a list.")

        logger.info(
            "binance klines request completed fetch_id=%s batch_index=%s symbol=%s interval=%s provider_count=%s first_open_time_ms=%s last_open_time_ms=%s duration_ms=%s",
            query.fetch_id,
            query.batch_index,
            exchange_symbol,
            query.interval,
            len(payload),
            payload[0][0] if payload else None,
            payload[-1][0] if payload else None,
            int((time.perf_counter() - request_started_at) * 1000),
        )

        return [
            map_provider_kline_to_candle(
                provider=query.provider,
                market_type=query.market_type,
                market_pair=pair.display,
                interval=query.interval,
                payload=item,
            )
            for item in payload
        ]

    def _get_json_with_retry(
        self,
        *,
        fetch_id: str,
        batch_index: int,
        path: str,
        params: dict[str, str | int],
        retry_attempts: int,
        retry_delay_seconds: float,
    ) -> object:
        for attempt in range(retry_attempts + 1):
            attempt_started_at = time.perf_counter()
            try:
                # Binance Spot documented IP weights: ping 1, klines 2, exchangeInfo 20.
                self._limiter.acquire({"/api/v3/ping": 1, "/api/v3/klines": 2, "/api/v3/exchangeInfo": 20}[path])
                with httpx.Client(base_url=self._base_url, timeout=self._timeout_seconds) as client:
                    response = client.get(path, params=params)
                    if response.status_code in {429, 418}:
                        retry_after = response.headers.get("Retry-After", "60")
                        try:
                            cooldown = float(retry_after)
                        except ValueError:
                            try:
                                cooldown = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                            except (ValueError, TypeError):
                                cooldown = 60
                        self._limiter.defer(cooldown)
                    response.raise_for_status()
                    logger.info(
                        "binance http request completed fetch_id=%s batch_index=%s path=%s attempt=%s status_code=%s duration_ms=%s",
                        fetch_id,
                        batch_index,
                        path,
                        attempt + 1,
                        response.status_code,
                        int((time.perf_counter() - attempt_started_at) * 1000),
                    )
                    check_execution()
                    return response.json()
            except httpx.HTTPError as exc:
                if attempt >= retry_attempts or not self._should_retry(exc):
                    logger.exception(
                        "binance http request failed fetch_id=%s batch_index=%s path=%s attempt=%s retryable=%s duration_ms=%s",
                        fetch_id,
                        batch_index,
                        path,
                        attempt + 1,
                        self._should_retry(exc),
                        int((time.perf_counter() - attempt_started_at) * 1000),
                    )
                    raise
                delay = retry_delay_seconds * (attempt + 1)
                logger.warning(
                    "binance http request retrying fetch_id=%s batch_index=%s path=%s attempt=%s max_attempts=%s delay_seconds=%s error=%s",
                    fetch_id,
                    batch_index,
                    path,
                    attempt + 1,
                    retry_attempts,
                    delay,
                    exc,
                )
                if delay > 0:
                    interruptible_wait(delay)
        raise RuntimeError("Unexpected retry loop exit.")

    def _should_retry(self, exc: httpx.HTTPError) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            return status_code == 429 or status_code >= 500
        return isinstance(exc, httpx.TransportError)


def _map_catalog_snapshot(payload: object) -> CatalogSnapshot:
    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
        raise ValueError("Incomplete Binance market catalog: symbols list is required.")
    server_time = payload.get("serverTime")
    if isinstance(server_time, bool) or not isinstance(server_time, int) or server_time < 0:
        raise ValueError("Invalid Binance market catalog server time.")
    symbols: list[CatalogSymbol] = []
    seen: set[str] = set()
    for item in payload["symbols"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid Binance catalog entry.")
        values = [item.get(key) for key in ("symbol", "baseAsset", "quoteAsset", "status")]
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("Incomplete Binance catalog entry.")
        symbol, base, quote, status = (value.strip().upper() for value in values)
        if symbol != base + quote or any(c in base + quote for c in "/-"):
            raise ValueError(f"Unsupported catalog market identity: {symbol}.")
        allowed = item.get("isSpotTradingAllowed")
        if not isinstance(allowed, bool) or symbol in seen:
            raise ValueError(f"Invalid or duplicate catalog symbol: {symbol}.")
        seen.add(symbol)
        symbols.append(CatalogSymbol(symbol, base, quote, status, allowed))
    if not symbols:
        raise ValueError("Empty Binance catalog cannot replace the last valid snapshot.")
    weight_limit = None
    limits = payload.get("rateLimits", [])
    if not isinstance(limits, list):
        raise ValueError("Invalid Binance rate limits.")
    for limit in limits:
        if (isinstance(limit, dict) and limit.get("rateLimitType") == "REQUEST_WEIGHT"
                and limit.get("interval") == "MINUTE" and limit.get("intervalNum") == 1):
            value = limit.get("limit")
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                weight_limit = value
    return CatalogSnapshot(tuple(symbols), server_time, weight_limit)


def _map_exchange_info_symbols(
    *,
    symbols: list[object],
    quote_asset: str | None,
    search: str | None,
    limit: int,
) -> list[ProviderMarket]:
    selected_quote_asset = quote_asset.strip().upper() if quote_asset else None
    selected_search = search.strip().upper() if search else None
    markets: list[ProviderMarket] = []
    for item in symbols:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).strip().upper()
        base_asset = str(item.get("baseAsset", "")).strip().upper()
        item_quote_asset = str(item.get("quoteAsset", "")).strip().upper()
        exchange_symbol = str(item.get("symbol", "")).strip().upper()
        if status != "TRADING" or not base_asset or not item_quote_asset or not exchange_symbol:
            continue
        market_pair = f"{base_asset}/{item_quote_asset}"
        if selected_quote_asset and item_quote_asset != selected_quote_asset:
            continue
        if selected_search and not _matches_market_search(
            search=selected_search,
            market_pair=market_pair,
            exchange_symbol=exchange_symbol,
            base_asset=base_asset,
            quote_asset=item_quote_asset,
        ):
            continue
        markets.append(
            ProviderMarket(
                provider="binance",
                market_type="spot",
                market_pair=market_pair,
                exchange_symbol=exchange_symbol,
                base_asset=base_asset,
                quote_asset=item_quote_asset,
                status=status,
            )
        )
        if len(markets) >= limit:
            break
    return markets


def _first_kline_open_time_ms(payload: list[object]) -> int | None:
    if not payload:
        return None
    first_item = payload[0]
    if not isinstance(first_item, list):
        raise ValueError("Expected binance kline payload item to be a list.")
    if not first_item:
        raise ValueError("Expected binance kline payload item to include open time.")
    return int(first_item[0])


def _matches_market_search(
    *,
    search: str,
    market_pair: str,
    exchange_symbol: str,
    base_asset: str,
    quote_asset: str,
) -> bool:
    return (
        search in market_pair
        or search in market_pair.replace("/", "")
        or search in exchange_symbol
        or search in base_asset
        or search in quote_asset
    )
