from typing import Literal, TypeAlias, cast

ProviderName: TypeAlias = Literal["binance"]

DEFAULT_PROVIDER: ProviderName = "binance"
SUPPORTED_PROVIDER_NAMES: tuple[ProviderName, ...] = ("binance",)


def normalize_provider(value: str) -> ProviderName:
    provider = value.strip().lower()
    if provider not in SUPPORTED_PROVIDER_NAMES:
        supported = ", ".join(SUPPORTED_PROVIDER_NAMES)
        raise ValueError(f"Unsupported market data provider: {value}. Supported providers: {supported}.")
    return cast(ProviderName, provider)
