from dataclasses import replace
from datetime import datetime, timezone
import logging
from uuid import uuid4

from app.application.models.fetch_job import CandleFetchJob, CandleFetchJobCreateCommand
from app.application.models.schedule import Schedule, ScheduleCreateCommand, ScheduleUpdateCommand
from app.application.ports.fetch_job_repository import FetchJobRepository
from app.application.ports.schedule_repository import ScheduleRepository
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.services.candle_fetch_planner import ms_to_iso
from app.application.services.cron import next_cron_run, validate_cron_expression
from app.domain.value_objects.candle_interval import CandleInterval
from app.domain.value_objects.market_pair import MarketPair
from app.domain.value_objects.provider import normalize_provider

logger = logging.getLogger(__name__)


class DuplicateScheduleError(ValueError):
    def __init__(self, existing_schedule: Schedule) -> None:
        self.existing_schedule = existing_schedule
        super().__init__(f"Schedule already exists: {existing_schedule.id}")


class ScheduleService:
    def __init__(
        self,
        *,
        schedule_repository: ScheduleRepository,
        fetch_job_repository: FetchJobRepository,
        fetch_job_service: CandleFetchJobService,
    ) -> None:
        self._schedule_repository = schedule_repository
        self._fetch_job_repository = fetch_job_repository
        self._fetch_job_service = fetch_job_service

    def create_schedule(self, command: ScheduleCreateCommand) -> Schedule:
        cron_expression = _normalize_cron_expression(command.cron_expression)
        validate_cron_expression(cron_expression)
        provider = normalize_provider(command.provider)
        pair = MarketPair.parse(command.market_pair)
        CandleInterval.parse(command.interval)
        mode = _resolve_schedule_mode(command.mode)
        timezone_name = _normalize_timezone(command.timezone)
        exchange_symbol = pair.exchange_symbol_for(provider)
        existing = self._schedule_repository.find_by_identity(
            provider=provider,
            market_type=command.market_type,
            exchange_symbol=exchange_symbol,
            interval=command.interval,
            mode=mode,
            cron_expression=cron_expression,
            timezone=timezone_name,
        )
        if existing is not None:
            raise DuplicateScheduleError(existing)
        created_at = _utcnow_iso()
        next_run_at_ms = _next_run_ms(cron_expression) if command.enabled else None
        schedule = Schedule(
            id=uuid4().hex[:12],
            name=_build_schedule_name(
                provider=provider,
                market_type=command.market_type,
                market_pair=pair.display,
                interval=command.interval,
                mode=mode,
                cron_expression=cron_expression,
                timezone_name=timezone_name,
            ),
            enabled=command.enabled,
            provider=provider,
            market_type=command.market_type,
            market_pair=pair.display,
            exchange_symbol=exchange_symbol,
            interval=command.interval,
            mode=mode,
            cron_expression=cron_expression,
            timezone=timezone_name,
            start_time_ms=command.start_time_ms,
            batch_limit=command.batch_limit,
            overlap_candles=command.overlap_candles,
            verify_continuity=command.verify_continuity,
            retry_attempts=command.retry_attempts,
            retry_delay_seconds=command.retry_delay_seconds,
            last_triggered_at_ms=None,
            next_run_at_ms=next_run_at_ms,
            created_at=created_at,
            updated_at=created_at,
        )
        created = self._schedule_repository.create(schedule)
        logger.info(
            "schedule created schedule_id=%s provider=%s market_pair=%s interval=%s mode=%s cron=%s enabled=%s next_run_at=%s",
            created.id,
            created.provider,
            created.market_pair,
            created.interval,
            created.mode,
            created.cron_expression,
            created.enabled,
            ms_to_iso(created.next_run_at_ms),
        )
        return created

    def get_schedule(self, schedule_id: str) -> Schedule:
        schedule = self._schedule_repository.get(schedule_id)
        if schedule is None:
            raise ValueError(f"Schedule not found: {schedule_id}")
        return schedule

    def list_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Schedule]:
        selected_provider = normalize_provider(provider) if provider else None
        return self._schedule_repository.list_schedules(
            provider=selected_provider,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )

    def count_schedules(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
    ) -> int:
        selected_provider = normalize_provider(provider) if provider else None
        return self._schedule_repository.count_schedules(provider=selected_provider, enabled=enabled)

    def update_schedule(self, schedule_id: str, command: ScheduleUpdateCommand) -> Schedule:
        current = self.get_schedule(schedule_id)
        provider = normalize_provider(command.provider) if command.provider else current.provider
        pair = MarketPair.parse(command.market_pair) if command.market_pair else MarketPair.parse(current.market_pair)
        interval = command.interval or current.interval
        CandleInterval.parse(interval)
        cron_expression = _normalize_cron_expression(command.cron_expression or current.cron_expression)
        validate_cron_expression(cron_expression)
        enabled = current.enabled if command.enabled is None else command.enabled
        market_type = command.market_type or current.market_type
        mode = _resolve_schedule_mode(command.mode or current.mode)
        timezone_name = _normalize_timezone(command.timezone or current.timezone)
        exchange_symbol = pair.exchange_symbol_for(provider)
        existing = self._schedule_repository.find_by_identity(
            provider=provider,
            market_type=market_type,
            exchange_symbol=exchange_symbol,
            interval=interval,
            mode=mode,
            cron_expression=cron_expression,
            timezone=timezone_name,
            exclude_id=schedule_id,
        )
        if existing is not None:
            raise DuplicateScheduleError(existing)
        next_run_at_ms = _next_run_ms(cron_expression) if enabled else None
        updated = replace(
            current,
            name=_build_schedule_name(
                provider=provider,
                market_type=market_type,
                market_pair=pair.display,
                interval=interval,
                mode=mode,
                cron_expression=cron_expression,
                timezone_name=timezone_name,
            ),
            enabled=enabled,
            provider=provider,
            market_type=market_type,
            market_pair=pair.display,
            exchange_symbol=exchange_symbol,
            interval=interval,
            mode=mode,
            cron_expression=cron_expression,
            timezone=timezone_name,
            start_time_ms=command.start_time_ms if command.start_time_ms is not None else current.start_time_ms,
            batch_limit=command.batch_limit if command.batch_limit is not None else current.batch_limit,
            overlap_candles=(
                command.overlap_candles if command.overlap_candles is not None else current.overlap_candles
            ),
            verify_continuity=(
                command.verify_continuity
                if command.verify_continuity is not None
                else current.verify_continuity
            ),
            retry_attempts=(
                command.retry_attempts if command.retry_attempts is not None else current.retry_attempts
            ),
            retry_delay_seconds=(
                command.retry_delay_seconds
                if command.retry_delay_seconds is not None
                else current.retry_delay_seconds
            ),
            next_run_at_ms=next_run_at_ms,
        )
        return self._schedule_repository.update(updated)

    def set_enabled(self, schedule_id: str, enabled: bool) -> Schedule:
        return self.update_schedule(schedule_id, ScheduleUpdateCommand(enabled=enabled))

    def delete_schedule(self, schedule_id: str) -> None:
        if not self._schedule_repository.delete(schedule_id):
            raise ValueError(f"Schedule not found: {schedule_id}")

    def create_job_from_schedule(self, schedule_id: str) -> CandleFetchJob:
        schedule = self.get_schedule(schedule_id)
        return self._create_job_from_schedule(schedule)

    def create_due_jobs(self, *, due_at: datetime | None = None, limit: int = 20) -> list[CandleFetchJob]:
        due_at = due_at or datetime.now(timezone.utc)
        due_at_ms = _datetime_to_ms(due_at)
        jobs: list[CandleFetchJob] = []
        for schedule in self._schedule_repository.list_due(due_at_ms=due_at_ms, limit=limit):
            next_run_at_ms = _next_run_ms(schedule.cron_expression, after=due_at)
            if self._fetch_job_repository.has_active_job_for_schedule(schedule.id):
                logger.info("schedule skipped because active job exists schedule_id=%s", schedule.id)
                self._schedule_repository.update_runtime(
                    schedule_id=schedule.id,
                    last_triggered_at_ms=None,
                    next_run_at_ms=next_run_at_ms,
                )
                continue
            job = self._create_job_from_schedule(schedule)
            self._schedule_repository.update_runtime(
                schedule_id=schedule.id,
                last_triggered_at_ms=due_at_ms,
                next_run_at_ms=next_run_at_ms,
            )
            jobs.append(job)
        return jobs

    def _create_job_from_schedule(self, schedule: Schedule) -> CandleFetchJob:
        job = self._fetch_job_service.create_scheduled_backfill_job(
            CandleFetchJobCreateCommand(
                provider=schedule.provider,
                market_type=schedule.market_type,
                market_pair=schedule.market_pair,
                interval=schedule.interval,
                start_time=_datetime_from_ms(schedule.start_time_ms),
                end_time=None,
                mode=schedule.mode,
                closed_only=True,
                batch_limit=schedule.batch_limit,
                overlap_candles=schedule.overlap_candles,
                verify_continuity=schedule.verify_continuity,
                retry_attempts=schedule.retry_attempts,
                retry_delay_seconds=schedule.retry_delay_seconds,
                schedule_id=schedule.id,
                trigger_type="scheduled",
            )
        )
        logger.info(
            "schedule created fetch job schedule_id=%s job_id=%s provider=%s market_pair=%s interval=%s mode=%s",
            schedule.id,
            job.id,
            job.provider,
            job.market_pair,
            job.interval,
            job.mode,
        )
        return job


