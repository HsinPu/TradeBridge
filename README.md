# TradeBridge

CLI-first market data collector for crypto trading research.

TradeBridge v1 collects Binance USD-M Futures candlestick data and stores it in
a local SQLite database. Order execution, accounts, risk guards, and AI decision
logic are left for later versions.

## Quick Start

```powershell
$env:PYTHONPATH="src"
python -m tradebridge.cli collect --symbol BTCUSDT --timeframe 1m --limit 1000
```

The command writes candles into `data/tradebridge.db`.

## Development

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```
