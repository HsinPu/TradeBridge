from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.models.candle_query import CandleFetchQuery
from app.domain.value_objects.candle_interval import CandleInterval


def datetime_to_ms(value: datetime | None) -> int | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def ms_to_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def ms_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    return ms_to_datetime(value).isoformat()


@dataclass(frozen=True)
class FetchBatch:
    start_open_time_ms: int
    end_open_time_ms: int
    start_time_ms: int
    end_time_ms: int
    limit: int


@dataclass(frozen=True)
class CandleFetchPlan:
    mode: str
    provider: str
    market_pair: str
    interval: str
    interval_ms: int
    closed_only: bool
    overlap_candles: int
    batch_limit: int
    max_batches: int
    verify_continuity: bool
    retry_attempts: int
    retry_delay_seconds: float
    requested_start_time_ms: int | None
    requested_end_time_ms: int | None
    effective_start_open_time_ms: int
    effective_end_open_time_ms: int
    effective_end_time_ms: int
    expected_candle_count: int
    excluded_open_candle: bool
    batches: list[FetchBatch]


def build_fetch_plan(
    query: CandleFetchQuery,
    *,
    coverage: dict[str, int | str | None],
    now: datetime | None = None,
) -> CandleFetchPlan:
    interval = CandleInterval.parse(query.interval)
    now_ms = datetime_to_ms(now or datetime.now(timezone.utc))
    if now_ms is None:
        raise ValueError("Unable to resolve current time.")

    current_open_time_ms = interval.floor_open_time_ms(now_ms)
    last_closed_open_time_ms = interval.last_closed_open_time_ms(now_ms)
    last_closed_end_time_ms = last_closed_open_time_ms + interval.milliseconds - 1

    requested_start_time_ms = datetime_to_ms(query.start_time)
    requested_end_time_ms = datetime_to_ms(query.end_time)
    mode = _resolve_mode(query=query, coverage=coverage)

    effective_end_time_ms = _resolve_effective_end_time_ms(
        mode=mode,
        coverage=coverage,
        interval=interval,
        requested_end_time_ms=requested_end_time_ms,
        now_ms=now_ms,
        last_closed_end_time_ms=last_closed_end_time_ms,
        closed_only=query.closed_only,
    )
    effective_end_open_time_ms = interval.floor_open_time_ms(effective_end_time_ms)

    effective_start_open_time_ms = _resolve_effective_start_open_time_ms(
        query=query,
        interval=interval,
        mode=mode,
        requested_start_time_ms=requested_start_time_ms,
        effective_end_open_time_ms=effective_end_open_time_ms,
        coverage=coverage,
    )

    if effective_start_open_time_ms > effective_end_open_time_ms:
        raise ValueError("Fetch range has no complete candles. Try a later end_time or set closed_only=false.")

    batches = _build_batches(
        interval_ms=interval.milliseconds,
        start_open_time_ms=effective_start_open_time_ms,
        end_open_time_ms=effective_end_open_time_ms,
        batch_limit=query.batch_limit,
        max_batches=query.max_batches,
    )
    expected_candle_count = _count_expected_candles(
        start_open_time_ms=effective_start_open_time_ms,
        end_open_time_ms=effective_end_open_time_ms,
        interval_ms=interval.milliseconds,
    )

    return CandleFetchPlan(
        mode=mode,
        provider=query.provider,
        market_pair=query.market_pair,
        interval=query.interval,
        interval_ms=interval.milliseconds,
        closed_only=query.closed_only,
        overlap_candles=query.overlap_candles,
        batch_limit=query.batch_limit,
        max_batches=query.max_batches,
        verify_continuity=query.verify_continuity,
        retry_attempts=query.retry_attempts,
        retry_delay_seconds=query.retry_delay_seconds,
        requested_start_time_ms=requested_start_time_ms,
        requested_end_time_ms=requested_end_time_ms,
        effective_start_open_time_ms=effective_start_open_time_ms,
        effective_end_open_time_ms=effective_end_open_time_ms,
        effective_end_time_ms=effective_end_time_ms,
        expected_candle_count=expected_candle_count,
        excluded_open_candle=(
            query.closed_only
            and effective_end_time_ms == last_closed_end_time_ms
            and (requested_end_time_ms is None or requested_end_time_ms > last_closed_end_time_ms)
            and effective_end_open_time_ms < current_open_time_ms
        ),
        batches=batches,
    )


