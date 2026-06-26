from dataclasses import dataclass

from app.domain.value_objects.provider import normalize_provider


@dataclass(frozen=True)
class MarketPair:
    base_asset: str
    quote_asset: str

    @classmethod
    def parse(cls, value: str) -> "MarketPair":
        normalized = value.strip().upper().replace("-", "/")
        parts = normalized.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("Market pair must use BASE/QUOTE format, for example BTC/USDT.")
        return cls(base_asset=parts[0], quote_asset=parts[1])

    @property
    def display(self) -> str:
        return f"{self.base_asset}/{self.quote_asset}"

    @property
    def exchange_symbol(self) -> str:
        return self.exchange_symbol_for("binance")

    def exchange_symbol_for(self, provider: str) -> str:
        provider_name = normalize_provider(provider)
        if provider_name == "binance":
            return f"{self.base_asset}{self.quote_asset}"
        raise ValueError(f"Unsupported market data provider: {provider_name}.")
