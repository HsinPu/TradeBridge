from app.application.models.data_gap import DataGapSummary
from app.application.models.fetch_job import CandleFetchJob, CandleFetchJobOverview, CandleFetchJobSummary
from app.application.models.market import Market
from app.application.services.dashboard_service import DashboardService


class FakeMarketService:
    def __init__(self) -> None:
        self.list_args: dict[str, object] | None = None

    def list_markets(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        self.list_args = {
            "provider": provider,
            "enabled": enabled,
            "limit": limit,
            "offset": offset,
        }
        return [
            _make_market("BTC/USDT", "BTCUSDT"),
            _make_market("ETH/USDT", "ETHUSDT"),
        ]


class FakeCandleService:
    def __init__(self) -> None:
        self.coverage_args: list[dict[str, object]] = []

    def coverage(self, *, provider: str, market_pair: str, interval: str) -> dict[str, int | str | None]:
        self.coverage_args.append(
            {
                "provider": provider,
                "market_pair": market_pair,
                "interval": interval,
            }
        )
        if market_pair == "BTC/USDT":
            return _make_coverage(
                market_pair=market_pair,
                exchange_symbol="BTCUSDT",
                candle_count=100,
                last_open_time_ms=120_000,
                last_fetched_at="2026-06-21T10:00:00+00:00",
            )
        return _make_coverage(
            market_pair=market_pair,
            exchange_symbol="ETHUSDT",
            candle_count=0,
            last_open_time_ms=None,
            last_fetched_at=None,
        )


class FakeFetchJobService:
    def __init__(self) -> None:
        self.summary_args: dict[str, object] | None = None
        self.overview_args: dict[str, object] | None = None

    def summarize_jobs(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
        search: str | None = None,
        timezone_name: str = "UTC",
    ) -> CandleFetchJobSummary:
        self.summary_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
            "timezone_name": timezone_name,
        }
        return CandleFetchJobSummary(
            total_count=7,
            running_count=1,
            queued_count=2,
            completed_today_count=3,
            failed_count=4,
            timezone=timezone_name,
            today_start_time_ms=0,
            today_end_time_ms=86_400_000,
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
        self.overview_args = {
            "provider": provider,
            "market_pair": market_pair,
            "interval": interval,
            "search": search,
            "recent_limit": recent_limit,
        }
        return CandleFetchJobOverview(
            recent_jobs=[_make_job("job-1")],
            latest_failed_job=None,
            failed_count=4,
        )


class FakeDataGapRepository:
    def __init__(self) -> None:
        self.summary_args: list[dict[str, object]] = []

    def summarize_gaps(
        self,
        *,
        provider: str | None = None,
        market_pair: str | None = None,
        interval: str | None = None,
    ) -> DataGapSummary:
        self.summary_args.append(
            {
                "provider": provider,
                "market_pair": market_pair,
                "interval": interval,
            }
        )
        if market_pair == "BTC/USDT":
            return DataGapSummary(
                total_count=31,
                detected_count=30,
                repairing_count=0,
                resolved_count=0,
                official_empty_count=0,
                failed_count=1,
                active_missing_count=8088,
                first_active_gap_start_time_ms=1515034860000,
                first_active_gap_start_time="2018-01-04T03:01:00+00:00",
                last_checked_at="2026-06-26 00:31:52",
            )
        return DataGapSummary(
            total_count=0,
            detected_count=0,
            repairing_count=0,
            resolved_count=0,
            official_empty_count=0,
            failed_count=0,
            active_missing_count=0,
            first_active_gap_start_time_ms=None,
            first_active_gap_start_time=None,
            last_checked_at=None,
        )


class FakeProvider:
    def ping(self) -> bool:
        return True


class FakeProviderResolver:
    def __init__(self) -> None:
        self.provider: str | None = None

    def get(self, provider: str) -> FakeProvider:
        self.provider = provider
        return FakeProvider()


def test_dashboard_service_builds_overview_with_gap_summary() -> None:
    market_service = FakeMarketService()
    candle_service = FakeCandleService()
    fetch_job_service = FakeFetchJobService()
    data_gap_repository = FakeDataGapRepository()
    provider_resolver = FakeProviderResolver()
    service = DashboardService(
        market_service=market_service,
        candle_service=candle_service,
        fetch_job_service=fetch_job_service,
        provider_resolver=provider_resolver,
        data_gap_repository=data_gap_repository,
        default_timezone="Asia/Taipei",
    )

    overview = service.get_overview(
        provider="binance",
        interval="1m",
        market_limit=10,
        activity_limit=5,
    )

    assert market_service.list_args == {
        "provider": "binance",
        "enabled": True,
        "limit": 10,
        "offset": 0,
    }
    assert candle_service.coverage_args == [
        {"provider": "binance", "market_pair": "BTC/USDT", "interval": "1m"},
        {"provider": "binance", "market_pair": "ETH/USDT", "interval": "1m"},
    ]
    assert overview.metrics.tracked_market_count == 2
    assert overview.metrics.stored_candle_count == 100
    assert overview.metrics.latest_sync_at == "2026-06-21T10:00:00+00:00"
    assert overview.metrics.latest_candle_time_ms == 120_000
    assert overview.metrics.data_gap_count == 8088
    assert overview.metrics.data_gap_failed_count == 1
    assert overview.metrics.data_gap_repairing_count == 0
    assert overview.metrics.first_data_gap_time_ms == 1515034860000
    assert overview.metrics.gap_check_status == "repair_failed"
    assert overview.coverage[0].missing_count == 8088
    assert overview.coverage[0].gap_check_status == "repair_failed"
    assert overview.coverage[0].health == "error"
    assert overview.coverage[1].health == "warning"
    assert data_gap_repository.summary_args == [
        {"provider": "binance", "market_pair": "BTC/USDT", "interval": "1m"},
        {"provider": "binance", "market_pair": "ETH/USDT", "interval": "1m"},
    ]
    assert fetch_job_service.summary_args == {
        "provider": "binance",
        "market_pair": None,
        "interval": None,
        "search": None,
        "timezone_name": "Asia/Taipei",
    }
    assert fetch_job_service.overview_args == {
        "provider": "binance",
        "market_pair": None,
        "interval": None,
        "search": None,
        "recent_limit": 5,
    }
    assert provider_resolver.provider == "binance"
    assert overview.provider_status.healthy is True


def _make_market(market_pair: str, exchange_symbol: str) -> Market:
    base_asset, quote_asset = market_pair.split("/")
    return Market(
        id=f"{base_asset.lower()}-{quote_asset.lower()}",
        enabled=True,
        provider="binance",
        market_type="spot",
        market_pair=market_pair,
        exchange_symbol=exchange_symbol,
        base_asset=base_asset,
        quote_asset=quote_asset,
        is_default=market_pair == "BTC/USDT",
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:00+00:00",
    )


def _make_coverage(
    *,
    market_pair: str,
    exchange_symbol: str,
    candle_count: int,
    last_open_time_ms: int | None,
    last_fetched_at: str | None,
) -> dict[str, int | str | None]:
    return {
        "provider": "binance",
        "market_pair": market_pair,
        "exchange_symbol": exchange_symbol,
        "interval": "1m",
        "candle_count": candle_count,
        "first_open_time_ms": 0 if last_open_time_ms is not None else None,
        "last_open_time_ms": last_open_time_ms,
        "first_open_time": "1970-01-01T00:00:00+00:00" if last_open_time_ms is not None else None,
        "last_open_time": "1970-01-01T00:02:00+00:00" if last_open_time_ms is not None else None,
        "last_fetched_at": last_fetched_at,
    }


def _make_job(job_id: str) -> CandleFetchJob:
    return CandleFetchJob(
        id=job_id,
        job_type="candle_fetch",
        status="success",
        provider="binance",
        market_type="spot",
        market_pair="BTC/USDT",
        exchange_symbol="BTCUSDT",
        interval="1m",
        mode="backfill",
        requested_start_time_ms=0,
        requested_end_time_ms=60_000,
        effective_start_time_ms=0,
        effective_end_time_ms=60_000,
        current_cursor_time_ms=60_000,
        batch_limit=1000,
        overlap_candles=1,
        total_estimated_count=2,
        fetched_count=2,
        saved_count=2,
        failed_count=0,
        missing_count=0,
        completed_batch_count=1,
        total_batch_count=1,
        progress_percent=100.0,
        closed_only=True,
        verify_continuity=True,
        retry_attempts=3,
        retry_delay_seconds=1.0,
        error_message=None,
        started_at="2026-06-21T00:00:00+00:00",
        finished_at="2026-06-21T00:00:01+00:00",
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:01+00:00",
    )
