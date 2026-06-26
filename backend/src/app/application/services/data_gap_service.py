from app.application.models.data_gap import DATA_GAP_STATUSES, DataGap, DataGapSummary
from app.application.ports.data_gap_repository import DataGapRepository
from app.domain.value_objects.provider import normalize_provider


class DataGapService:
    def __init__(self, repository: DataGapRepository) -> None:
        self._repository = repository

    def list_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DataGap]:
        selected_provider = normalize_provider(provider) if provider else None
        self._validate_status_filter(status)
        return self._repository.list_gaps(
            provider=selected_provider,
            market_pair=market_pair,
            interval=interval,
            status=status,
            limit=limit,
            offset=offset,
        )

    def count_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        status: list[str] | None = None,
    ) -> int:
        selected_provider = normalize_provider(provider) if provider else None
        self._validate_status_filter(status)
        return self._repository.count_gaps(
            provider=selected_provider,
            market_pair=market_pair,
            interval=interval,
            status=status,
        )

    def summarize_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
    ) -> DataGapSummary:
        selected_provider = normalize_provider(provider) if provider else None
        return self._repository.summarize_gaps(
            provider=selected_provider,
            market_pair=market_pair,
            interval=interval,
        )

    def _validate_status_filter(self, status: list[str] | None) -> None:
        if not status:
            return
        invalid = sorted(set(status) - DATA_GAP_STATUSES)
        if invalid:
            raise ValueError(f"Unsupported data gap status: {', '.join(invalid)}.")
