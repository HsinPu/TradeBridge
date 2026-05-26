# TradeBridge

CLI-first market data collector for crypto trading research.

TradeBridge v1 collects Binance USD-M Futures candlestick data and stores it in
a local SQLite database. Order execution, accounts, risk guards, and AI decision
logic are left for later versions.

## Quick Start

```powershell
$env:PYTHONPATH="src"
python -m tradebridge.cli backfill --symbol BTCUSDT --timeframe 1m --start 2026-01-01 --end 2026-01-02
python -m tradebridge.cli collect --symbol BTCUSDT --timeframe 1m
python -m tradebridge.cli summary
python -m tradebridge.cli candles --symbol BTCUSDT --timeframe 1m --limit 10
```

The backfill command fills a historical time range. The collect command only
continues from the latest stored candle and brings the database up to date.
Both commands write candles into `data/tradebridge.db`.

## Development

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```
