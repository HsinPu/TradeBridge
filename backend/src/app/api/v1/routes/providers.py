import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.dependencies import (
    get_market_data_provider_registry,
    get_provider_data_source_repository,
    get_provider_market_discovery_service,
)
from app.application.models.provider_data_source import ProviderDataSourceConfig
from app.application.ports.provider_data_source_repository import ProviderDataSourceRepository
from app.application.services.provider_market_discovery_service import ProviderMarketDiscoveryService
from app.core.settings import Settings, get_settings
from app.domain.value_objects.provider import ProviderName, normalize_provider
from app.infrastructure.external.provider_registry import MarketDataProviderRegistry
from app.schemas.requests.providers import ProviderDataSourceUpdateRequest
from app.schemas.responses.providers import (
    ProviderDataSourceResponse,
    ProviderMarketResponse,
    ProviderMarketsResponse,
    ProviderStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_provider_health(provider_registry: MarketDataProviderRegistry, provider: ProviderName) -> bool:
    market_data_provider = provider_registry.get(provider)
    try:
        return market_data_provider.ping()
    except Exception:
        logger.exception("market data provider health check failed provider=%s", provider)
        return False


def _check_provider_health_from_config(
    provider_registry: MarketDataProviderRegistry,
    config: ProviderDataSourceConfig,
) -> bool:
    market_data_provider = provider_registry.create_from_config(config)
    try:
        return market_data_provider.ping()
    except Exception:
        logger.exception("market data provider health check failed provider=%s", config.provider)
        return False


def _get_default_provider_data_source_config(settings: Settings, provider: ProviderName) -> ProviderDataSourceConfig:
    if provider == "binance":
        return ProviderDataSourceConfig(
            provider=provider,
            market_type="spot",
            api_base_url=settings.binance_base_url,
            timeout_seconds=settings.binance_timeout_seconds,
            rate_limit_weight_per_minute=settings.market_data_rate_limit_weight_per_minute,
            retry_attempts=settings.market_data_retry_attempts,
            cooldown_ms=settings.market_data_cooldown_ms,
        )
    raise ValueError(f"Unsupported market data provider: {provider}.")


def _get_effective_provider_data_source_config(
    *,
    settings: Settings,
    repository: ProviderDataSourceRepository,
    provider: ProviderName,
) -> ProviderDataSourceConfig:
    saved_config = repository.get(provider=provider, market_type="spot")
    return saved_config or _get_default_provider_data_source_config(settings, provider)


@router.get("/status", response_model=ProviderStatusResponse)
def get_provider_status(
    provider_name: str | None = Query(default=None, alias="provider"),
    provider_registry: MarketDataProviderRegistry = Depends(get_market_data_provider_registry),
) -> ProviderStatusResponse:
    try:
        selected_provider = normalize_provider(provider_name or get_settings().market_data_default_provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProviderStatusResponse(
        provider=selected_provider,
        market_type="spot",
        healthy=_check_provider_health(provider_registry, selected_provider),
    )


@router.get("/data-source", response_model=ProviderDataSourceResponse)
def get_provider_data_source(
    provider_name: str | None = Query(default=None, alias="provider"),
    provider_registry: MarketDataProviderRegistry = Depends(get_market_data_provider_registry),
    data_source_repository: ProviderDataSourceRepository = Depends(get_provider_data_source_repository),
) -> ProviderDataSourceResponse:
    settings = get_settings()
    try:
        selected_provider = normalize_provider(provider_name or settings.market_data_default_provider)
        config = _get_effective_provider_data_source_config(
            settings=settings,
            repository=data_source_repository,
            provider=selected_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ProviderDataSourceResponse.from_config(
        config,
        healthy=_check_provider_health(provider_registry, selected_provider),
    )


@router.patch("/data-source", response_model=ProviderDataSourceResponse)
def update_provider_data_source(
    request: ProviderDataSourceUpdateRequest,
    provider_registry: MarketDataProviderRegistry = Depends(get_market_data_provider_registry),
    data_source_repository: ProviderDataSourceRepository = Depends(get_provider_data_source_repository),
) -> ProviderDataSourceResponse:
    try:
        config = request.to_config()
        saved_config = data_source_repository.upsert(config)
        provider_registry.clear(saved_config.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ProviderDataSourceResponse.from_config(
        saved_config,
        healthy=_check_provider_health(provider_registry, saved_config.provider),
    )


@router.post("/data-source/test", response_model=ProviderDataSourceResponse)
def test_provider_data_source(
    request: ProviderDataSourceUpdateRequest,
    provider_registry: MarketDataProviderRegistry = Depends(get_market_data_provider_registry),
) -> ProviderDataSourceResponse:
    try:
        config = request.to_config()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ProviderDataSourceResponse.from_config(
        config,
        healthy=_check_provider_health_from_config(provider_registry, config),
    )


@router.get("/markets", response_model=ProviderMarketsResponse)
def discover_provider_markets(
    provider_name: str | None = Query(default=None, alias="provider"),
    market_type: str = Query(default="spot"),
    quote_asset: str | None = Query(default="USDT"),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    discovery_service: ProviderMarketDiscoveryService = Depends(get_provider_market_discovery_service),
) -> ProviderMarketsResponse:
    selected_provider = provider_name or get_settings().market_data_default_provider
    try:
        markets = discovery_service.discover_markets(
            provider=selected_provider,
            market_type=market_type,
            quote_asset=quote_asset,
            search=search,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "market discovery failed provider=%s market_type=%s quote_asset=%s search=%s",
            selected_provider,
            market_type,
            quote_asset,
            search,
        )
        raise HTTPException(status_code=502, detail="Market data provider discovery failed.") from exc

    return ProviderMarketsResponse(
        provider=normalize_provider(str(selected_provider)),
        market_type=market_type.strip().lower(),
        quote_asset=quote_asset.strip().upper() if quote_asset else None,
        search=search.strip().upper() if search else None,
        count=len(markets),
        markets=[ProviderMarketResponse.from_market(market) for market in markets],
    )
