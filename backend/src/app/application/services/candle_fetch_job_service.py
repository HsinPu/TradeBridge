import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from time import perf_counter
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.models.candle_query import CandleAvailabilityQuery, CandleBatchQuery
from app.application.models.data_gap import DataGap, DataGapCreate, DataGapRepairCommand
from app.application.models.fetch_job import (
    CandleFetchJob,
    CandleFetchJobCreateCommand,
    CandleFetchJobOverview,
    CandleFetchJobSummary,
)
from app.application.ports.candle_repository import CandleRepository
from app.application.ports.data_gap_repository import DataGapRepository
from app.application.ports.fetch_job_repository import FetchJobRepository
from app.application.ports.market_data_provider import MarketDataProvider, MarketDataProviderResolver
from app.application.services.candle_fetch_planner import datetime_to_ms, ms_to_iso
from app.domain.entities.candle import Candle
from app.domain.value_objects.candle_interval import CandleInterval
from app.domain.value_objects.market_pair import MarketPair
from app.domain.value_objects.provider import normalize_provider

logger = logging.getLogger(__name__)

CANCELLED_BY_USER_MESSAGE = "Cancelled by user."
PAUSE_REQUESTED_BY_USER_MESSAGE = "Pause requested by user."
PAUSED_BY_USER_MESSAGE = "Paused by user."
FIXED_TIMEZONE_OFFSETS = {
    "Asia/Taipei": timedelta(hours=8),
    "Asia/Shanghai": timedelta(hours=8),
    "Asia/Hong_Kong": timedelta(hours=8),
    "Asia/Singapore": timedelta(hours=8),
    "Asia/Tokyo": timedelta(hours=9),
    "Asia/Seoul": timedelta(hours=9),
}


@dataclass(frozen=True)
class OpenTimeRange:
    start_open_time_ms: int
    end_open_time_ms: int


@dataclass(frozen=True)
class DataGapRepairResult:
    gap: DataGap
    job: CandleFetchJob
    should_start_job: bool


