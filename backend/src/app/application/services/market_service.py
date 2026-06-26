from dataclasses import replace
from datetime import datetime, timezone
import logging
from uuid import uuid4

from app.application.models.market import Market, MarketCreateCommand, MarketUpdateCommand
from app.application.ports.market_repository import MarketRepository
from app.domain.value_objects.market_pair import MarketPair
from app.domain.value_objects.provider import normalize_provider

logger = logging.getLogger(__name__)


class MarketService:
    def __init__(self, *, market_repository: MarketRepository) -> None:
        self._market_repository = market_repository

    def create_market(self, command: MarketCreateCommand) -> Market:
        provider = normalize_provider(command.provider)
        pair = MarketPair.parse(command.market_pair)
        market_type = _normalize_market_type(command.market_type)
        if self._market_repository.find_by_identity(
            provider=provider,
            market_type=market_type,
            market_pair=pair.display,
        ):
            raise ValueError(f"Market already exists: {provider} {market_type} {pair.display}")
        created_at = _utcnow_iso()
        market = Market(
            id=uuid4().hex[:12],
            enabled=command.enabled,
            provider=provider,
            market_type=market_type,
            market_pair=pair.display,
            exchange_symbol=pair.exchange_symbol_for(provider),
            base_asset=pair.base_asset,
            quote_asset=pair.quote_asset,
            is_default=False,
            created_at=created_at,
            updated_at=created_at,
        )
        created = self._market_repository.create(market)
        if command.is_default:
            created = self._market_repository.set_default(
                market_id=created.id,
                provider=created.provider,
                market_type=created.market_type,
            )
        logger.info(
            "market created market_id=%s provider=%s market_type=%s market_pair=%s enabled=%s is_default=%s",
            created.id,
            created.provider,
            created.market_type,
            created.market_pair,
            created.enabled,
            created.is_default,
        )
        return created

    def get_market(self, market_id: str) -> Market:
        market = self._market_repository.get(market_id)
        if market is None:
            raise ValueError(f"Market not found: {market_id}")
        return market

    def list_markets(
        self,
        *,
        provider: str | None = None,
        enabled: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        selected_provider = normalize_provider(provider) if provider else None
        return self._market_repository.list_markets(
            provider=selected_provider,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )

    def update_market(self, market_id: str, command: MarketUpdateCommand) -> Market:
        current = self.get_market(market_id)
        provider = normalize_provider(command.provider) if command.provider else current.provider
        market_type = _normalize_market_type(command.market_type or current.market_type)
        pair = MarketPair.parse(command.market_pair) if command.market_pair else MarketPair.parse(current.market_pair)
        existing = self._market_repository.find_by_identity(
            provider=provider,
            market_type=market_type,
            market_pair=pair.display,
        )
        if existing is not None and existing.id != market_id:
            raise ValueError(f"Market already exists: {provider} {market_type} {pair.display}")
        updated = replace(
            current,
            enabled=current.enabled if command.enabled is None else command.enabled,
            provider=provider,
            market_type=market_type,
            market_pair=pair.display,
            exchange_symbol=pair.exchange_symbol_for(provider),
            base_asset=pair.base_asset,
            quote_asset=pair.quote_asset,
            is_default=current.is_default if command.is_default is None else command.is_default,
        )
        if command.is_default is True:
            updated = replace(updated, is_default=False)
            self._market_repository.update(updated)
            return self._market_repository.set_default(
                market_id=market_id,
                provider=provider,
                market_type=market_type,
            )
        return self._market_repository.update(updated)

    def set_default(self, market_id: str) -> Market:
        market = self.get_market(market_id)
        return self._market_repository.set_default(
            market_id=market.id,
            provider=market.provider,
            market_type=market.market_type,
        )

    def delete_market(self, market_id: str) -> None:
        if not self._market_repository.delete(market_id):
            raise ValueError(f"Market not found: {market_id}")


def _normalize_market_type(value: str) -> str:
    market_type = value.strip().lower()
    if market_type != "spot":
        raise ValueError("Only spot markets are currently supported.")
    return market_type


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