def _resolve_schedule_mode(mode: str) -> str:
    if mode == "latest":
        return "auto"
    return mode


def _build_schedule_name(
    *,
    provider: str,
    market_type: str,
    market_pair: str,
    interval: str,
    mode: str,
    cron_expression: str,
    timezone_name: str,
) -> str:
    return (
        f"{_provider_label(provider)} {market_type.upper()} {market_pair} "
        f"{interval} {_mode_label(mode)} - {_cron_label(cron_expression)} ({timezone_name})"
    )


def _provider_label(provider: str) -> str:
    if provider.lower() == "okx":
        return "OKX"
    return provider[:1].upper() + provider[1:]


def _mode_label(mode: str) -> str:
    return {
        "auto": "Auto",
        "backfill": "Backfill",
        "fill_gaps": "Fill gaps",
        "overwrite_range": "Overwrite range",
        "delete_reload": "Delete reload",
    }.get(mode, mode.replace("_", " ").title())


def _cron_label(expression: str) -> str:
    parts = expression.split()
    if len(parts) != 5:
        return expression
    minute, hour, day, month, weekday = parts
    if hour == day == month == weekday == "*" and minute.startswith("*/"):
        return _every_label(minute[2:], "minute")
    if minute == "0" and day == month == weekday == "*" and hour.startswith("*/"):
        return _every_label(hour[2:], "hour")
    if minute == "0" and hour == "0" and day == month == weekday == "*":
        return "daily"
    return expression


def _every_label(value: str, unit: str) -> str:
    try:
        amount = int(value)
    except ValueError:
        return f"every {value} {unit}s"
    suffix = "" if amount == 1 else "s"
    return f"every {amount} {unit}{suffix}"


def _normalize_cron_expression(expression: str) -> str:
    return " ".join(expression.split())


def _normalize_timezone(timezone_name: str) -> str:
    return timezone_name.strip() or "UTC"


def _next_run_ms(expression: str, *, after: datetime | None = None) -> int:
    return _datetime_to_ms(next_cron_run(expression, after=after or datetime.now(timezone.utc)))


def _datetime_to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def _datetime_from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