def _resolve_mode(
    *,
    query: CandleFetchQuery,
    coverage: dict[str, int | str | None],
) -> str:
    if query.mode in {"overwrite_range", "delete_reload"}:
        if query.start_time is None or query.end_time is None:
            raise ValueError(f"start_time and end_time are required when mode is {query.mode}.")
        return query.mode
    if query.mode == "backfill":
        if query.start_time is None:
            raise ValueError("start_time is required when mode is backfill.")
        return "backfill"
    if query.mode == "fill_gaps":
        return "fill_gaps"
    if query.mode == "latest":
        return "latest"
    if query.start_time is not None:
        return "backfill"
    if coverage.get("last_open_time_ms") is not None:
        return "incremental"
    return "latest"


def _resolve_effective_end_time_ms(
    *,
    mode: str,
    coverage: dict[str, int | str | None],
    interval: CandleInterval,
    requested_end_time_ms: int | None,
    now_ms: int,
    last_closed_end_time_ms: int,
    closed_only: bool,
) -> int:
    if mode == "fill_gaps" and requested_end_time_ms is None and coverage.get("last_open_time_ms") is not None:
        return int(coverage["last_open_time_ms"]) + interval.milliseconds - 1

    end_time_ms = requested_end_time_ms if requested_end_time_ms is not None else now_ms
    if closed_only:
        return min(end_time_ms, last_closed_end_time_ms)
    return end_time_ms


def _resolve_effective_start_open_time_ms(
    *,
    query: CandleFetchQuery,
    interval: CandleInterval,
    mode: str,
    requested_start_time_ms: int | None,
    effective_end_open_time_ms: int,
    coverage: dict[str, int | str | None],
) -> int:
    if requested_start_time_ms is not None:
        return interval.floor_open_time_ms(requested_start_time_ms)

    if mode == "fill_gaps":
        first_open_time_ms = coverage.get("first_open_time_ms")
        if first_open_time_ms is not None:
            return int(first_open_time_ms)

    if mode == "incremental":
        last_open_time_ms = coverage.get("last_open_time_ms")
        if last_open_time_ms is None:
            raise ValueError("No previous candle coverage found for incremental mode.")
        safe_start = int(last_open_time_ms) - (query.overlap_candles * interval.milliseconds)
        return max(0, min(safe_start, effective_end_open_time_ms))

    return max(0, effective_end_open_time_ms - ((query.limit - 1) * interval.milliseconds))


def _build_batches(
    *,
    interval_ms: int,
    start_open_time_ms: int,
    end_open_time_ms: int,
    batch_limit: int,
    max_batches: int,
) -> list[FetchBatch]:
    batches: list[FetchBatch] = []
    cursor = start_open_time_ms
    while cursor <= end_open_time_ms:
        if len(batches) >= max_batches:
            raise ValueError(
                "Fetch range is larger than max_batches allows. Increase max_batches or narrow the time range."
            )

        batch_end_open_time_ms = min(
            end_open_time_ms,
            cursor + ((batch_limit - 1) * interval_ms),
        )
        limit = _count_expected_candles(
            start_open_time_ms=cursor,
            end_open_time_ms=batch_end_open_time_ms,
            interval_ms=interval_ms,
        )
        batches.append(
            FetchBatch(
                start_open_time_ms=cursor,
                end_open_time_ms=batch_end_open_time_ms,
                start_time_ms=cursor,
                end_time_ms=batch_end_open_time_ms + interval_ms - 1,
                limit=limit,
            )
        )
        cursor = batch_end_open_time_ms + interval_ms

    return batches


def _count_expected_candles(
    *,
    start_open_time_ms: int,
    end_open_time_ms: int,
    interval_ms: int,
) -> int:
    return ((end_open_time_ms - start_open_time_ms) // interval_ms) + 1