class CandleFetchJobService:
    def __init__(
        self,
        *,
        candle_repository: CandleRepository,
        fetch_job_repository: FetchJobRepository,
        provider_resolver: MarketDataProviderResolver,
        data_gap_repository: DataGapRepository | None = None,
    ) -> None:
        self._candle_repository = candle_repository
        self._fetch_job_repository = fetch_job_repository
        self._provider_resolver = provider_resolver
        self._data_gap_repository = data_gap_repository

    def create_manual_backfill_job(self, command: CandleFetchJobCreateCommand) -> CandleFetchJob:
        return self.create_fetch_job(
            CandleFetchJobCreateCommand(
                provider=command.provider,
                market_type=command.market_type,
                market_pair=command.market_pair,
                interval=command.interval,
                start_time=command.start_time,
                end_time=command.end_time,
                mode=command.mode,
                closed_only=command.closed_only,
                batch_limit=command.batch_limit,
                overlap_candles=command.overlap_candles,
                verify_continuity=command.verify_continuity,
                retry_attempts=command.retry_attempts,
                retry_delay_seconds=command.retry_delay_seconds,
                schedule_id=None,
                trigger_type="manual",
            )
        )

    def create_scheduled_backfill_job(self, command: CandleFetchJobCreateCommand) -> CandleFetchJob:
        if command.schedule_id is None:
            raise ValueError("schedule_id is required for scheduled fetch jobs.")
        return self.create_fetch_job(command)

    def create_data_gap_repair_job(self, command: DataGapRepairCommand) -> DataGapRepairResult:
        if self._data_gap_repository is None:
            raise ValueError("Data gap repository is required to repair data gaps.")

        gap = self._data_gap_repository.get_gap(command.gap_id)
        if gap is None:
            raise ValueError(f"Data gap not found: {command.gap_id}")
        if gap.status in {"resolved", "official_empty"}:
            raise ValueError(f"Data gap cannot be repaired from status: {gap.status}.")
        if gap.status == "repairing" and gap.repair_job_id:
            existing_job = self._fetch_job_repository.get(gap.repair_job_id)
            if existing_job is not None and existing_job.status in {"pending", "running", "pausing", "paused"}:
                return DataGapRepairResult(gap=gap, job=existing_job, should_start_job=False)

        job = self.create_fetch_job(
            CandleFetchJobCreateCommand(
                provider=gap.provider,
                market_type=gap.market_type,
                market_pair=gap.market_pair,
                interval=gap.interval,
                start_time=_datetime_from_ms(gap.start_open_time_ms),
                end_time=_datetime_from_ms(gap.end_open_time_ms),
                mode="fill_gaps",
                closed_only=True,
                batch_limit=command.batch_limit,
                overlap_candles=command.overlap_candles,
                verify_continuity=command.verify_continuity,
                retry_attempts=command.retry_attempts,
                retry_delay_seconds=command.retry_delay_seconds,
                schedule_id=None,
                trigger_type="data_gap_repair",
            )
        )
        updated_gap = self._data_gap_repository.mark_repairing(gap_id=gap.id, repair_job_id=job.id)
        logger.info(
            "data gap repair job created gap_id=%s repair_job_id=%s provider=%s market_pair=%s interval=%s missing_count=%s",
            gap.id,
            job.id,
            gap.provider,
            gap.market_pair,
            gap.interval,
            gap.missing_count,
        )
        return DataGapRepairResult(gap=updated_gap, job=job, should_start_job=True)

    def create_fetch_job(self, command: CandleFetchJobCreateCommand) -> CandleFetchJob:
        interval = CandleInterval.parse(command.interval)
        pair = MarketPair.parse(command.market_pair)
        requested_start_time_ms = datetime_to_ms(command.start_time)
        requested_end_time_ms = datetime_to_ms(command.end_time)
        if requested_start_time_ms is None:
            raise ValueError("start_time is required for manual backfill jobs.")

        now_ms = datetime_to_ms(datetime.now(timezone.utc))
        if now_ms is None:
            raise ValueError("Unable to resolve current time.")
        current_open_time_ms = interval.floor_open_time_ms(now_ms)
        last_closed_open_time_ms = max(0, current_open_time_ms - interval.milliseconds)
        last_closed_end_time_ms = last_closed_open_time_ms + interval.milliseconds - 1
        effective_end_time_ms = requested_end_time_ms if requested_end_time_ms is not None else now_ms
        if command.closed_only:
            effective_end_time_ms = min(effective_end_time_ms, last_closed_end_time_ms)

        requested_start_open_time_ms = interval.floor_open_time_ms(requested_start_time_ms)
        effective_end_open_time_ms = interval.floor_open_time_ms(effective_end_time_ms)
        if requested_start_open_time_ms > effective_end_open_time_ms:
            raise ValueError("Fetch job range has no complete candles.")

        estimated_count = _count_expected_candles(
            start_open_time_ms=requested_start_open_time_ms,
            end_open_time_ms=effective_end_open_time_ms,
            interval_ms=interval.milliseconds,
        )
        created_at = _utcnow_iso()
        job = CandleFetchJob(
            id=uuid4().hex[:12],
            job_type="manual_backfill",
            status="pending",
            schedule_id=command.schedule_id,
            trigger_type=command.trigger_type,
            provider=command.provider,
            market_type=command.market_type,
            market_pair=pair.display,
            exchange_symbol=pair.exchange_symbol_for(command.provider),
            interval=command.interval,
            mode=_resolve_job_mode(command.mode),
            requested_start_time_ms=requested_start_open_time_ms,
            requested_end_time_ms=requested_end_time_ms,
            effective_start_time_ms=None,
            effective_end_time_ms=effective_end_time_ms,
            current_cursor_time_ms=requested_start_open_time_ms,
            batch_limit=command.batch_limit,
            overlap_candles=command.overlap_candles,
            total_estimated_count=estimated_count,
            fetched_count=0,
            saved_count=0,
            failed_count=0,
            missing_count=0,
            completed_batch_count=0,
            total_batch_count=_count_batches_with_overlap(
                total_estimated_count=estimated_count,
                batch_limit=command.batch_limit,
                overlap_candles=command.overlap_candles,
            ),
            progress_percent=0,
            closed_only=command.closed_only,
            verify_continuity=command.verify_continuity,
            retry_attempts=command.retry_attempts,
            retry_delay_seconds=command.retry_delay_seconds,
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=created_at,
            updated_at=created_at,
        )
        created_job = self._fetch_job_repository.create(job)
        logger.info(
            "fetch job created job_id=%s type=%s trigger_type=%s schedule_id=%s mode=%s provider=%s market_type=%s market_pair=%s interval=%s requested_start_time_ms=%s requested_end_time_ms=%s effective_end_time_ms=%s batch_limit=%s overlap_candles=%s estimated_count=%s total_batch_count=%s closed_only=%s verify_continuity=%s",
            created_job.id,
            created_job.job_type,
            created_job.trigger_type,
            created_job.schedule_id,
            created_job.mode,
            created_job.provider,
            created_job.market_type,
            created_job.market_pair,
            created_job.interval,
            created_job.requested_start_time_ms,
            created_job.requested_end_time_ms,
            created_job.effective_end_time_ms,
            created_job.batch_limit,
            created_job.overlap_candles,
            created_job.total_estimated_count,
            created_job.total_batch_count,
            created_job.closed_only,
            created_job.verify_continuity,
        )
        return created_job

    def get_job(self, job_id: str) -> CandleFetchJob:
        job = self._fetch_job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Fetch job not found: {job_id}")
        return job

    def list_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CandleFetchJob]:
        selected_provider = normalize_provider(provider) if provider else None
        self._validate_status_filter(status)
        return self._fetch_job_repository.list_jobs(
            provider=selected_provider,
            status=status,
            schedule_id=schedule_id,
            market_pair=market_pair,
            interval=interval,
            search=search,
            limit=limit,
            offset=offset,
        )

    def count_jobs(
        self,
        *,
        provider: str | None = None,
        status: list[str] | None = None,
        schedule_id: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        finished_at_from_ms: int | None = None,
        finished_at_to_ms: int | None = None,
    ) -> int:
        selected_provider = normalize_provider(provider) if provider else None
        self._validate_status_filter(status)
        return self._fetch_job_repository.count_jobs(
            provider=selected_provider,
            status=status,
            schedule_id=schedule_id,
            market_pair=market_pair,
            interval=interval,
            search=search,
            finished_at_from_ms=finished_at_from_ms,
            finished_at_to_ms=finished_at_to_ms,
        )

    def summarize_jobs(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        timezone_name: str = "UTC",
    ) -> CandleFetchJobSummary:
        selected_provider = normalize_provider(provider) if provider else None
        selected_timezone, resolved_timezone_name = _resolve_timezone(timezone_name)
        now = datetime.now(timezone.utc).astimezone(selected_timezone)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_start_ms = _require_datetime_ms(today_start.astimezone(timezone.utc))
        today_end_ms = _require_datetime_ms(today_end.astimezone(timezone.utc))
        common_filters = {
            "provider": selected_provider,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
        }
        return CandleFetchJobSummary(
            total_count=self._fetch_job_repository.count_jobs(**common_filters),
            running_count=self._fetch_job_repository.count_jobs(**common_filters, status=["running"]),
            queued_count=self._fetch_job_repository.count_jobs(**common_filters, status=["pending"]),
            completed_today_count=self._fetch_job_repository.count_jobs(
                **common_filters,
                status=["success"],
                finished_at_from_ms=today_start_ms,
                finished_at_to_ms=today_end_ms,
            ),
            failed_count=self._fetch_job_repository.count_jobs(**common_filters, status=["failed"]),
            timezone=resolved_timezone_name,
            today_start_time_ms=today_start_ms,
            today_end_time_ms=today_end_ms,
        )

    def get_jobs_overview(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        recent_limit: int = 8,
    ) -> CandleFetchJobOverview:
        selected_provider = normalize_provider(provider) if provider else None
        common_filters = {
            "provider": selected_provider,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
        }
        failed_jobs = self._fetch_job_repository.list_jobs(
            **common_filters,
            status=["failed"],
            limit=1,
            offset=0,
        )
        return CandleFetchJobOverview(
            recent_jobs=self._fetch_job_repository.list_jobs(
                **common_filters,
                limit=recent_limit,
                offset=0,
            ),
            latest_failed_job=failed_jobs[0] if failed_jobs else None,
            failed_count=self._fetch_job_repository.count_jobs(**common_filters, status=["failed"]),
        )

    def _validate_status_filter(self, status: list[str] | None) -> None:
        valid_statuses = {"pending", "running", "pausing", "paused", "success", "failed", "cancelled"}
        if status:
            invalid = sorted(set(status) - valid_statuses)
            if invalid:
                raise ValueError(f"Unsupported fetch job status: {', '.join(invalid)}.")

    def cancel_job(self, job_id: str) -> CandleFetchJob:
        job = self.get_job(job_id)
        if job.status not in {"pending", "running", "pausing", "paused"}:
            raise ValueError(
                "Only pending, running, pausing, or paused fetch jobs can be cancelled. "
                f"Current status: {job.status}."
            )

        cancelled_job = self._fetch_job_repository.mark_cancelled(
            job_id=job.id,
            error_message=CANCELLED_BY_USER_MESSAGE,
        )
        logger.info("fetch job cancelled job_id=%s previous_status=%s", job.id, job.status)
        return cancelled_job

    def pause_job(self, job_id: str) -> CandleFetchJob:
        job = self.get_job(job_id)
        if job.status == "paused":
            return job
        if job.status == "pausing":
            return job
        if job.status == "pending":
            paused_job = self._fetch_job_repository.mark_paused(
                job_id=job.id,
                error_message=PAUSED_BY_USER_MESSAGE,
            )
            logger.info("fetch job paused job_id=%s previous_status=%s", job.id, job.status)
            return paused_job
        if job.status == "running":
            pausing_job = self._fetch_job_repository.mark_pause_requested(
                job_id=job.id,
                error_message=PAUSE_REQUESTED_BY_USER_MESSAGE,
            )
            logger.info("fetch job pause requested job_id=%s previous_status=%s", job.id, job.status)
            return pausing_job
        raise ValueError(f"Only pending or running fetch jobs can be paused. Current status: {job.status}.")

    def resume_job(self, job_id: str) -> CandleFetchJob:
        job = self.get_job(job_id)
        if job.status not in {"paused", "pausing"}:
            raise ValueError(f"Only paused or pausing fetch jobs can be resumed. Current status: {job.status}.")

        resumed_job = self._fetch_job_repository.mark_pending(job_id=job.id, error_message=None)
        logger.info("fetch job resumed job_id=%s previous_status=%s", job.id, job.status)
        return resumed_job

    def run_job(self, job_id: str) -> CandleFetchJob:
        job = self.get_job(job_id)
        if job.status not in {"pending", "running"}:
            logger.info("fetch job run skipped job_id=%s status=%s", job.id, job.status)
            self._sync_data_gap_repair_status(job)
            return job

        started_at = perf_counter()
        job = self._fetch_job_repository.mark_running(job.id)
        controlled_job = self._get_controlled_job(job.id)
        if controlled_job is not None:
            logger.info("fetch job run stopped before start job_id=%s status=%s", job.id, job.status)
            self._sync_data_gap_repair_status(controlled_job)
            return controlled_job
        logger.info(
            "fetch job started job_id=%s mode=%s market_pair=%s interval=%s requested_start_time_ms=%s effective_end_time_ms=%s batch_limit=%s overlap_candles=%s",
            job.id,
            job.mode,
            job.market_pair,
            job.interval,
            job.requested_start_time_ms,
            job.effective_end_time_ms,
            job.batch_limit,
            job.overlap_candles,
        )

        try:
            completed_job = self._run_manual_backfill(job)
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.info(
                "fetch job completed job_id=%s status=%s fetched_count=%s saved_count=%s missing_count=%s completed_batch_count=%s total_batch_count=%s duration_ms=%s",
                completed_job.id,
                completed_job.status,
                completed_job.fetched_count,
                completed_job.saved_count,
                completed_job.missing_count,
                completed_job.completed_batch_count,
                completed_job.total_batch_count,
                duration_ms,
            )
            self._sync_data_gap_repair_status(completed_job)
            return completed_job
        except Exception as exc:
            failed_job = self._fetch_job_repository.mark_failed(job_id=job.id, error_message=str(exc))
            self._sync_data_gap_repair_status(failed_job)
            logger.exception(
                "fetch job failed job_id=%s status=%s fetched_count=%s saved_count=%s completed_batch_count=%s duration_ms=%s",
                failed_job.id,
                failed_job.status,
                failed_job.fetched_count,
                failed_job.saved_count,
                failed_job.completed_batch_count,
                int((perf_counter() - started_at) * 1000),
            )
            return failed_job

    def _sync_data_gap_repair_status(self, job: CandleFetchJob) -> None:
        if self._data_gap_repository is None or job.trigger_type != "data_gap_repair":
            return
        if job.status == "success":
            repaired_gaps = self._data_gap_repository.mark_repair_succeeded(repair_job_id=job.id)
            logger.info("data gap repair succeeded job_id=%s repaired_gap_count=%s", job.id, len(repaired_gaps))
            return
        if job.status in {"failed", "cancelled"}:
            reason = job.error_message or f"Repair job ended with status: {job.status}."
            repaired_gaps = self._data_gap_repository.mark_repair_failed(repair_job_id=job.id, reason=reason)
            logger.info("data gap repair failed job_id=%s repaired_gap_count=%s", job.id, len(repaired_gaps))

    def _get_controlled_job(self, job_id: str) -> CandleFetchJob | None:
        job = self._fetch_job_repository.get(job_id)
        if job is None:
            return None
        if job.status == "cancelled":
            logger.info("fetch job cancellation observed job_id=%s", job_id)
            return job
        if job.status == "pausing":
            paused_job = self._fetch_job_repository.mark_paused(
                job_id=job.id,
                error_message=PAUSED_BY_USER_MESSAGE,
            )
            logger.info("fetch job pause observed job_id=%s", job_id)
            return paused_job
        if job.status == "paused":
            logger.info("fetch job paused state observed job_id=%s", job_id)
            return job
        return None

    def _run_manual_backfill(self, job: CandleFetchJob) -> CandleFetchJob:
        interval = CandleInterval.parse(job.interval)
        provider = self._provider_resolver.get(job.provider)
        effective_end_open_time_ms = interval.floor_open_time_ms(job.effective_end_time_ms)
        controlled_job = self._get_controlled_job(job.id)
        if controlled_job is not None:
            return controlled_job

        requested_missing_ranges: list[OpenTimeRange] | None = None
        if job.mode == "fill_gaps":
            requested_missing_ranges = _find_repository_missing_ranges(
                repository=self._candle_repository,
                provider=job.provider,
                market_pair=job.market_pair,
                interval=job.interval,
                start_open_time_ms=job.requested_start_time_ms,
                end_open_time_ms=effective_end_open_time_ms,
                interval_ms=interval.milliseconds,
            )
            if not requested_missing_ranges:
                logger.info(
                    "fetch job fill_gaps found no missing candles job_id=%s requested_start_time_ms=%s effective_end_open_time_ms=%s",
                    job.id,
                    job.requested_start_time_ms,
                    effective_end_open_time_ms,
                )
                job = self._fetch_job_repository.update_progress(
                    job_id=job.id,
                    effective_start_time_ms=job.requested_start_time_ms,
                    current_cursor_time_ms=effective_end_open_time_ms + interval.milliseconds,
                    total_estimated_count=0,
                    fetched_count=job.fetched_count,
                    saved_count=job.saved_count,
                    failed_count=job.failed_count,
                    missing_count=0,
                    completed_batch_count=job.completed_batch_count,
                    total_batch_count=0,
                    progress_percent=100,
                )
                return self._fetch_job_repository.mark_succeeded(job.id)

        provider_start_open_time_ms = self._resolve_provider_start_open_time_ms(
            job=job,
            provider=provider,
            interval=interval,
            effective_end_open_time_ms=effective_end_open_time_ms,
        )
        controlled_job = self._get_controlled_job(job.id)
        if controlled_job is not None:
            return controlled_job
        if provider_start_open_time_ms is None:
            logger.info(
                "fetch job has no provider data job_id=%s requested_start_time_ms=%s effective_end_time_ms=%s",
                job.id,
                job.requested_start_time_ms,
                job.effective_end_time_ms,
            )
            if job.mode == "fill_gaps":
                missing_count = _count_open_time_ranges(
                    ranges=requested_missing_ranges or [],
                    interval_ms=interval.milliseconds,
                )
                first_missing_open_time_ms = (
                    requested_missing_ranges[0].start_open_time_ms
                    if requested_missing_ranges
                    else None
                )
                self._fetch_job_repository.update_progress(
                    job_id=job.id,
                    effective_start_time_ms=None,
                    current_cursor_time_ms=effective_end_open_time_ms + interval.milliseconds,
                    total_estimated_count=missing_count,
                    fetched_count=job.fetched_count,
                    saved_count=job.saved_count,
                    failed_count=job.failed_count,
                    missing_count=missing_count,
                    completed_batch_count=job.completed_batch_count,
                    total_batch_count=0,
                    progress_percent=0,
                )
                raise ValueError(
                    "Fetch job has no provider data for missing ranges. "
                    f"missing_count={missing_count}, "
                    f"first_missing_open_time={ms_to_iso(first_missing_open_time_ms)}"
                )
            job = self._fetch_job_repository.update_progress(
                job_id=job.id,
                effective_start_time_ms=None,
                current_cursor_time_ms=effective_end_open_time_ms + interval.milliseconds,
                total_estimated_count=0,
                fetched_count=0,
                saved_count=0,
                failed_count=0,
                missing_count=0,
                completed_batch_count=0,
                total_batch_count=0,
                progress_percent=100,
            )
            return self._fetch_job_repository.mark_succeeded(job.id)

        effective_start_time_ms = provider_start_open_time_ms
        if effective_start_time_ms > job.requested_start_time_ms:
            skipped_count = _count_expected_candles(
                start_open_time_ms=job.requested_start_time_ms,
                end_open_time_ms=effective_start_time_ms - interval.milliseconds,
                interval_ms=interval.milliseconds,
            )
            logger.info(
                "fetch job skipped provider unavailable prefix job_id=%s requested_start_time_ms=%s provider_start_open_time_ms=%s skipped_count=%s",
                job.id,
                job.requested_start_time_ms,
                effective_start_time_ms,
                skipped_count,
            )
        if job.mode == "fill_gaps":
            missing_ranges = _find_repository_missing_ranges(
                repository=self._candle_repository,
                provider=job.provider,
                market_pair=job.market_pair,
                interval=job.interval,
                start_open_time_ms=effective_start_time_ms,
                end_open_time_ms=effective_end_open_time_ms,
                interval_ms=interval.milliseconds,
            )
            fetch_ranges = _expand_ranges_with_overlap(
                ranges=missing_ranges,
                lower_bound_open_time_ms=effective_start_time_ms,
                upper_bound_open_time_ms=effective_end_open_time_ms,
                interval_ms=interval.milliseconds,
                overlap_candles=job.overlap_candles,
            )
        else:
            fetch_ranges = [
                OpenTimeRange(
                    start_open_time_ms=effective_start_time_ms,
                    end_open_time_ms=effective_end_open_time_ms,
                )
            ]

        full_total_estimated_count = _count_open_time_ranges(
            ranges=fetch_ranges,
            interval_ms=interval.milliseconds,
        )
        resume_cursor_time_ms = _resolve_resume_cursor(
            job=job,
            effective_start_time_ms=effective_start_time_ms,
            effective_end_open_time_ms=effective_end_open_time_ms,
            interval_ms=interval.milliseconds,
        )
        is_resuming = resume_cursor_time_ms is not None
        if resume_cursor_time_ms is not None:
            fetch_ranges = _trim_open_time_ranges_from_cursor(
                ranges=fetch_ranges,
                cursor_open_time_ms=resume_cursor_time_ms,
            )
        remaining_batch_count = _count_batches_for_ranges(
            ranges=fetch_ranges,
            interval_ms=interval.milliseconds,
            batch_limit=job.batch_limit,
            overlap_candles=job.overlap_candles,
        )
        total_estimated_count = (
            job.total_estimated_count
            if is_resuming and job.total_estimated_count > 0
            else full_total_estimated_count
        )
        total_batch_count = (
            max(job.total_batch_count, job.completed_batch_count + remaining_batch_count)
            if is_resuming and job.total_batch_count > 0
            else remaining_batch_count
        )
        cursor = (
            fetch_ranges[0].start_open_time_ms
            if fetch_ranges
            else effective_end_open_time_ms + interval.milliseconds
        )
        fetched_count = job.fetched_count
        saved_count = job.saved_count
        failed_count = job.failed_count
        missing_count = job.missing_count
        completed_batch_count = job.completed_batch_count
        provider_unavailable_ranges: list[OpenTimeRange] = []
        completed_fetch_count = (
            _count_completed_before_cursor(
                start_open_time_ms=effective_start_time_ms,
                cursor_open_time_ms=resume_cursor_time_ms,
                interval_ms=interval.milliseconds,
            )
            if resume_cursor_time_ms is not None
            else 0
        )

        logger.info(
            "fetch job effective range resolved job_id=%s mode=%s requested_start_time_ms=%s effective_start_time_ms=%s effective_end_open_time_ms=%s fetch_range_count=%s total_estimated_count=%s total_batch_count=%s overlap_candles=%s resume_cursor_time_ms=%s",
            job.id,
            job.mode,
            job.requested_start_time_ms,
            effective_start_time_ms,
            effective_end_open_time_ms,
            len(fetch_ranges),
            total_estimated_count,
            total_batch_count,
            job.overlap_candles,
            resume_cursor_time_ms,
        )

        for range_index, fetch_range in enumerate(fetch_ranges, start=1):
            controlled_job = self._get_controlled_job(job.id)
            if controlled_job is not None:
                return controlled_job
            cursor = fetch_range.start_open_time_ms
            expected_next_open_time_ms = fetch_range.start_open_time_ms
            range_completed_count = 0
            logger.info(
                "fetch job range started job_id=%s range_index=%s range_count=%s start_open_time_ms=%s end_open_time_ms=%s start_time=%s end_time=%s",
                job.id,
                range_index,
                len(fetch_ranges),
                fetch_range.start_open_time_ms,
                fetch_range.end_open_time_ms,
                ms_to_iso(fetch_range.start_open_time_ms),
                ms_to_iso(fetch_range.end_open_time_ms),
            )

            while cursor <= fetch_range.end_open_time_ms:
                controlled_job = self._get_controlled_job(job.id)
                if controlled_job is not None:
                    return controlled_job
                batch_index = completed_batch_count + 1
                batch_started_at = perf_counter()
                batch_end_open_time_ms = min(
                    fetch_range.end_open_time_ms,
                    cursor + ((job.batch_limit - 1) * interval.milliseconds),
                )
                batch_limit = _count_expected_candles(
                    start_open_time_ms=cursor,
                    end_open_time_ms=batch_end_open_time_ms,
                    interval_ms=interval.milliseconds,
                )
                logger.info(
                    "fetch job batch started job_id=%s batch_index=%s total_batch_count=%s range_index=%s start_open_time_ms=%s end_open_time_ms=%s start_time=%s end_time=%s limit=%s overlap_candles=%s",
                    job.id,
                    batch_index,
                    total_batch_count,
                    range_index,
                    cursor,
                    batch_end_open_time_ms,
                    ms_to_iso(cursor),
                    ms_to_iso(batch_end_open_time_ms),
                    batch_limit,
                    job.overlap_candles,
                )
                batch_candles = provider.fetch_klines(
                    CandleBatchQuery(
                        fetch_id=job.id,
                        batch_index=batch_index,
                        batch_count=total_batch_count,
                        provider=job.provider,
                        market_type=job.market_type,
                        market_pair=job.market_pair,
                        interval=job.interval,
                        start_time_ms=cursor,
                        end_time_ms=batch_end_open_time_ms + interval.milliseconds - 1,
                        limit=batch_limit,
                        retry_attempts=job.retry_attempts,
                        retry_delay_seconds=job.retry_delay_seconds,
                    )
                )
                controlled_job = self._get_controlled_job(job.id)
                if controlled_job is not None:
                    return controlled_job
                accepted_candles = [
                    candle
                    for candle in batch_candles[:batch_limit]
                    if cursor <= candle.open_time_ms <= batch_end_open_time_ms
                ]
                if not accepted_candles:
                    logger.warning(
                        "fetch job batch returned no accepted candles job_id=%s batch_index=%s provider_count=%s cursor=%s batch_end_open_time_ms=%s",
                        job.id,
                        batch_index,
                        len(batch_candles),
                        cursor,
                        batch_end_open_time_ms,
                    )
                    if job.mode != "fill_gaps" and batch_end_open_time_ms >= fetch_range.end_open_time_ms:
                        logger.info(
                            "fetch job reached provider tail with no accepted candles job_id=%s batch_index=%s cursor=%s fetch_range_end_open_time_ms=%s",
                            job.id,
                            batch_index,
                            cursor,
                            fetch_range.end_open_time_ms,
                        )
                        break
                    provider_unavailable_ranges.append(
                        OpenTimeRange(
                            start_open_time_ms=cursor,
                            end_open_time_ms=batch_end_open_time_ms,
                        )
                    )
                    completed_batch_count += 1
                    cursor = batch_end_open_time_ms + interval.milliseconds
                    expected_next_open_time_ms = cursor
                    range_completed_count = _count_expected_candles(
                        start_open_time_ms=fetch_range.start_open_time_ms,
                        end_open_time_ms=batch_end_open_time_ms,
                        interval_ms=interval.milliseconds,
                    )
                    progress_percent = _calculate_progress_percent(
                        completed_count=min(total_estimated_count, completed_fetch_count + range_completed_count),
                        total_estimated_count=total_estimated_count,
                    )
                    job = self._fetch_job_repository.update_progress(
                        job_id=job.id,
                        effective_start_time_ms=effective_start_time_ms,
                        current_cursor_time_ms=cursor,
                        total_estimated_count=total_estimated_count,
                        fetched_count=fetched_count,
                        saved_count=saved_count,
                        failed_count=failed_count,
                        missing_count=missing_count,
                        completed_batch_count=completed_batch_count,
                        total_batch_count=total_batch_count,
                        progress_percent=progress_percent,
                    )
                    continue

                if job.verify_continuity:
                    provider_unavailable_ranges.extend(
                        _find_batch_missing_ranges(
                            expected_next_open_time_ms=expected_next_open_time_ms,
                            candles=accepted_candles,
                            interval_ms=interval.milliseconds,
                            job_id=job.id,
                            batch_index=batch_index,
                        )
                    )

                batch_saved_count = self._store_batch(
                    job=job,
                    candles=accepted_candles,
                    start_open_time_ms=cursor,
                    end_open_time_ms=batch_end_open_time_ms,
                )
                fetched_count += len(accepted_candles)
                saved_count += batch_saved_count
                completed_batch_count += 1
                last_open_time_ms = accepted_candles[-1].open_time_ms
                next_cursor_no_overlap = last_open_time_ms + interval.milliseconds
                should_continue = (
                    len(accepted_candles) >= batch_limit
                    and next_cursor_no_overlap <= fetch_range.end_open_time_ms
                )
                cursor = (
                    _calculate_next_cursor_with_overlap(
                        current_cursor_time_ms=cursor,
                        next_cursor_no_overlap=next_cursor_no_overlap,
                        interval_ms=interval.milliseconds,
                        overlap_candles=job.overlap_candles,
                        accepted_count=len(accepted_candles),
                    )
                    if should_continue
                    else next_cursor_no_overlap
                )
                expected_next_open_time_ms = max(expected_next_open_time_ms, next_cursor_no_overlap)
                range_completed_count = _count_expected_candles(
                    start_open_time_ms=fetch_range.start_open_time_ms,
                    end_open_time_ms=min(last_open_time_ms, fetch_range.end_open_time_ms),
                    interval_ms=interval.milliseconds,
                )
                progress_percent = _calculate_progress_percent(
                    completed_count=min(total_estimated_count, completed_fetch_count + range_completed_count),
                    total_estimated_count=total_estimated_count,
                )
                job = self._fetch_job_repository.update_progress(
                    job_id=job.id,
                    effective_start_time_ms=effective_start_time_ms,
                    current_cursor_time_ms=cursor,
                    total_estimated_count=total_estimated_count,
                    fetched_count=fetched_count,
                    saved_count=saved_count,
                    failed_count=failed_count,
                    missing_count=missing_count,
                    completed_batch_count=completed_batch_count,
                    total_batch_count=total_batch_count,
                    progress_percent=progress_percent,
                )
                controlled_job = self._get_controlled_job(job.id)
                if controlled_job is not None:
                    return controlled_job
                logger.info(
                    "fetch job batch completed job_id=%s batch_index=%s provider_count=%s accepted_count=%s saved_count=%s total_saved_count=%s next_cursor_no_overlap=%s current_cursor_time_ms=%s progress_percent=%.4f duration_ms=%s",
                    job.id,
                    batch_index,
                    len(batch_candles),
                    len(accepted_candles),
                    batch_saved_count,
                    saved_count,
                    next_cursor_no_overlap,
                    cursor,
                    progress_percent,
                    int((perf_counter() - batch_started_at) * 1000),
                )
                if len(accepted_candles) < batch_limit and last_open_time_ms < batch_end_open_time_ms:
                    logger.info(
                        "fetch job batch ended before requested end job_id=%s batch_index=%s accepted_count=%s batch_limit=%s last_open_time_ms=%s batch_end_open_time_ms=%s",
                        job.id,
                        batch_index,
                        len(accepted_candles),
                        batch_limit,
                        last_open_time_ms,
                        batch_end_open_time_ms,
                    )

            completed_fetch_count += range_completed_count

        controlled_job = self._get_controlled_job(job.id)
        if controlled_job is not None:
            return controlled_job

        if job.verify_continuity:
            final_missing_ranges = _find_repository_missing_ranges(
                repository=self._candle_repository,
                provider=job.provider,
                market_pair=job.market_pair,
                interval=job.interval,
                start_open_time_ms=effective_start_time_ms,
                end_open_time_ms=effective_end_open_time_ms,
                interval_ms=interval.milliseconds,
                excluded_ranges=provider_unavailable_ranges,
            )
            final_missing_count = _count_open_time_ranges(
                ranges=final_missing_ranges,
                interval_ms=interval.milliseconds,
            )
            first_missing_open_time_ms = (
                final_missing_ranges[0].start_open_time_ms if final_missing_ranges else None
            )
            missing_count = final_missing_count
            if final_missing_count:
                progress_percent = _calculate_progress_percent(
                    completed_count=max(0, total_estimated_count - final_missing_count),
                    total_estimated_count=total_estimated_count,
                )
                self._fetch_job_repository.update_progress(
                    job_id=job.id,
                    effective_start_time_ms=effective_start_time_ms,
                    current_cursor_time_ms=cursor,
                    total_estimated_count=total_estimated_count,
                    fetched_count=fetched_count,
                    saved_count=saved_count,
                    failed_count=failed_count,
                    missing_count=missing_count,
                    completed_batch_count=completed_batch_count,
                    total_batch_count=total_batch_count,
                    progress_percent=progress_percent,
                )
                self._record_detected_data_gaps(
                    job=job,
                    ranges=final_missing_ranges,
                    interval_ms=interval.milliseconds,
                    reason="fetch_job_continuity_check",
                )
                raise ValueError(
                    "Fetch job finished with incomplete stored candles. "
                    f"missing_count={final_missing_count}, "
                    f"first_missing_open_time={ms_to_iso(first_missing_open_time_ms)}"
                )

        job = self._fetch_job_repository.update_progress(
            job_id=job.id,
            effective_start_time_ms=effective_start_time_ms,
            current_cursor_time_ms=cursor,
            total_estimated_count=total_estimated_count,
            fetched_count=fetched_count,
            saved_count=saved_count,
            failed_count=failed_count,
            missing_count=missing_count,
            completed_batch_count=completed_batch_count,
            total_batch_count=total_batch_count,
            progress_percent=100,
        )
        controlled_job = self._get_controlled_job(job.id)
        if controlled_job is not None:
            return controlled_job
        return self._fetch_job_repository.mark_succeeded(job.id)

    def _record_detected_data_gaps(
        self,
        *,
        job: CandleFetchJob,
        ranges: list[OpenTimeRange],
        interval_ms: int,
        reason: str,
    ) -> None:
        if self._data_gap_repository is None or not ranges:
            return

        gaps = [
            DataGapCreate(
                provider=job.provider,
                market_type=job.market_type,
                market_pair=job.market_pair,
                exchange_symbol=job.exchange_symbol,
                interval=job.interval,
                start_open_time_ms=item.start_open_time_ms,
                end_open_time_ms=item.end_open_time_ms,
                start_open_time=ms_to_iso(item.start_open_time_ms) or "",
                end_open_time=ms_to_iso(item.end_open_time_ms) or "",
                missing_count=_count_expected_candles(
                    start_open_time_ms=item.start_open_time_ms,
                    end_open_time_ms=item.end_open_time_ms,
                    interval_ms=interval_ms,
                ),
                source_job_id=job.id,
                reason=reason,
            )
            for item in ranges
        ]
        try:
            self._data_gap_repository.upsert_detected_many(gaps)
        except Exception:
            logger.exception("fetch job failed to record data gaps job_id=%s gap_count=%s", job.id, len(gaps))

    def _resolve_provider_start_open_time_ms(
        self,
        *,
        job: CandleFetchJob,
        provider: MarketDataProvider,
        interval: CandleInterval,
        effective_end_open_time_ms: int,
    ) -> int | None:
        logger.info(
            "fetch job provider start discovery started job_id=%s requested_start_time_ms=%s effective_end_open_time_ms=%s",
            job.id,
            job.requested_start_time_ms,
            effective_end_open_time_ms,
        )
        first_available_open_time_ms = provider.first_available_open_time_ms(
            CandleAvailabilityQuery(
                fetch_id=job.id,
                provider=job.provider,
                market_type=job.market_type,
                market_pair=job.market_pair,
                interval=job.interval,
                start_time_ms=job.requested_start_time_ms,
                end_time_ms=effective_end_open_time_ms + interval.milliseconds - 1,
                retry_attempts=job.retry_attempts,
                retry_delay_seconds=job.retry_delay_seconds,
            )
        )
        if first_available_open_time_ms is None:
            resolved_start_open_time_ms = None
        elif first_available_open_time_ms > effective_end_open_time_ms:
            resolved_start_open_time_ms = None
        else:
            resolved_start_open_time_ms = max(job.requested_start_time_ms, first_available_open_time_ms)
        logger.info(
            "fetch job provider start discovery completed job_id=%s provider_first_open_time_ms=%s resolved_start_open_time_ms=%s",
            job.id,
            first_available_open_time_ms,
            resolved_start_open_time_ms,
        )
        return resolved_start_open_time_ms

    def _store_batch(
        self,
        *,
        job: CandleFetchJob,
        candles: list[Candle],
        start_open_time_ms: int,
        end_open_time_ms: int,
    ) -> int:
        if job.mode == "delete_reload":
            self._ensure_complete_batch(
                candles=candles,
                start_open_time_ms=start_open_time_ms,
                end_open_time_ms=end_open_time_ms,
                interval_ms=CandleInterval.parse(job.interval).milliseconds,
            )
            return self._candle_repository.replace_range(
                provider=job.provider,
                market_type=job.market_type,
                market_pair=job.market_pair,
                interval=job.interval,
                start_time_ms=start_open_time_ms,
                end_time_ms=end_open_time_ms,
                candles=candles,
            )
        return self._candle_repository.upsert_many(candles)

    def _ensure_complete_batch(
        self,
        *,
        candles: list[Candle],
        start_open_time_ms: int,
        end_open_time_ms: int,
        interval_ms: int,
    ) -> None:
        actual_open_times = {candle.open_time_ms for candle in candles}
        expected_open_time_ms = start_open_time_ms
        while expected_open_time_ms <= end_open_time_ms:
            if expected_open_time_ms not in actual_open_times:
                raise ValueError(
                    "delete_reload job requires a complete provider response before replacing stored data. "
                    f"first_missing_open_time={ms_to_iso(expected_open_time_ms)}"
                )
            expected_open_time_ms += interval_ms


