from datetime import datetime, timezone

import pytest

from app.application.models.candle_query import CandleFetchQuery
from app.application.services.candle_fetch_planner import build_fetch_plan


def _query(**overrides) -> CandleFetchQuery:
    defaults = {
        "provider": "binance",
        "market_type": "spot",
        "market_pair": "BTC/USDT",
        "interval": "1m",
        "start_time": None,
        "end_time": None,
        "limit": 5,
        "mode": "auto",
        "closed_only": True,
        "overlap_candles": 2,
        "batch_limit": 1000,
        "max_batches": 10,
        "verify_continuity": True,
        "retry_attempts": 2,
        "retry_delay_seconds": 0,
    }
    defaults.update(overrides)
    return CandleFetchQuery(**defaults)


def _dt_from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def test_latest_plan_excludes_current_open_candle() -> None:
    plan = build_fetch_plan(
        _query(limit=5),
        coverage={"last_open_time_ms": None},
        now=datetime(2026, 6, 20, 2, 25, 30, tzinfo=timezone.utc),
    )

    assert plan.mode == "latest"
    assert plan.excluded_open_candle is True
    assert plan.effective_start_open_time_ms == 1781922000000
    assert plan.effective_end_open_time_ms == 1781922240000
    assert plan.expected_candle_count == 5
    assert len(plan.batches) == 1
    assert plan.batches[0].limit == 5


def test_incremental_plan_refetches_overlap_from_existing_coverage() -> None:
    plan = build_fetch_plan(
        _query(),
        coverage={"last_open_time_ms": 1781922000000},
        now=datetime(2026, 6, 20, 2, 25, 30, tzinfo=timezone.utc),
    )

    assert plan.mode == "incremental"
    assert plan.effective_start_open_time_ms == 1781921880000
    assert plan.effective_end_open_time_ms == 1781922240000
    assert plan.expected_candle_count == 7


def test_fill_gaps_plan_uses_existing_coverage_range_without_latest_candle() -> None:
    plan = build_fetch_plan(
        _query(
            mode="fill_gaps",
            batch_limit=2,
        ),
        coverage={
            "first_open_time_ms": 0,
            "last_open_time_ms": 180_000,
        },
        now=datetime(2026, 6, 20, 2, 25, 30, tzinfo=timezone.utc),
    )

    assert plan.mode == "fill_gaps"
    assert plan.effective_start_open_time_ms == 0
    assert plan.effective_end_open_time_ms == 180_000
    assert plan.expected_candle_count == 4
    assert plan.excluded_open_candle is False
    assert len(plan.batches) == 2


def test_backfill_plan_splits_large_range_into_batches() -> None:
    plan = build_fetch_plan(
        _query(
            mode="backfill",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(180_000),
            batch_limit=2,
        ),
        coverage={"last_open_time_ms": None},
        now=datetime(2026, 6, 20, 2, 25, 30, tzinfo=timezone.utc),
    )

    assert plan.mode == "backfill"
    assert plan.expected_candle_count == 4
    assert len(plan.batches) == 2
    assert [batch.limit for batch in plan.batches] == [2, 2]


@pytest.mark.parametrize("mode", ["overwrite_range", "delete_reload"])
def test_range_reload_modes_require_start_and_end_time(mode: str) -> None:
    with pytest.raises(ValueError, match="start_time and end_time"):
        build_fetch_plan(
            _query(mode=mode, start_time=_dt_from_ms(0), end_time=None),
            coverage={"last_open_time_ms": None},
            now=datetime(2026, 6, 20, 2, 25, 30, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("mode", ["overwrite_range", "delete_reload"])
def test_range_reload_modes_use_selected_time_range(mode: str) -> None:
    plan = build_fetch_plan(
        _query(
            mode=mode,
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(180_000),
            batch_limit=2,
        ),
        coverage={"last_open_time_ms": None},
        now=datetime(2026, 6, 20, 2, 25, 30, tzinfo=timezone.utc),
    )

    assert plan.mode == mode
    assert plan.effective_start_open_time_ms == 0
    assert plan.effective_end_open_time_ms == 180_000
    assert plan.expected_candle_count == 4
    assert [batch.limit for batch in plan.batches] == [2, 2]


def test_plan_rejects_range_larger_than_max_batches() -> None:
    with pytest.raises(ValueError, match="max_batches"):
        build_fetch_plan(
            _query(
                mode="backfill",
                start_time=_dt_from_ms(0),
                end_time=_dt_from_ms(240_000),
                batch_limit=2,
                max_batches=2,
            ),
            coverage={"last_open_time_ms": None},
            now=datetime(2026, 6, 20, 2, 25, 30, tzinfo=timezone.utc),
        )
