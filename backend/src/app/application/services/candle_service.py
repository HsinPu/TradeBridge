import logging
from dataclasses import dataclass, replace

from app.application.models.candle_query import CandleFetchQuery, CandleListItem
from app.application.ports.candle_repository import CandleRepository
from app.application.ports.market_data_provider import MarketDataProviderResolver
from app.application.services.candle_fetch_planner import (
    datetime_to_ms,
    ms_to_iso,
)
from app.domain.entities.candle import Candle
from app.domain.value_objects.candle_interval import CandleInterval

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MissingCandleRange:
    start_open_time_ms: int
    end_open_time_ms: int
    start_open_time: str
    end_open_time: str
    missing_count: int




class CandleService:
    def __init__(
        self,
        repository: CandleRepository,
        provider_resolver: MarketDataProviderResolver,
    ) -> None:
        self._repository = repository
        self._provider_resolver = provider_resolver


    def list_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time=None,
        end_time=None,
    ) -> list[Candle]:
        start_time_ms = datetime_to_ms(start_time)
        end_time_ms = datetime_to_ms(end_time)
        logger.info(
            "Listing candles provider=%s market_pair=%s interval=%s limit=%s offset=%s start_time_ms=%s end_time_ms=%s",
            provider,
            market_pair,
            interval,
            limit,
            offset,
            start_time_ms,
            end_time_ms,
        )
        return self._repository.list_candles(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            limit=limit,
            offset=offset,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

    def list_candle_items(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        offset: int = 0,
        start_time=None,
        end_time=None,
    ) -> list[CandleListItem]:
        start_time_ms = datetime_to_ms(start_time)
        end_time_ms = datetime_to_ms(end_time)
        logger.info(
            "Listing candle items provider=%s market_pair=%s interval=%s limit=%s offset=%s start_time_ms=%s end_time_ms=%s",
            provider,
            market_pair,
            interval,
            limit,
            offset,
            start_time_ms,
            end_time_ms,
        )
        return self._repository.list_candle_items(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            limit=limit,
            offset=offset,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

    def get_candle_detail(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        open_time_ms: int,
    ) -> Candle:
        candle = self._repository.get_candle(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            open_time_ms=open_time_ms,
        )
        if candle is None:
            raise ValueError("Candle not found.")
        return candle

    def count_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time=None,
        end_time=None,
    ) -> int:
        start_time_ms = datetime_to_ms(start_time)
        end_time_ms = datetime_to_ms(end_time)
        logger.info(
            "Counting candles provider=%s market_pair=%s interval=%s start_time_ms=%s end_time_ms=%s",
            provider,
            market_pair,
            interval,
            start_time_ms,
            end_time_ms,
        )
        return self._repository.count_candles(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

    def coverage(self, *, provider: str, market_pair: str, interval: str) -> dict[str, int | str | None]:
        logger.info("Reading candle coverage provider=%s market_pair=%s interval=%s", provider, market_pair, interval)
        return self._repository.coverage(provider=provider, market_pair=market_pair, interval=interval)

    def missing_ranges(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time=None,
        end_time=None,
    ) -> dict[str, int | str | list[MissingCandleRange] | None]:
        logger.info(
            "Reading candle gaps provider=%s market_pair=%s interval=%s start_time=%s end_time=%s",
            provider,
            market_pair,
            interval,
            start_time,
            end_time,
        )
        coverage = self._repository.coverage(provider=provider, market_pair=market_pair, interval=interval)
        interval_value = CandleInterval.parse(interval)
        requested_start_time_ms = datetime_to_ms(start_time)
        requested_end_time_ms = datetime_to_ms(end_time)
        first_open_time_ms = coverage.get("first_open_time_ms")
        last_open_time_ms = coverage.get("last_open_time_ms")

        if requested_start_time_ms is None and first_open_time_ms is None:
            return self._empty_missing_ranges_response(coverage=coverage)
        if requested_end_time_ms is None and last_open_time_ms is None:
            return self._empty_missing_ranges_response(coverage=coverage)

        start_open_time_ms = interval_value.floor_open_time_ms(
            requested_start_time_ms if requested_start_time_ms is not None else int(first_open_time_ms)
        )
        end_open_time_ms = interval_value.floor_open_time_ms(
            requested_end_time_ms if requested_end_time_ms is not None else int(last_open_time_ms)
        )
        if start_open_time_ms > end_open_time_ms:
            raise ValueError("Gap range start_time must be before end_time.")

        missing_ranges = self._find_missing_ranges_for_bounds(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            interval_ms=interval_value.milliseconds,
            start_open_time_ms=start_open_time_ms,
            end_open_time_ms=end_open_time_ms,
        )
        missing_count = sum(item.missing_count for item in missing_ranges)
        return {
            "provider": coverage["provider"],
            "market_pair": coverage["market_pair"],
            "exchange_symbol": coverage["exchange_symbol"],
            "interval": interval,
            "checked_start_open_time_ms": start_open_time_ms,
            "checked_end_open_time_ms": end_open_time_ms,
            "checked_start_open_time": ms_to_iso(start_open_time_ms),
            "checked_end_open_time": ms_to_iso(end_open_time_ms),
            "missing_count": missing_count,
            "missing_ranges": missing_ranges,
        }

    def _empty_missing_ranges_response(
        self,
        *,
        coverage: dict[str, int | str | None],
    ) -> dict[str, int | str | list[MissingCandleRange] | None]:
        return {
            "provider": coverage["provider"],
            "market_pair": coverage["market_pair"],
            "exchange_symbol": coverage["exchange_symbol"],
            "interval": coverage["interval"],
            "checked_start_open_time_ms": None,
            "checked_end_open_time_ms": None,
            "checked_start_open_time": None,
            "checked_end_open_time": None,
            "missing_count": 0,
            "missing_ranges": [],
        }

    def resolve_auto_query(
        self,
        *,
        query: CandleFetchQuery,
        coverage: dict[str, int | str | None],
        fetch_id: str,
    ) -> CandleFetchQuery:
        if query.mode != "auto":
            return query

        first_open_time_ms = coverage.get("first_open_time_ms")
        last_open_time_ms = coverage.get("last_open_time_ms")
        if first_open_time_ms is None or last_open_time_ms is None:
            return query

        interval = CandleInterval.parse(query.interval)
        missing_ranges = self._find_missing_ranges_for_bounds(
            provider=query.provider,
            market_pair=query.market_pair,
            interval=query.interval,
            interval_ms=interval.milliseconds,
            start_open_time_ms=int(first_open_time_ms),
            end_open_time_ms=int(last_open_time_ms),
        )
        if not missing_ranges:
            logger.info(
                "auto mode selected fetch_id=%s selected_mode=incremental reason=no_existing_gap market_pair=%s interval=%s",
                fetch_id,
                query.market_pair,
                query.interval,
            )
            return query

        logger.info(
            "auto mode selected fetch_id=%s selected_mode=fill_gaps reason=existing_gap market_pair=%s interval=%s missing_range_count=%s first_missing_start_ms=%s first_missing_end_ms=%s",
            fetch_id,
            query.market_pair,
            query.interval,
            len(missing_ranges),
            missing_ranges[0].start_open_time_ms,
            missing_ranges[0].end_open_time_ms,
        )
        return replace(query, mode="fill_gaps")





    def _find_missing_ranges_for_bounds(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        interval_ms: int,
        start_open_time_ms: int,
        end_open_time_ms: int,
    ) -> list[MissingCandleRange]:
        actual_open_times = set(
            self._repository.list_open_time_ms(
                provider=provider,
                market_pair=market_pair,
                interval=interval,
                start_time_ms=start_open_time_ms,
                end_time_ms=end_open_time_ms,
            )
        )

        missing_ranges: list[MissingCandleRange] = []
        current_start: int | None = None
        current_end: int | None = None
        current_count = 0

        expected_time = start_open_time_ms
        while expected_time <= end_open_time_ms:
            if expected_time not in actual_open_times:
                if current_start is None:
                    current_start = expected_time
                current_end = expected_time
                current_count += 1
            elif current_start is not None and current_end is not None:
                missing_ranges.append(
                    MissingCandleRange(
                        start_open_time_ms=current_start,
                        end_open_time_ms=current_end,
                        start_open_time=ms_to_iso(current_start) or "",
                        end_open_time=ms_to_iso(current_end) or "",
                        missing_count=current_count,
                    )
                )
                current_start = None
                current_end = None
                current_count = 0
            expected_time += interval_ms

        if current_start is not None and current_end is not None:
            missing_ranges.append(
                MissingCandleRange(
                    start_open_time_ms=current_start,
                    end_open_time_ms=current_end,
                    start_open_time=ms_to_iso(current_start) or "",
                    end_open_time=ms_to_iso(current_end) or "",
                    missing_count=current_count,
                )
            )

        return missing_ranges
