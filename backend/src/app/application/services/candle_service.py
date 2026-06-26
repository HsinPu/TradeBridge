import logging
from time import perf_counter
from dataclasses import dataclass, replace
from uuid import uuid4

from app.application.models.candle_query import CandleBatchQuery, CandleFetchQuery, CandleListItem
from app.application.ports.candle_repository import CandleRepository
from app.application.ports.market_data_provider import MarketDataProviderResolver
from app.application.services.candle_fetch_planner import (
    CandleFetchPlan,
    build_fetch_plan,
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


@dataclass(frozen=True)
class CandleFetchResult:
    fetch_id: str
    candles: list[Candle]
    saved_count: int
    plan: CandleFetchPlan
    is_complete: bool
    missing_count: int
    missing_ranges: list[MissingCandleRange]


class CandleService:
    def __init__(
        self,
        repository: CandleRepository,
        provider_resolver: MarketDataProviderResolver,
    ) -> None:
        self._repository = repository
        self._provider_resolver = provider_resolver

    def fetch_and_store(self, query: CandleFetchQuery) -> CandleFetchResult:
        fetch_id = uuid4().hex[:12]
        started_at = perf_counter()
        logger.info(
            "candle fetch started fetch_id=%s provider=%s market_type=%s market_pair=%s interval=%s requested_mode=%s start_time=%s end_time=%s limit=%s closed_only=%s overlap_candles=%s batch_limit=%s max_batches=%s verify_continuity=%s retry_attempts=%s",
            fetch_id,
            query.provider,
            query.market_type,
            query.market_pair,
            query.interval,
            query.mode,
            query.start_time,
            query.end_time,
            query.limit,
            query.closed_only,
            query.overlap_candles,
            query.batch_limit,
            query.max_batches,
            query.verify_continuity,
            query.retry_attempts,
        )
        try:
            coverage = self._repository.coverage(
                provider=query.provider,
                market_pair=query.market_pair,
                interval=query.interval,
            )
            logger.info(
                "candle coverage loaded fetch_id=%s market_pair=%s interval=%s candle_count=%s first_open_time_ms=%s last_open_time_ms=%s first_open_time=%s last_open_time=%s",
                fetch_id,
                query.market_pair,
                query.interval,
                coverage.get("candle_count"),
                coverage.get("first_open_time_ms"),
                coverage.get("last_open_time_ms"),
                coverage.get("first_open_time"),
                coverage.get("last_open_time"),
            )

            query = self._resolve_auto_query(query=query, coverage=coverage, fetch_id=fetch_id)
            plan = build_fetch_plan(query, coverage=coverage)
            logger.info(
                "candle fetch planned fetch_id=%s mode=%s market_pair=%s interval=%s interval_ms=%s expected_candle_count=%s batch_count=%s effective_start_open_time_ms=%s effective_end_open_time_ms=%s effective_start_open_time=%s effective_end_open_time=%s excluded_open_candle=%s",
                fetch_id,
                plan.mode,
                query.market_pair,
                query.interval,
                plan.interval_ms,
                plan.expected_candle_count,
                len(plan.batches),
                plan.effective_start_open_time_ms,
                plan.effective_end_open_time_ms,
                ms_to_iso(plan.effective_start_open_time_ms),
                ms_to_iso(plan.effective_end_open_time_ms),
                plan.excluded_open_candle,
            )

            candles = self._fetch_plan_batches(query=query, plan=plan, fetch_id=fetch_id)
            storage_started_at = perf_counter()
            saved_count = self._store_fetched_candles(
                query=query,
                plan=plan,
                candles=candles,
                fetch_id=fetch_id,
            )
            logger.info(
                "candle storage completed fetch_id=%s mode=%s fetched_count=%s saved_count=%s duration_ms=%s",
                fetch_id,
                plan.mode,
                len(candles),
                saved_count,
                int((perf_counter() - storage_started_at) * 1000),
            )

            continuity_started_at = perf_counter()
            missing_ranges = (
                self._find_missing_ranges(plan=plan)
                if plan.verify_continuity
                else []
            )
            missing_count = sum(item.missing_count for item in missing_ranges)
            logger.info(
                "candle continuity checked fetch_id=%s enabled=%s is_complete=%s missing_count=%s missing_range_count=%s duration_ms=%s",
                fetch_id,
                plan.verify_continuity,
                missing_count == 0,
                missing_count,
                len(missing_ranges),
                int((perf_counter() - continuity_started_at) * 1000),
            )
            for index, missing_range in enumerate(missing_ranges[:5], start=1):
                logger.warning(
                    "candle gap detected fetch_id=%s range_index=%s start_open_time_ms=%s end_open_time_ms=%s start_open_time=%s end_open_time=%s missing_count=%s",
                    fetch_id,
                    index,
                    missing_range.start_open_time_ms,
                    missing_range.end_open_time_ms,
                    missing_range.start_open_time,
                    missing_range.end_open_time,
                    missing_range.missing_count,
                )

            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.info(
                "candle fetch completed fetch_id=%s provider=%s market_pair=%s interval=%s mode=%s fetched_count=%s saved_count=%s is_complete=%s missing_count=%s duration_ms=%s",
                fetch_id,
                query.provider,
                query.market_pair,
                query.interval,
                plan.mode,
                len(candles),
                saved_count,
                missing_count == 0,
                missing_count,
                duration_ms,
            )
            return CandleFetchResult(
                fetch_id=fetch_id,
                candles=candles,
                saved_count=saved_count,
                plan=plan,
                is_complete=missing_count == 0,
                missing_count=missing_count,
                missing_ranges=missing_ranges,
            )
        except Exception:
            logger.exception(
                "candle fetch failed fetch_id=%s provider=%s market_pair=%s interval=%s requested_mode=%s duration_ms=%s",
                fetch_id,
                query.provider,
                query.market_pair,
                query.interval,
                query.mode,
                int((perf_counter() - started_at) * 1000),
            )
            raise

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

    def _resolve_auto_query(
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

    def _fetch_plan_batches(
        self,
        *,
        query: CandleFetchQuery,
        plan: CandleFetchPlan,
        fetch_id: str,
    ) -> list[Candle]:
        candles_by_open_time: dict[int, Candle] = {}
        provider = self._provider_resolver.get(query.provider)
        for index, batch in enumerate(plan.batches, start=1):
            batch_started_at = perf_counter()
            logger.info(
                "candle batch started fetch_id=%s batch_index=%s batch_count=%s start_time_ms=%s end_time_ms=%s start_open_time_ms=%s end_open_time_ms=%s limit=%s",
                fetch_id,
                index,
                len(plan.batches),
                batch.start_time_ms,
                batch.end_time_ms,
                batch.start_open_time_ms,
                batch.end_open_time_ms,
                batch.limit,
            )
            batch_candles = provider.fetch_klines(
                CandleBatchQuery(
                    fetch_id=fetch_id,
                    batch_index=index,
                    batch_count=len(plan.batches),
                    provider=query.provider,
                    market_type=query.market_type,
                    market_pair=query.market_pair,
                    interval=query.interval,
                    start_time_ms=batch.start_time_ms,
                    end_time_ms=batch.end_time_ms,
                    limit=batch.limit,
                    retry_attempts=query.retry_attempts,
                    retry_delay_seconds=query.retry_delay_seconds,
                )
            )
            accepted_count = 0
            for candle in batch_candles:
                if plan.effective_start_open_time_ms <= candle.open_time_ms <= plan.effective_end_open_time_ms:
                    candles_by_open_time[candle.open_time_ms] = candle
                    accepted_count += 1
            logger.info(
                "candle batch completed fetch_id=%s batch_index=%s batch_count=%s provider_count=%s accepted_count=%s unique_count=%s first_open_time_ms=%s last_open_time_ms=%s duration_ms=%s",
                fetch_id,
                index,
                len(plan.batches),
                len(batch_candles),
                accepted_count,
                len(candles_by_open_time),
                batch_candles[0].open_time_ms if batch_candles else None,
                batch_candles[-1].open_time_ms if batch_candles else None,
                int((perf_counter() - batch_started_at) * 1000),
            )

        return [
            candles_by_open_time[open_time_ms]
            for open_time_ms in sorted(candles_by_open_time.keys())
        ]

    def _store_fetched_candles(
        self,
        *,
        query: CandleFetchQuery,
        plan: CandleFetchPlan,
        candles: list[Candle],
        fetch_id: str,
    ) -> int:
        if plan.mode != "delete_reload":
            return self._repository.upsert_many(candles)

        self._ensure_complete_fetched_range(plan=plan, candles=candles)
        logger.info(
            "candle delete reload replacing range fetch_id=%s market_pair=%s interval=%s start_open_time_ms=%s end_open_time_ms=%s candle_count=%s",
            fetch_id,
            query.market_pair,
            query.interval,
            plan.effective_start_open_time_ms,
            plan.effective_end_open_time_ms,
            len(candles),
        )
        return self._repository.replace_range(
            provider=query.provider,
            market_type=query.market_type,
            market_pair=query.market_pair,
            interval=query.interval,
            start_time_ms=plan.effective_start_open_time_ms,
            end_time_ms=plan.effective_end_open_time_ms,
            candles=candles,
        )

    def _ensure_complete_fetched_range(
        self,
        *,
        plan: CandleFetchPlan,
        candles: list[Candle],
    ) -> None:
        actual_open_times = {candle.open_time_ms for candle in candles}
        expected_time = plan.effective_start_open_time_ms
        missing_count = 0
        first_missing_time: int | None = None

        while expected_time <= plan.effective_end_open_time_ms:
            if expected_time not in actual_open_times:
                missing_count += 1
                if first_missing_time is None:
                    first_missing_time = expected_time
            expected_time += plan.interval_ms

        if missing_count:
            raise ValueError(
                "delete_reload requires a complete provider response before replacing stored data. "
                f"missing_count={missing_count}, first_missing_open_time={ms_to_iso(first_missing_time)}"
            )

    def _find_missing_ranges(self, *, plan: CandleFetchPlan) -> list[MissingCandleRange]:
        return self._find_missing_ranges_for_bounds(
            provider=plan.provider,
            market_pair=plan.market_pair,
            interval=plan.interval,
            interval_ms=plan.interval_ms,
            start_open_time_ms=plan.effective_start_open_time_ms,
            end_open_time_ms=plan.effective_end_open_time_ms,
        )

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
