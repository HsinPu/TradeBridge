"""Small Binance USD-M Futures REST client."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tradebridge.exchange.models import Candle


class BinanceFuturesClient:
    """Fetch public market data from Binance USD-M Futures."""

    def __init__(self, base_url: str = "https://fapi.binance.com", timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Candle]:
        if limit <= 0 or limit > 1500:
            raise ValueError("limit must be between 1 and 1500")

        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        url = f"{self.base_url}/fapi/v1/klines?{urlencode(params)}"
        payload = self._get_json(url)
        return [Candle.from_binance_row(row) for row in payload]

    def _get_json(self, url: str) -> object:
        request = Request(url, headers={"User-Agent": "TradeBridge/0.1"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Binance request failed: HTTP {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Binance request failed: {exc.reason}") from exc

        return json.loads(body)
