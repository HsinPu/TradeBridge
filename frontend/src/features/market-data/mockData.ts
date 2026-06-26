import type { CandleRow, CoverageRow, SyncActivity } from "./types";

export const coverageRows: CoverageRow[] = [
  {
    symbol: "BTC/USDT",
    interval: "1m",
    coveragePercent: 96,
    latestCandle: "2026-06-19 13:44",
    missingRanges: 2,
    health: "warning",
    segments: [
      { status: "available", width: 10 },
      { status: "available", width: 8 },
      { status: "available", width: 9 },
      { status: "missing", width: 1 },
      { status: "available", width: 11 },
      { status: "available", width: 8 },
      { status: "available", width: 10 },
      { status: "missing", width: 1 },
      { status: "available", width: 9 },
      { status: "empty", width: 2 }
    ]
  },
  {
    symbol: "ETH/USDT",
    interval: "5m",
    coveragePercent: 99,
    latestCandle: "2026-06-19 13:40",
    missingRanges: 0,
    health: "healthy",
    segments: [
      { status: "available", width: 9 },
      { status: "available", width: 8 },
      { status: "available", width: 8 },
      { status: "available", width: 9 },
      { status: "available", width: 8 },
      { status: "available", width: 9 },
      { status: "available", width: 8 },
      { status: "available", width: 9 },
      { status: "available", width: 8 },
      { status: "empty", width: 1 }
    ]
  },
];

export const syncActivity: SyncActivity[] = [
  {
    key: "1",
    time: "13:44:10",
    source: "Binance",
    symbol: "BTC/USDT",
    interval: "1m",
    rows: 1000,
    status: "success",
    duration: "1.32 s"
  },
  {
    key: "2",
    time: "13:38:02",
    source: "Binance",
    symbol: "ETH/USDT",
    interval: "1m",
    rows: 1000,
    status: "success",
    duration: "1.28 s"
  },
  {
    key: "3",
    time: "13:12:48",
    source: "Binance",
    symbol: "BTC/USDT",
    interval: "5m",
    rows: 200,
    status: "success",
    duration: "820 ms"
  },
  {
    key: "4",
    time: "13:02:55",
    source: "Binance",
    symbol: "ETH/USDT",
    interval: "5m",
    rows: 200,
    status: "success",
    duration: "790 ms"
  }
];

export const candleRows: CandleRow[] = [
  {
    key: "1",
    time: "2024-05-17 15:30:00",
    open: 66780.12,
    high: 66920.35,
    low: 66720.01,
    close: 66892.41,
    volume: 1.287,
    trades: 3842,
    source: "Binance"
  },
  {
    key: "2",
    time: "2024-05-17 15:15:00",
    open: 66701.55,
    high: 66810.0,
    low: 66650.12,
    close: 66780.12,
    volume: 1.124,
    trades: 3210,
    source: "Binance"
  },
  {
    key: "3",
    time: "2024-05-17 15:00:00",
    open: 66654.21,
    high: 66750.0,
    low: 66520.0,
    close: 66701.55,
    volume: 1.356,
    trades: 3566,
    source: "Binance"
  },
  {
    key: "4",
    time: "2024-05-17 14:45:00",
    open: 66420.1,
    high: 66690.0,
    low: 66360.0,
    close: 66654.21,
    volume: 1.098,
    trades: 3128,
    source: "Binance"
  },
  {
    key: "5",
    time: "2024-05-17 14:30:00",
    open: 66510.0,
    high: 66655.0,
    low: 66300.0,
    close: 66420.1,
    volume: 1.205,
    trades: 3276,
    source: "Binance"
  }
];

export const candleBars = [
  { open: 42, close: 46, high: 58, low: 36, volume: 28 },
  { open: 46, close: 39, high: 50, low: 32, volume: 34 },
  { open: 39, close: 52, high: 61, low: 35, volume: 41 },
  { open: 52, close: 50, high: 59, low: 45, volume: 36 },
  { open: 50, close: 57, high: 65, low: 48, volume: 45 },
  { open: 57, close: 63, high: 71, low: 55, volume: 62 },
  { open: 63, close: 66, high: 76, low: 60, volume: 78 },
  { open: 66, close: 61, high: 72, low: 56, volume: 54 },
  { open: 61, close: 59, high: 65, low: 50, volume: 38 },
  { open: 59, close: 52, high: 62, low: 45, volume: 44 },
  { open: 52, close: 56, high: 64, low: 49, volume: 39 },
  { open: 56, close: 58, high: 66, low: 53, volume: 46 },
  { open: 58, close: 64, high: 70, low: 55, volume: 57 },
  { open: 64, close: 62, high: 69, low: 58, volume: 32 },
  { open: 62, close: 67, high: 74, low: 59, volume: 51 },
  { open: 67, close: 65, high: 73, low: 61, volume: 49 },
  { open: 65, close: 69, high: 75, low: 63, volume: 43 },
  { open: 69, close: 68, high: 76, low: 64, volume: 58 },
  { open: 68, close: 63, high: 71, low: 58, volume: 83 },
  { open: 63, close: 61, high: 68, low: 56, volume: 45 },
  { open: 61, close: 59, high: 66, low: 55, volume: 37 },
  { open: 59, close: 56, high: 63, low: 52, volume: 33 },
  { open: 56, close: 54, high: 60, low: 49, volume: 42 },
  { open: 54, close: 55, high: 61, low: 51, volume: 29 },
  { open: 55, close: 58, high: 63, low: 53, volume: 31 },
  { open: 58, close: 57, high: 64, low: 54, volume: 36 },
  { open: 57, close: 60, high: 66, low: 55, volume: 40 },
  { open: 60, close: 62, high: 69, low: 58, volume: 48 },
  { open: 62, close: 61, high: 68, low: 56, volume: 35 },
  { open: 61, close: 59, high: 65, low: 54, volume: 30 },
  { open: 59, close: 58, high: 64, low: 53, volume: 34 },
  { open: 58, close: 57, high: 63, low: 52, volume: 28 },
  { open: 57, close: 59, high: 66, low: 55, volume: 36 },
  { open: 59, close: 61, high: 68, low: 57, volume: 44 },
  { open: 61, close: 60, high: 66, low: 56, volume: 32 },
  { open: 60, close: 64, high: 71, low: 58, volume: 52 }
];