def _resolve_job_mode(mode: str) -> str:
    if mode == "auto":
        return "backfill"
    return mode


def _count_expected_candles(
    *,
    start_open_time_ms: int,
    end_open_time_ms: int,
    interval_ms: int,
) -> int:
    return ((end_open_time_ms - start_open_time_ms) // interval_ms) + 1


def _count_batches_with_overlap(
    *,
    total_estimated_count: int,
    batch_limit: int,
    overlap_candles: int,
) -> int:
    if total_estimated_count <= 0:
        return 0
    if total_estimated_count <= batch_limit:
        return 1
    safe_overlap = min(max(0, overlap_candles), max(0, batch_limit - 1))
    advance_count = max(1, batch_limit - safe_overlap)
    remaining_count = total_estimated_count - batch_limit
    return 1 + ((remaining_count + advance_count - 1) // advance_count)


def _count_batches_for_ranges(
    *,
    ranges: list[OpenTimeRange],
    interval_ms: int,
    batch_limit: int,
    overlap_candles: int,
) -> int:
    return sum(
        _count_batches_with_overlap(
            total_estimated_count=_count_expected_candles(
                start_open_time_ms=item.start_open_time_ms,
                end_open_time_ms=item.end_open_time_ms,
                interval_ms=interval_ms,
            ),
            batch_limit=batch_limit,
            overlap_candles=overlap_candles,
        )
        for item in ranges
    )


def _count_open_time_ranges(*, ranges: list[OpenTimeRange], interval_ms: int) -> int:
    return sum(
        _count_expected_candles(
            start_open_time_ms=item.start_open_time_ms,
            end_open_time_ms=item.end_open_time_ms,
            interval_ms=interval_ms,
        )
        for item in ranges
    )


def _resolve_resume_cursor(
    *,
    job: CandleFetchJob,
    effective_start_time_ms: int,
    effective_end_open_time_ms: int,
    interval_ms: int,
) -> int | None:
    if job.current_cursor_time_ms is None:
        return None
    if job.completed_batch_count <= 0 and job.fetched_count <= 0 and job.saved_count <= 0:
        return None
    if job.current_cursor_time_ms <= effective_start_time_ms:
        return None
    if job.current_cursor_time_ms > effective_end_open_time_ms:
        return effective_end_open_time_ms + interval_ms
    return job.current_cursor_time_ms


def _trim_open_time_ranges_from_cursor(
    *,
    ranges: list[OpenTimeRange],
    cursor_open_time_ms: int,
) -> list[OpenTimeRange]:
    return [
        OpenTimeRange(
            start_open_time_ms=max(item.start_open_time_ms, cursor_open_time_ms),
            end_open_time_ms=item.end_open_time_ms,
        )
        for item in ranges
        if item.end_open_time_ms >= cursor_open_time_ms
    ]


def _count_completed_before_cursor(
    *,
    start_open_time_ms: int,
    cursor_open_time_ms: int | None,
    interval_ms: int,
) -> int:
    if cursor_open_time_ms is None or cursor_open_time_ms <= start_open_time_ms:
        return 0
    last_completed_open_time_ms = cursor_open_time_ms - interval_ms
    return _count_expected_candles(
        start_open_time_ms=start_open_time_ms,
        end_open_time_ms=last_completed_open_time_ms,
        interval_ms=interval_ms,
    )


def _find_repository_missing_ranges(
    *,
    repository: CandleRepository,
    provider: str,
    market_pair: str,
    interval: str,
    start_open_time_ms: int,
    end_open_time_ms: int,
    interval_ms: int,
    excluded_ranges: list[OpenTimeRange] | None = None,
) -> list[OpenTimeRange]:
    actual_open_times = set(
        repository.list_open_time_ms(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            start_time_ms=start_open_time_ms,
            end_time_ms=end_open_time_ms,
        )
    )
    merged_excluded_ranges = _merge_open_time_ranges(
        ranges=excluded_ranges or [],
        interval_ms=interval_ms,
    )
    excluded_index = 0

    missing_ranges: list[OpenTimeRange] = []
    current_start: int | None = None
    current_end: int | None = None
    expected_open_time_ms = start_open_time_ms
    while expected_open_time_ms <= end_open_time_ms:
        while (
            excluded_index < len(merged_excluded_ranges)
            and merged_excluded_ranges[excluded_index].end_open_time_ms < expected_open_time_ms
        ):
            excluded_index += 1
        is_provider_unavailable = (
            excluded_index < len(merged_excluded_ranges)
            and merged_excluded_ranges[excluded_index].start_open_time_ms <= expected_open_time_ms
            and expected_open_time_ms <= merged_excluded_ranges[excluded_index].end_open_time_ms
        )
        if not is_provider_unavailable and expected_open_time_ms not in actual_open_times:
            if current_start is None:
                current_start = expected_open_time_ms
            current_end = expected_open_time_ms
        elif current_start is not None and current_end is not None:
            missing_ranges.append(
                OpenTimeRange(
                    start_open_time_ms=current_start,
                    end_open_time_ms=current_end,
                )
            )
            current_start = None
            current_end = None
        expected_open_time_ms += interval_ms

    if current_start is not None and current_end is not None:
        missing_ranges.append(
            OpenTimeRange(
                start_open_time_ms=current_start,
                end_open_time_ms=current_end,
            )
        )

    return missing_ranges


def _expand_ranges_with_overlap(
    *,
    ranges: list[OpenTimeRange],
    lower_bound_open_time_ms: int,
    upper_bound_open_time_ms: int,
    interval_ms: int,
    overlap_candles: int,
) -> list[OpenTimeRange]:
    overlap_ms = max(0, overlap_candles) * interval_ms
    expanded = [
        OpenTimeRange(
            start_open_time_ms=max(lower_bound_open_time_ms, item.start_open_time_ms - overlap_ms),
            end_open_time_ms=min(upper_bound_open_time_ms, item.end_open_time_ms + overlap_ms),
        )
        for item in ranges
    ]
    return _merge_open_time_ranges(ranges=expanded, interval_ms=interval_ms)


def _merge_open_time_ranges(
    *,
    ranges: list[OpenTimeRange],
    interval_ms: int,
) -> list[OpenTimeRange]:
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda item: item.start_open_time_ms)
    merged: list[OpenTimeRange] = [sorted_ranges[0]]
    for item in sorted_ranges[1:]:
        last = merged[-1]
        if item.start_open_time_ms <= last.end_open_time_ms + interval_ms:
            merged[-1] = OpenTimeRange(
                start_open_time_ms=last.start_open_time_ms,
                end_open_time_ms=max(last.end_open_time_ms, item.end_open_time_ms),
            )
            continue
        merged.append(item)
    return merged


def _calculate_next_cursor_with_overlap(
    *,
    current_cursor_time_ms: int,
    next_cursor_no_overlap: int,
    interval_ms: int,
    overlap_candles: int,
    accepted_count: int,
) -> int:
    safe_overlap = min(max(0, overlap_candles), max(0, accepted_count - 1))
    next_cursor = next_cursor_no_overlap - (safe_overlap * interval_ms)
    if next_cursor <= current_cursor_time_ms:
        return next_cursor_no_overlap
    return next_cursor


def _calculate_progress_percent(*, completed_count: int, total_estimated_count: int) -> float:
    if total_estimated_count <= 0:
        return 100
    return min(99.9, (completed_count / total_estimated_count) * 100)


def _find_batch_missing_ranges(
    *,
    expected_next_open_time_ms: int,
    candles: list[Candle],
    interval_ms: int,
    job_id: str,
    batch_index: int,
) -> list[OpenTimeRange]:
    missing_ranges: list[OpenTimeRange] = []
    expected_open_time_ms = expected_next_open_time_ms
    for candle in candles:
        if candle.open_time_ms < expected_open_time_ms:
            continue
        if expected_open_time_ms < candle.open_time_ms:
            gap = OpenTimeRange(
                start_open_time_ms=expected_open_time_ms,
                end_open_time_ms=candle.open_time_ms - interval_ms,
            )
            logger.warning(
                "fetch job provider unavailable gap detected job_id=%s batch_index=%s first_missing_open_time_ms=%s first_missing_open_time=%s next_provider_open_time_ms=%s",
                job_id,
                batch_index,
                gap.start_open_time_ms,
                ms_to_iso(gap.start_open_time_ms),
                candle.open_time_ms,
            )
            missing_ranges.append(gap)
        expected_open_time_ms = candle.open_time_ms + interval_ms
    return missing_ranges


def _count_repository_missing_candles(
    *,
    repository: CandleRepository,
    provider: str,
    market_pair: str,
    interval: str,
    start_open_time_ms: int,
    end_open_time_ms: int,
    interval_ms: int,
    excluded_ranges: list[OpenTimeRange] | None = None,
) -> tuple[int, int | None]:
    actual_open_times = set(
        repository.list_open_time_ms(
            provider=provider,
            market_pair=market_pair,
            interval=interval,
            start_time_ms=start_open_time_ms,
            end_time_ms=end_open_time_ms,
        )
    )
    merged_excluded_ranges = _merge_open_time_ranges(
        ranges=excluded_ranges or [],
        interval_ms=interval_ms,
    )
    excluded_index = 0

    missing_count = 0
    first_missing_open_time_ms: int | None = None
    expected_open_time_ms = start_open_time_ms
    while expected_open_time_ms <= end_open_time_ms:
        while (
            excluded_index < len(merged_excluded_ranges)
            and merged_excluded_ranges[excluded_index].end_open_time_ms < expected_open_time_ms
        ):
            excluded_index += 1
        is_provider_unavailable = (
            excluded_index < len(merged_excluded_ranges)
            and merged_excluded_ranges[excluded_index].start_open_time_ms <= expected_open_time_ms
            and expected_open_time_ms <= merged_excluded_ranges[excluded_index].end_open_time_ms
        )
        if not is_provider_unavailable and expected_open_time_ms not in actual_open_times:
            missing_count += 1
            if first_missing_open_time_ms is None:
                first_missing_open_time_ms = expected_open_time_ms
        expected_open_time_ms += interval_ms

    return missing_count, first_missing_open_time_ms


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _datetime_from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _resolve_timezone(timezone_name: str) -> tuple[tzinfo, str]:
    if timezone_name in {"UTC", "Etc/UTC"}:
        return timezone.utc, "UTC"
    try:
        return ZoneInfo(timezone_name), timezone_name
    except ZoneInfoNotFoundError as exc:
        fixed_offset = FIXED_TIMEZONE_OFFSETS.get(timezone_name)
        if fixed_offset is not None:
            return timezone(fixed_offset, timezone_name), timezone_name
        raise ValueError(f"Unsupported timezone: {timezone_name}") from exc


def _require_datetime_ms(value: datetime) -> int:
    timestamp_ms = datetime_to_ms(value)
    if timestamp_ms is None:
        raise ValueError("Unable to resolve summary time range.")
    return timestamp_ms
