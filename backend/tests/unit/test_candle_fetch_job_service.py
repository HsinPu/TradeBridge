import pytest
from dataclasses import replace
from datetime import datetime, timezone

from app.application.models.data_gap import DataGap, DataGapCreate, DataGapRepairCommand
from app.application.models.fetch_job import CandleFetchJobCreateCommand
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.domain.entities.candle import Candle
from app.infrastructure.external.kline_mapper import map_provider_kline_to_candle
from app.infrastructure.persistence.sqlite_fetch_job_repository import SQLiteFetchJobRepository


def _dt_from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _copy_gap(gap: DataGap, **changes) -> DataGap:
    return replace(gap, **changes)


class MemoryCandleRepository:
    def __init__(self) -> None:
        self.candles: dict[int, Candle] = {}

    def initialize(self) -> None:
        return None

    def upsert_many(self, candles: list[Candle]) -> int:
        for candle in candles:
            self.candles[candle.open_time_ms] = candle
        return len(candles)

    def replace_range(
        self,
        *,
        provider: str,
        market_type: str,
        market_pair: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        candles: list[Candle],
    ) -> int:
        for open_time_ms in list(self.candles):
            if start_time_ms <= open_time_ms <= end_time_ms:
                del self.candles[open_time_ms]
        return self.upsert_many(candles)

    def list_candles(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        limit: int,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[Candle]:
        candles = [
            candle
            for open_time_ms, candle in sorted(self.candles.items())
            if (start_time_ms is None or open_time_ms >= start_time_ms)
            and (end_time_ms is None or open_time_ms <= end_time_ms)
        ]
        return candles[:limit]

    def coverage(self, *, provider: str, market_pair: str, interval: str) -> dict[str, int | str | None]:
        return {
            "provider": provider,
            "market_pair": market_pair,
            "exchange_symbol": "BTCUSDT",
            "interval": interval,
            "candle_count": len(self.candles),
            "first_open_time_ms": min(self.candles) if self.candles else None,
            "last_open_time_ms": max(self.candles) if self.candles else None,
            "first_open_time": None,
            "last_open_time": None,
            "last_fetched_at": None,
        }

    def list_open_time_ms(
        self,
        *,
        provider: str,
        market_pair: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> list[int]:
        return [
            open_time_ms
            for open_time_ms in sorted(self.candles)
            if start_time_ms <= open_time_ms <= end_time_ms
        ]


class DroppingCandleRepository(MemoryCandleRepository):
    def __init__(self, *, drop_open_time_ms: int) -> None:
        super().__init__()
        self.drop_open_time_ms = drop_open_time_ms

    def upsert_many(self, candles: list[Candle]) -> int:
        stored_candles = [candle for candle in candles if candle.open_time_ms != self.drop_open_time_ms]
        return super().upsert_many(stored_candles)


class MemoryDataGapRepository:
    def __init__(self) -> None:
        self.detected_gaps: list[DataGapCreate] = []
        self.gaps: dict[str, DataGap] = {}

    def initialize(self) -> None:
        return None

    def upsert_detected_many(self, gaps: list[DataGapCreate]):
        self.detected_gaps.extend(gaps)
        for gap in gaps:
            gap_id = f"gap-{len(self.gaps) + 1}"
            self.gaps[gap_id] = DataGap(
                id=gap_id,
                provider=gap.provider,
                market_type=gap.market_type,
                market_pair=gap.market_pair,
                exchange_symbol=gap.exchange_symbol,
                interval=gap.interval,
                start_open_time_ms=gap.start_open_time_ms,
                end_open_time_ms=gap.end_open_time_ms,
                start_open_time=gap.start_open_time,
                end_open_time=gap.end_open_time,
                missing_count=gap.missing_count,
                status=gap.status,
                source_job_id=gap.source_job_id,
                repair_job_id=gap.repair_job_id,
                reason=gap.reason,
                first_detected_at="2026-06-24 13:22:27",
                last_checked_at="2026-06-24 13:22:27",
                resolved_at=None,
                created_at="2026-06-24 13:22:27",
                updated_at="2026-06-24 13:22:27",
            )
        return []

    def add_gap(self, gap: DataGap) -> None:
        self.gaps[gap.id] = gap

    def get_gap(self, gap_id: str) -> DataGap | None:
        return self.gaps.get(gap_id)

    def mark_repairing(self, *, gap_id: str, repair_job_id: str) -> DataGap:
        gap = self.gaps[gap_id]
        updated = _copy_gap(gap, status="repairing", repair_job_id=repair_job_id, resolved_at=None)
        self.gaps[gap_id] = updated
        return updated

    def mark_repair_succeeded(self, *, repair_job_id: str) -> list[DataGap]:
        updated_gaps = []
        for gap_id, gap in list(self.gaps.items()):
            if gap.repair_job_id == repair_job_id and gap.status == "repairing":
                updated = _copy_gap(gap, status="resolved", resolved_at="2026-06-24 13:30:00")
                self.gaps[gap_id] = updated
                updated_gaps.append(updated)
        return updated_gaps

    def mark_repair_failed(self, *, repair_job_id: str, reason: str) -> list[DataGap]:
        updated_gaps = []
        for gap_id, gap in list(self.gaps.items()):
            if gap.repair_job_id == repair_job_id and gap.status == "repairing":
                updated = _copy_gap(gap, status="failed", reason=reason, resolved_at=None)
                self.gaps[gap_id] = updated
                updated_gaps.append(updated)
        return updated_gaps


class StaticProviderResolver:
    def __init__(self, provider) -> None:
        self.provider = provider

    def get(self, provider: str):
        return self.provider


class LimitedMarketDataProvider:
    def __init__(self, *, available_start_ms: int, available_end_ms: int) -> None:
        self.available_start_ms = available_start_ms
        self.available_end_ms = available_end_ms
        self.availability_calls = []
        self.calls = []

    def ping(self) -> bool:
        return True

    def first_available_open_time_ms(self, query) -> int | None:
        self.availability_calls.append(query)
        open_time_ms = max(query.start_time_ms, self.available_start_ms)
        end_time_ms = min(query.end_time_ms, self.available_end_ms)
        return open_time_ms if open_time_ms <= end_time_ms else None

    def fetch_klines(self, query) -> list[Candle]:
        self.calls.append(query)
        candles: list[Candle] = []
        open_time_ms = max(query.start_time_ms, self.available_start_ms)
        end_time_ms = min(query.end_time_ms, self.available_end_ms)
        while open_time_ms <= end_time_ms and len(candles) < query.limit:
            candles.append(_make_candle(open_time_ms))
            open_time_ms += 60_000
        return candles


class GappedMarketDataProvider:
    def __init__(self, *, available_ranges: list[tuple[int, int]]) -> None:
        self.available_ranges = available_ranges
        self.availability_calls = []
        self.calls = []

    def ping(self) -> bool:
        return True

    def first_available_open_time_ms(self, query) -> int | None:
        self.availability_calls.append(query)
        for start_time_ms, end_time_ms in self.available_ranges:
            open_time_ms = max(query.start_time_ms, start_time_ms)
            if open_time_ms <= min(query.end_time_ms, end_time_ms):
                return open_time_ms
        return None

    def fetch_klines(self, query) -> list[Candle]:
        self.calls.append(query)
        candles: list[Candle] = []
        open_time_ms = query.start_time_ms
        while open_time_ms <= query.end_time_ms and len(candles) < query.limit:
            if any(start <= open_time_ms <= end for start, end in self.available_ranges):
                candles.append(_make_candle(open_time_ms))
            open_time_ms += 60_000
        return candles


class SparseMarketDataProvider:
    def __init__(self, *, missing_open_time_ms: int) -> None:
        self.missing_open_time_ms = missing_open_time_ms
        self.availability_calls = []
        self.calls = []

    def ping(self) -> bool:
        return True

    def first_available_open_time_ms(self, query) -> int | None:
        self.availability_calls.append(query)
        return query.start_time_ms if query.start_time_ms <= query.end_time_ms else None

    def fetch_klines(self, query) -> list[Candle]:
        self.calls.append(query)
        candles: list[Candle] = []
        open_time_ms = query.start_time_ms
        while open_time_ms <= query.end_time_ms and len(candles) < query.limit:
            if open_time_ms != self.missing_open_time_ms:
                candles.append(_make_candle(open_time_ms))
            open_time_ms += 60_000
        return candles


class CancellingMarketDataProvider(LimitedMarketDataProvider):
    def __init__(
        self,
        *,
        available_start_ms: int,
        available_end_ms: int,
        fetch_job_repository: SQLiteFetchJobRepository,
        cancel_on_call: int,
    ) -> None:
        super().__init__(available_start_ms=available_start_ms, available_end_ms=available_end_ms)
        self.fetch_job_repository = fetch_job_repository
        self.cancel_on_call = cancel_on_call

    def fetch_klines(self, query) -> list[Candle]:
        candles = super().fetch_klines(query)
        if len(self.calls) == self.cancel_on_call:
            self.fetch_job_repository.mark_cancelled(
                job_id=query.fetch_id,
                error_message="Cancelled by user.",
            )
        return candles


class PausingMarketDataProvider(LimitedMarketDataProvider):
    def __init__(
        self,
        *,
        available_start_ms: int,
        available_end_ms: int,
        fetch_job_repository: SQLiteFetchJobRepository,
        pause_on_call: int,
    ) -> None:
        super().__init__(available_start_ms=available_start_ms, available_end_ms=available_end_ms)
        self.fetch_job_repository = fetch_job_repository
        self.pause_on_call = pause_on_call

    def fetch_klines(self, query) -> list[Candle]:
        candles = super().fetch_klines(query)
        if len(self.calls) == self.pause_on_call:
            self.fetch_job_repository.mark_pause_requested(
                job_id=query.fetch_id,
                error_message="Pause requested by user.",
            )
        return candles


def test_pending_fetch_job_can_be_cancelled_before_running(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=240_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    cancelled_job = service.cancel_job(job.id)
    skipped_job = service.run_job(job.id)

    assert cancelled_job.status == "cancelled"
    assert cancelled_job.finished_at is not None
    assert "Cancelled by user." in (cancelled_job.error_message or "")
    assert skipped_job.status == "cancelled"
    assert provider.calls == []
    assert candle_repository.candles == {}


def test_pending_fetch_job_can_be_paused_before_running_and_resumed(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=120_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(120_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    paused_job = service.pause_job(job.id)
    skipped_job = service.run_job(job.id)
    resumed_job = service.resume_job(job.id)
    completed_job = service.run_job(job.id)

    assert paused_job.status == "paused"
    assert paused_job.finished_at is not None
    assert skipped_job.status == "paused"
    assert resumed_job.status == "pending"
    assert completed_job.status == "success"
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000]
    assert [call.start_time_ms for call in provider.availability_calls] == [0]
    assert [call.start_time_ms for call in provider.calls] == [0, 120_000]


def test_pausing_fetch_job_cannot_resume_before_pause_checkpoint(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=120_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(120_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )
    fetch_job_repository.mark_running(job.id)

    pausing_job = service.pause_job(job.id)
    with pytest.raises(ValueError, match="Only paused fetch jobs"):
        service.resume_job(job.id)
    assert pausing_job.status == "pausing"
    assert service.get_job(job.id).status == "pausing"


def test_running_fetch_job_stops_when_cancelled_between_batches(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = CancellingMarketDataProvider(
        available_start_ms=0,
        available_end_ms=240_000,
        fetch_job_repository=fetch_job_repository,
        cancel_on_call=1,
    )
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "cancelled"
    assert completed_job.finished_at is not None
    assert sorted(candle_repository.candles) == []
    assert [call.start_time_ms for call in provider.availability_calls] == [0]
    assert [call.start_time_ms for call in provider.calls] == [0]


def test_running_fetch_job_pauses_and_resumes_from_cursor(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = PausingMarketDataProvider(
        available_start_ms=0,
        available_end_ms=240_000,
        fetch_job_repository=fetch_job_repository,
        pause_on_call=2,
    )
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    paused_job = service.run_job(job.id)
    paused_candle_open_times = sorted(candle_repository.candles)
    resumed_job = service.resume_job(job.id)
    completed_job = service.run_job(job.id)

    assert paused_job.status == "paused"
    assert paused_job.current_cursor_time_ms == 120_000
    assert paused_candle_open_times == [0, 60_000]
    assert resumed_job.status == "pending"
    assert completed_job.status == "success"
    assert completed_job.total_estimated_count == 5
    assert completed_job.total_batch_count == 3
    assert completed_job.completed_batch_count == 3
    assert completed_job.fetched_count == 5
    assert completed_job.saved_count == 5
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000, 180_000, 240_000]
    assert [call.start_time_ms for call in provider.availability_calls] == [0, 0]
    assert [call.start_time_ms for call in provider.calls] == [0, 120_000, 120_000, 240_000]


def test_manual_fetch_job_discovers_provider_start_and_runs_until_end(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=120_000, available_end_ms=360_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(360_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.effective_start_time_ms == 120_000
    assert completed_job.effective_end_time_ms == 360_000
    assert completed_job.total_estimated_count == 5
    assert completed_job.total_batch_count == 3
    assert completed_job.completed_batch_count == 3
    assert completed_job.fetched_count == 5
    assert completed_job.saved_count == 5
    assert completed_job.progress_percent == 100
    assert sorted(candle_repository.candles) == [120_000, 180_000, 240_000, 300_000, 360_000]
    assert [call.start_time_ms for call in provider.availability_calls] == [0]
    assert [call.limit for call in provider.calls] == [2, 2, 1]
    assert [call.start_time_ms for call in provider.calls] == [120_000, 240_000, 360_000]


def test_manual_fetch_job_succeeds_with_zero_rows_when_provider_has_no_data(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=600_000, available_end_ms=900_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )
    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(300_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.fetched_count == 0
    assert completed_job.saved_count == 0
    assert completed_job.total_estimated_count == 0
    assert completed_job.progress_percent == 100
    assert candle_repository.candles == {}


def test_manual_fetch_job_overlaps_between_batches(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=240_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="backfill",
            closed_only=False,
            batch_limit=3,
            overlap_candles=1,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.overlap_candles == 1
    assert completed_job.total_estimated_count == 5
    assert completed_job.total_batch_count == 2
    assert completed_job.completed_batch_count == 2
    assert completed_job.fetched_count == 6
    assert completed_job.saved_count == 6
    assert completed_job.missing_count == 0
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000, 180_000, 240_000]
    assert [call.start_time_ms for call in provider.availability_calls] == [0]
    assert [call.limit for call in provider.calls] == [3, 3]
    assert [call.start_time_ms for call in provider.calls] == [0, 120_000]


def test_manual_fetch_job_keeps_moving_when_overlap_exceeds_batch_size(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=180_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(180_000),
            mode="backfill",
            closed_only=False,
            batch_limit=2,
            overlap_candles=20,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.total_estimated_count == 4
    assert completed_job.total_batch_count == 3
    assert completed_job.completed_batch_count == 3
    assert completed_job.missing_count == 0
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000, 180_000]
    assert [call.start_time_ms for call in provider.availability_calls] == [0]
    assert [call.start_time_ms for call in provider.calls] == [0, 60_000, 120_000]


def test_fill_gaps_job_fetches_only_missing_range_with_overlap(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    candle_repository.upsert_many(
        [_make_candle(open_time_ms) for open_time_ms in [0, 60_000, 180_000, 240_000]]
    )
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=240_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="fill_gaps",
            closed_only=False,
            batch_limit=10,
            overlap_candles=1,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.mode == "fill_gaps"
    assert completed_job.total_estimated_count == 3
    assert completed_job.total_batch_count == 1
    assert completed_job.completed_batch_count == 1
    assert completed_job.fetched_count == 3
    assert completed_job.missing_count == 0
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000, 180_000, 240_000]
    assert [call.start_time_ms for call in provider.availability_calls] == [0]
    assert [call.limit for call in provider.calls] == [3]
    assert [call.start_time_ms for call in provider.calls] == [60_000]
    assert provider.calls[0].end_time_ms == 239_999


def test_fill_gaps_job_does_not_call_provider_when_no_gap_exists(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    candle_repository.upsert_many(
        [_make_candle(open_time_ms) for open_time_ms in [0, 60_000, 120_000, 180_000, 240_000]]
    )
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=240_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="fill_gaps",
            closed_only=False,
            batch_limit=10,
            overlap_candles=1,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.total_estimated_count == 0
    assert completed_job.total_batch_count == 0
    assert completed_job.completed_batch_count == 0
    assert completed_job.fetched_count == 0
    assert completed_job.saved_count == 0
    assert completed_job.progress_percent == 100
    assert provider.calls == []
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000, 180_000, 240_000]


def test_data_gap_repair_job_marks_gap_resolved_when_fetch_succeeds(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    candle_repository.upsert_many([_make_candle(open_time_ms) for open_time_ms in [0, 60_000, 180_000, 240_000]])
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    data_gap_repository = MemoryDataGapRepository()
    data_gap_repository.add_gap(_make_gap_model(start_open_time_ms=120_000, end_open_time_ms=120_000))
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=240_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        data_gap_repository=data_gap_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    result = service.create_data_gap_repair_job(
        DataGapRepairCommand(
            gap_id="gap-1",
            batch_limit=10,
            overlap_candles=0,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )
    completed_job = service.run_job(result.job.id)

    repaired_gap = data_gap_repository.get_gap("gap-1")
    assert result.should_start_job is True
    assert result.gap.status == "repairing"
    assert result.job.mode == "fill_gaps"
    assert result.job.trigger_type == "data_gap_repair"
    assert completed_job.status == "success"
    assert repaired_gap is not None
    assert repaired_gap.status == "resolved"
    assert repaired_gap.repair_job_id == result.job.id
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000, 180_000, 240_000]


def test_data_gap_repair_job_marks_gap_failed_when_fetch_fails(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    data_gap_repository = MemoryDataGapRepository()
    data_gap_repository.add_gap(_make_gap_model(start_open_time_ms=120_000, end_open_time_ms=120_000))
    provider = LimitedMarketDataProvider(available_start_ms=300_000, available_end_ms=360_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        data_gap_repository=data_gap_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    result = service.create_data_gap_repair_job(
        DataGapRepairCommand(
            gap_id="gap-1",
            batch_limit=10,
            overlap_candles=0,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )
    completed_job = service.run_job(result.job.id)

    repaired_gap = data_gap_repository.get_gap("gap-1")
    assert completed_job.status == "failed"
    assert repaired_gap is not None
    assert repaired_gap.status == "failed"
    assert "no provider data" in (repaired_gap.reason or "")


def test_manual_fetch_job_skips_provider_unavailable_gap_and_continues(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = GappedMarketDataProvider(
        available_ranges=[
            (0, 120_000),
            (300_000, 540_000),
        ]
    )
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(540_000),
            mode="backfill",
            closed_only=False,
            batch_limit=6,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.missing_count == 0
    assert completed_job.progress_percent == 100
    assert sorted(candle_repository.candles) == [
        0,
        60_000,
        120_000,
        300_000,
        360_000,
        420_000,
        480_000,
        540_000,
    ]
    assert [call.start_time_ms for call in provider.calls] == [0, 360_000]


def test_fill_gaps_job_skips_provider_unavailable_gap(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    candle_repository.upsert_many(
        [_make_candle(open_time_ms) for open_time_ms in [0, 60_000, 120_000, 300_000, 360_000]]
    )
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = GappedMarketDataProvider(
        available_ranges=[
            (0, 120_000),
            (300_000, 360_000),
        ]
    )
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(360_000),
            mode="fill_gaps",
            closed_only=False,
            batch_limit=10,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "success"
    assert completed_job.fetched_count == 0
    assert completed_job.saved_count == 0
    assert completed_job.missing_count == 0
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000, 300_000, 360_000]


def test_manual_fetch_job_fails_when_stored_range_has_gap(tmp_path) -> None:
    candle_repository = DroppingCandleRepository(drop_open_time_ms=120_000)
    data_gap_repository = MemoryDataGapRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=240_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
        data_gap_repository=data_gap_repository,
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="backfill",
            closed_only=False,
            batch_limit=5,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "failed"
    assert completed_job.missing_count == 1
    assert completed_job.progress_percent < 100
    assert "missing_count=1" in (completed_job.error_message or "")
    assert sorted(candle_repository.candles) == [0, 60_000, 180_000, 240_000]
    assert len(data_gap_repository.detected_gaps) == 1
    assert data_gap_repository.detected_gaps[0].source_job_id == job.id
    assert data_gap_repository.detected_gaps[0].start_open_time_ms == 120_000
    assert data_gap_repository.detected_gaps[0].end_open_time_ms == 120_000
    assert data_gap_repository.detected_gaps[0].missing_count == 1


def test_manual_fetch_job_fails_when_provider_stops_before_requested_end(tmp_path) -> None:
    candle_repository = MemoryCandleRepository()
    fetch_job_repository = SQLiteFetchJobRepository(str(tmp_path / "tradebridge.db"))
    fetch_job_repository.initialize()
    provider = LimitedMarketDataProvider(available_start_ms=0, available_end_ms=120_000)
    service = CandleFetchJobService(
        candle_repository=candle_repository,
        fetch_job_repository=fetch_job_repository,
        provider_resolver=StaticProviderResolver(provider),
    )

    job = service.create_manual_backfill_job(
        CandleFetchJobCreateCommand(
            provider="binance",
            market_type="spot",
            market_pair="BTC/USDT",
            interval="1m",
            start_time=_dt_from_ms(0),
            end_time=_dt_from_ms(240_000),
            mode="backfill",
            closed_only=False,
            batch_limit=5,
            overlap_candles=0,
            verify_continuity=True,
            retry_attempts=0,
            retry_delay_seconds=0,
        )
    )

    completed_job = service.run_job(job.id)

    assert completed_job.status == "failed"
    assert completed_job.missing_count == 2
    assert completed_job.progress_percent < 100
    assert "first_missing_open_time=1970-01-01T00:03:00+00:00" in (completed_job.error_message or "")
    assert sorted(candle_repository.candles) == [0, 60_000, 120_000]


def _make_candle(open_time_ms: int) -> Candle:
    return map_provider_kline_to_candle(
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        interval="1m",
        payload=[
            open_time_ms,
            "1.0",
            "2.0",
            "0.5",
            "1.5",
            "10.0",
            open_time_ms + 59_999,
            "15.0",
            3,
            "4.0",
            "6.0",
            "0",
        ],
    )


def _make_gap_model(*, start_open_time_ms: int, end_open_time_ms: int) -> DataGap:
    return DataGap(
        id="gap-1",
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        start_open_time_ms=start_open_time_ms,
        end_open_time_ms=end_open_time_ms,
        start_open_time=f"1970-01-01T00:{start_open_time_ms // 60_000:02d}:00+00:00",
        end_open_time=f"1970-01-01T00:{end_open_time_ms // 60_000:02d}:00+00:00",
        missing_count=((end_open_time_ms - start_open_time_ms) // 60_000) + 1,
        status="detected",
        source_job_id="source-job-1",
        repair_job_id=None,
        reason="fetch_job_continuity_check",
        first_detected_at="2026-06-24 13:22:27",
        last_checked_at="2026-06-24 13:22:27",
        resolved_at=None,
        created_at="2026-06-24 13:22:27",
        updated_at="2026-06-24 13:22:27",
    )
