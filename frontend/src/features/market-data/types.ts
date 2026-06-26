export type ProviderHealth = "healthy" | "warning" | "error";

export type CoverageSegment = {
  status: "available" | "missing" | "empty";
  width: number;
};

export type CoverageRow = {
  symbol: string;
  interval: string;
  coveragePercent: number;
  latestCandle: string;
  missingRanges: number | null;
  health: ProviderHealth;
  segments: CoverageSegment[];
  dateLabels?: string[];
};

export type SyncActivity = {
  key: string;
  time: string;
  source: string;
  symbol: string;
  interval: string;
  rows: number;
  status: "success" | "warning" | "failed";
  duration: string;
};

export type CandleRow = {
  key: string;
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trades: number;
  source: string;
};

export type PriceSnapshot = {
  label: string;
  value: string;
  detail: string;
  trend: string;
  sparkline: number[];
  tone: "neutral" | "success" | "warning" | "danger";
};
