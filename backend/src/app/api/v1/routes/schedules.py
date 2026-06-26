from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.v1.dependencies import get_candle_fetch_job_service, get_schedule_service
from app.application.services.candle_fetch_job_service import CandleFetchJobService
from app.application.services.schedule_service import DuplicateScheduleError, ScheduleService
from app.schemas.requests.schedules import ScheduleCreateRequest, ScheduleUpdateRequest
from app.schemas.responses.fetch_jobs import CandleFetchJobResponse
from app.schemas.responses.schedules import ScheduleListResponse, ScheduleResponse

router = APIRouter()


@router.get("", response_model=ScheduleListResponse)
def list_schedules(
    provider: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleListResponse:
    try:
        count = service.count_schedules(provider=provider, enabled=enabled)
        schedules = service.list_schedules(provider=provider, enabled=enabled, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    responses = [ScheduleResponse.from_schedule(schedule) for schedule in schedules]
    return ScheduleListResponse(count=count, schedules=responses)


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    request: ScheduleCreateRequest,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        schedule = service.create_schedule(request.to_command())
    except DuplicateScheduleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScheduleResponse.from_schedule(schedule)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        schedule = service.get_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.from_schedule(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        schedule = service.update_schedule(schedule_id, request.to_command())
    except DuplicateScheduleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScheduleResponse.from_schedule(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> None:
    try:
        service.delete_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{schedule_id}/enable", response_model=ScheduleResponse)
def enable_schedule(
    schedule_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        schedule = service.set_enabled(schedule_id, True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.from_schedule(schedule)


@router.post("/{schedule_id}/resume", response_model=ScheduleResponse)
def resume_schedule(
    schedule_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        schedule = service.set_enabled(schedule_id, True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.from_schedule(schedule)


@router.post("/{schedule_id}/disable", response_model=ScheduleResponse)
def disable_schedule(
    schedule_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        schedule = service.set_enabled(schedule_id, False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.from_schedule(schedule)


@router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
def pause_schedule(
    schedule_id: str,
    service: ScheduleService = Depends(get_schedule_service),
) -> ScheduleResponse:
    try:
        schedule = service.set_enabled(schedule_id, False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScheduleResponse.from_schedule(schedule)


@router.post("/{schedule_id}/run-now", response_model=CandleFetchJobResponse, status_code=status.HTTP_202_ACCEPTED)
def run_schedule_now(
    schedule_id: str,
    background_tasks: BackgroundTasks,
    service: ScheduleService = Depends(get_schedule_service),
    fetch_job_service: CandleFetchJobService = Depends(get_candle_fetch_job_service),
) -> CandleFetchJobResponse:
    try:
        job = service.create_job_from_schedule(schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(fetch_job_service.run_job, job.id)
    return CandleFetchJobResponse.from_job(job)
