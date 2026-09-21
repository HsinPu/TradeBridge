import { MinuteDataPage } from "../features/collection/MinuteDataPage";
import {
  CheckCircleOutlined,
  CloseOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  DownloadOutlined,
  FullscreenOutlined,
  LoadingOutlined,
  MoreOutlined,
  ReloadOutlined,
  SettingOutlined,
  SyncOutlined,
  WarningOutlined
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Form,
  InputNumber,
  Modal,
  Progress,
  Radio,
  Row,
  Segmented,
  Select,
  Space,
  Table,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelCandleFetchJob,
  createCandleFetchJob,
  DEFAULT_MARKET_DATA_PROVIDER,
  getCandleCoverage,
  getCandleDetail,
  getDataGapSummary,
  getCandleFetchJob,
  getStorageSettings,
  MARKET_DATA_PROVIDER_LABELS,
  getProviderStatus,
  listDataGaps,
  listChartCandles,
  listCandles,
  listMarkets,
  pauseCandleFetchJob,
  repairDataGap,
  resumeCandleFetchJob
} from "../features/market-data/api";
import type {
  CandleCoverageResponse,
  CandleFetchResponse,
  CandleFetchJobResponse,
  CandleFetchMode,
  CandleListItemResponse,
  CandleResponse,
  DataGapResponse,
  DataGapSummaryResponse,
  ProviderStatusResponse
} from "../features/market-data/api";
import { CandlestickChart } from "../features/market-data/components/CandlestickChart";
import type { CandleRow } from "../features/market-data/types";
import type { AppMessages } from "../shared/i18n/messages";

const DEFAULT_MARKET_PAIR = "BTC/USDT";
const DEFAULT_INTERVAL = "1m";
const DEFAULT_LIMIT = 1000;
const MAX_LIMIT = 1000;
const CHART_VISIBLE_CANDLE_LIMIT = 80;
const DEFAULT_TABLE_PAGE_SIZE = 20;
const TABLE_PAGE_SIZE_OPTIONS = [20, 50, 100, 200] as const;
const TABLE_QUERY_DEBOUNCE_MS = 180;
const CHART_CACHE_MAX_ENTRIES = 12;
const DEFAULT_MARKET_PAIR_OPTIONS = ["BTC/USDT", "ETH/USDT"].map((value) => ({ value, label: value }));
const DATA_PAGE_STORAGE_KEY = "tradebridge.dataPage.preferences";

type DataPageProps = {
  messages: AppMessages;
};

type DateLikeValue = {
  toISOString: () => string;
};

type DateValue = DateLikeValue | null;

type FetchProgressStatus = "idle" | "running" | "paused" | "success" | "error" | "cancelled";

type FetchProgressState = {
  status: FetchProgressStatus;
  mode: CandleFetchMode;
  percent: number;
  elapsedSeconds: number;
  startedAtMs: number | null;
  job: CandleFetchJobResponse | null;
  directResult: CandleFetchResponse | null;
  errorMessage: string | null;
};

type FetchStepStatus = "waiting" | "active" | "done" | "error";

type FetchStep = {
  label: string;
  status: FetchStepStatus;
};

type DrawerMode = "fill-gaps" | "overwrite-range" | "delete-reload";

type DataPagePreferences = {
  marketPair: string;
  interval: string;
  limit: number;
  tablePageSize: number;
  mode: DrawerMode;
  refetchVerifyContinuity: boolean;
};

type TableQueryState = {
  marketPair: string;
  interval: string;
  page: number;
  pageSize: number;
};

type ChartCacheEntry = {
  candles: CandleListItemResponse[];
  cachedAtMs: number;
};

type DataCandleRow = CandleRow & {
  provider: string;
  marketType: string;
  marketPair: string;
  exchangeSymbol: string;
  interval: string;
  openTime: string;
  closeTime: string;
  openTimeMs: number;
  closeTimeMs: number;
  quoteVolume: number;
  takerBuyBaseVolume: number;
  takerBuyQuoteVolume: number;
  unusedValue: string;
  rawPayloadJson?: string | null;
};

type CandleDetailLoadState = {
  loading: boolean;
  candle: CandleResponse | null;
  errorMessage: string | null;
};

type FetchResultSummary = {
  mode: CandleFetchMode;
  fetchedCount: number;
  savedCount: number;
  missingCount: number;
  batchCount: number;
  completedAt: string;
};

const INITIAL_FETCH_PROGRESS: FetchProgressState = {
  status: "idle",
  mode: "auto",
  percent: 0,
  elapsedSeconds: 0,
  startedAtMs: null,
  job: null,
  directResult: null,
  errorMessage: null
};

const FETCH_STEP_DEFINITIONS = [
  { label: "建立抓取計畫", doneAt: 22 },
  { label: "抓取官方資料", doneAt: 68 },
  { label: "寫入資料庫", doneAt: 86 },
  { label: "驗證資料缺口", doneAt: 100 }
] as const;

function getCandleColumns(messages: AppMessages): ColumnsType<DataCandleRow> {
  return [
    { title: messages.data.table.time, dataIndex: "time", key: "time", width: 180 },
    {
      title: messages.data.table.open,
      dataIndex: "open",
      key: "open",
      width: 120,
      render: (value: number) => value.toLocaleString(undefined, { minimumFractionDigits: 2 })
    },
    {
      title: messages.data.table.high,
      dataIndex: "high",
      key: "high",
      width: 120,
      render: (value: number) => value.toLocaleString(undefined, { minimumFractionDigits: 2 })
    },
    {
      title: messages.data.table.low,
      dataIndex: "low",
      key: "low",
      width: 120,
      render: (value: number) => value.toLocaleString(undefined, { minimumFractionDigits: 2 })
    },
    {
      title: messages.data.table.close,
      dataIndex: "close",
      key: "close",
      width: 120,
      render: (value: number, row) => (
        <strong className={value >= row.open ? "positive-text" : "negative-text"}>
          {value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
        </strong>
      )
    },
    {
      title: messages.data.table.volume,
      dataIndex: "volume",
      key: "volume",
      width: 120,
      render: (value: number) =>
        value.toLocaleString(undefined, {
          maximumFractionDigits: 3
        })
    },
    { title: messages.data.table.trades, dataIndex: "trades", key: "trades", width: 120 },
    { title: messages.data.table.source, dataIndex: "source", key: "source", width: 120 }
  ];
}

function canRepairDataGap(gap: DataGapResponse) {
  return gap.status === "detected" || gap.status === "failed";
}

function getDataGapColumns(
  isEnglish: boolean,
  timezone: string,
  onRepair: (gap: DataGapResponse) => void,
  repairingGapId: string | null
): ColumnsType<DataGapResponse> {
  return [
    {
      title: isEnglish ? "Start" : "開始時間",
      dataIndex: "start_open_time",
      key: "start_open_time",
      width: 180,
      render: (value: string) => toDisplayDateTime(value, timezone)
    },
    {
      title: isEnglish ? "End" : "結束時間",
      dataIndex: "end_open_time",
      key: "end_open_time",
      width: 180,
      render: (value: string) => toDisplayDateTime(value, timezone)
    },
    {
      title: isEnglish ? "Missing" : "缺少",
      dataIndex: "missing_count",
      key: "missing_count",
      width: 110,
      render: (value: number) => formatInteger(value)
    },
    {
      title: isEnglish ? "Status" : "狀態",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (value: string) => getDataGapStatusLabel(value, isEnglish)
    },
    {
      title: "Job ID",
      dataIndex: "source_job_id",
      key: "source_job_id",
      width: 140,
      render: (value: string | null) => value ?? "--"
    },
    {
      title: isEnglish ? "Checked" : "檢查時間",
      dataIndex: "last_checked_at",
      key: "last_checked_at",
      width: 180,
      render: (value: string) => toDisplayDateTime(value, timezone)
    },
    {
      title: isEnglish ? "Action" : "操作",
      key: "action",
      width: 120,
      render: (_: unknown, record: DataGapResponse) => {
        const isSubmitting = repairingGapId === record.id;
        const isRepairing = record.status === "repairing";
        return (
          <Button
            icon={<SyncOutlined />}
            loading={isSubmitting}
            disabled={!canRepairDataGap(record) || isRepairing || (repairingGapId !== null && !isSubmitting)}
            size="small"
            onClick={() => onRepair(record)}
          >
            {isEnglish ? "Repair" : "修補"}
          </Button>
        );
      }
    }
  ];
}

function isDateLikeValue(value: unknown): value is DateLikeValue {
  return (
    typeof value === "object" &&
    value !== null &&
    "toISOString" in value &&
    typeof value.toISOString === "function"
  );
}

function normalizeStartDate(value: unknown): DateValue {
  return isDateLikeValue(value) ? value : null;
}

function toLocalStartOfDay(value: DateLikeValue) {
  const selectedDate = new Date(value.toISOString());
  return new Date(selectedDate.getFullYear(), selectedDate.getMonth(), selectedDate.getDate(), 0, 0, 0, 0);
}

function toLocalEndOfToday() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
}

function getHistoryDateParams(startDate: DateValue) {
  if (startDate === null) {
    return {};
  }

  return {
    start_time: toLocalStartOfDay(startDate).toISOString(),
    end_time: toLocalEndOfToday().toISOString()
  };
}

function toNumber(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function isTablePageSize(value: number): value is (typeof TABLE_PAGE_SIZE_OPTIONS)[number] {
  return TABLE_PAGE_SIZE_OPTIONS.includes(value as (typeof TABLE_PAGE_SIZE_OPTIONS)[number]);
}

function normalizeDrawerMode(value: unknown): DrawerMode {
  return value === "overwrite-range" || value === "delete-reload" ? value : "fill-gaps";
}

function getStoredDataPagePreferences(): DataPagePreferences {
  const defaults: DataPagePreferences = {
    marketPair: DEFAULT_MARKET_PAIR,
    interval: DEFAULT_INTERVAL,
    limit: DEFAULT_LIMIT,
    tablePageSize: DEFAULT_TABLE_PAGE_SIZE,
    mode: "fill-gaps",
    refetchVerifyContinuity: true,
  };

  if (typeof window === "undefined") {
    return defaults;
  }

  try {
    const rawValue = window.localStorage.getItem(DATA_PAGE_STORAGE_KEY);
    if (!rawValue) {
      return defaults;
    }

    const parsed = JSON.parse(rawValue) as Partial<DataPagePreferences>;
    const parsedLimit = typeof parsed.limit === "number" ? parsed.limit : defaults.limit;
    const parsedPageSize = typeof parsed.tablePageSize === "number" ? parsed.tablePageSize : defaults.tablePageSize;

    return {
      marketPair: typeof parsed.marketPair === "string" && parsed.marketPair ? parsed.marketPair : defaults.marketPair,
      interval: typeof parsed.interval === "string" && parsed.interval ? parsed.interval : defaults.interval,
      limit: Math.min(MAX_LIMIT, Math.max(1, parsedLimit)),
      tablePageSize: isTablePageSize(parsedPageSize) ? parsedPageSize : defaults.tablePageSize,
      mode: normalizeDrawerMode(parsed.mode),
      refetchVerifyContinuity:
        typeof parsed.refetchVerifyContinuity === "boolean"
          ? parsed.refetchVerifyContinuity
          : defaults.refetchVerifyContinuity,

    };
  } catch {
    return defaults;
  }
}

function normalizeTimezone(value: string | null | undefined) {
  const timezone = value?.trim() || "Asia/Taipei";
  try {
    new Intl.DateTimeFormat("sv-SE", { timeZone: timezone }).format(new Date());
    return timezone;
  } catch {
    return "Asia/Taipei";
  }
}

function parseApiDateTime(value: string) {
  if (value.includes("T")) {
    return new Date(value);
  }
  return new Date(`${value.replace(" ", "T")}Z`);
}

function toDisplayDateTime(value: string | null | undefined, timezone = "UTC") {
  if (!value) {
    return "--";
  }

  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) {
    return value.replace("T", " ").replace("Z", "").slice(0, 19);
  }

  return new Intl.DateTimeFormat("sv-SE", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: normalizeTimezone(timezone)
  }).format(date);
}

function formatPrice(value: number | null) {
  if (value === null || !Number.isFinite(value)) {
    return "--";
  }

  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatInteger(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "0";
  }

  return value.toLocaleString();
}

function formatLatency(value: number | null) {
  return value === null ? "--" : `${value} ms`;
}

function formatDuration(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;

  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

function getDataGapStatusLabel(status: string, isEnglish: boolean) {
  const labels: Record<string, { zh: string; en: string }> = {
    detected: { zh: "已偵測", en: "Detected" },
    repairing: { zh: "回補中", en: "Repairing" },
    resolved: { zh: "已補齊", en: "Resolved" },
    official_empty: { zh: "官方無資料", en: "Official empty" },
    failed: { zh: "回補失敗", en: "Failed" }
  };
  const label = labels[status];
  if (!label) {
    return status;
  }
  return isEnglish ? label.en : label.zh;
}

function getFetchModeLabel(mode: CandleFetchMode) {
  if (mode === "fill_gaps") {
    return "補齊缺口";
  }
  if (mode === "overwrite_range") {
    return "覆蓋範圍";
  }
  if (mode === "delete_reload") {
    return "刪除後重抓";
  }
  if (mode === "latest") {
    return "抓取最新";
  }
  if (mode === "backfill") {
    return "回補範圍";
  }

  return "自動抓取";
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }

  return "重新抓取失敗，請稍後再試。";
}

function getDataLoadErrorMessage(
  section: "provider" | "chart" | "coverage" | "table" | "gap",
  error: unknown,
  isEnglish: boolean
) {
  const detail = getErrorMessage(error);
  const labels = isEnglish
    ? {
        provider: "Data source status failed",
        chart: "Chart data failed",
        coverage: "Coverage summary failed",
        table: "Table data failed",
        gap: "Gap check failed"
      }
    : {
        provider: "資料來源狀態讀取失敗",
        chart: "圖表資料讀取失敗",
        coverage: "資料摘要讀取失敗",
        table: "表格資料讀取失敗",
        gap: "缺口檢查失敗"
      };

  return `${labels[section]}: ${detail}`;
}

function getFetchSteps(progress: FetchProgressState): FetchStep[] {
  const activeIndex = FETCH_STEP_DEFINITIONS.findIndex((step) => progress.percent < step.doneAt);
  const currentIndex = activeIndex === -1 ? FETCH_STEP_DEFINITIONS.length - 1 : activeIndex;

  return FETCH_STEP_DEFINITIONS.map((step, index) => {
    if (progress.status === "success") {
      return { label: step.label, status: "done" };
    }
    if ((progress.status === "error" || progress.status === "cancelled") && index === currentIndex) {
      return { label: step.label, status: "error" };
    }
    if ((progress.status === "error" || progress.status === "cancelled") && index < currentIndex) {
      return { label: step.label, status: "done" };
    }
    if (progress.percent >= step.doneAt) {
      return { label: step.label, status: "done" };
    }
    if (index === currentIndex) {
      return { label: step.label, status: "active" };
    }

    return { label: step.label, status: "waiting" };
  });
}

function getProgressStatusText(progress: FetchProgressState, timezone: string) {
  if (progress.job?.status === "pending") return "排隊中 / Queued";
  if (progress.job?.status === "pausing") return "暫停中 / Pausing";
  if (progress.job?.status === "cancelling") return "取消中 / Cancelling";
  if (progress.job?.recovery_count && progress.job.status === "running") return "已恢復執行 / Recovered";
  if (progress.status === "success") {
    return "資料已完成寫入並驗證缺口";
  }
  if (progress.status === "paused") {
    return "抓取任務已暫停，可稍後恢復。";
  }
  if (progress.status === "cancelled") {
    return "抓取任務已中止。";
  }
  if (progress.status === "error") {
    return progress.errorMessage ?? "重新抓取失敗";
  }
  if (progress.job?.current_cursor_time) {
    return `正在批次抓取，已推進到 ${toDisplayDateTime(progress.job.current_cursor_time, timezone)}`;
  }
  if (progress.percent < 24) {
    return "正在建立抓取計畫...";
  }
  if (progress.percent < 70) {
    return "正在向資料來源取得 K 線資料...";
  }
  if (progress.percent < 88) {
    return "正在寫入資料庫...";
  }

  return "正在驗證資料缺口...";
}

function getChartCacheKey(provider: string, marketPair: string, interval: string) {
  return [provider, marketPair, interval].join("|");
}

function setChartCacheEntry(cache: Map<string, ChartCacheEntry>, key: string, candles: CandleListItemResponse[]) {
  if (cache.has(key)) {
    cache.delete(key);
  }
  cache.set(key, {
    candles,
    cachedAtMs: Date.now()
  });

  while (cache.size > CHART_CACHE_MAX_ENTRIES) {
    const oldestKey = cache.keys().next().value;
    if (!oldestKey) {
      return;
    }
    cache.delete(oldestKey);
  }
}

function mapCandleToRow(candle: CandleListItemResponse | CandleResponse, timezone: string): DataCandleRow {
  return {
    key: `${candle.exchange_symbol}-${candle.interval}-${candle.open_time_ms}`,
    time: toDisplayDateTime(candle.open_time, timezone),
    open: toNumber(candle.open_price),
    high: toNumber(candle.high_price),
    low: toNumber(candle.low_price),
    close: toNumber(candle.close_price),
    volume: toNumber(candle.base_volume),
    trades: candle.trade_count,
    source: getProviderLabel(candle.provider),
    provider: candle.provider,
    marketType: candle.market_type,
    marketPair: candle.market_pair,
    exchangeSymbol: candle.exchange_symbol,
    interval: candle.interval,
    openTime: toDisplayDateTime(candle.open_time, timezone),
    closeTime: toDisplayDateTime(candle.close_time, timezone),
    openTimeMs: candle.open_time_ms,
    closeTimeMs: candle.close_time_ms,
    quoteVolume: toNumber(candle.quote_volume),
    takerBuyBaseVolume: toNumber(candle.taker_buy_base_volume),
    takerBuyQuoteVolume: toNumber(candle.taker_buy_quote_volume),
    unusedValue: candle.unused_value,
    rawPayloadJson: "raw_payload_json" in candle ? candle.raw_payload_json : null
  };
}

function getProviderLabel(provider: string) {
  return provider === DEFAULT_MARKET_DATA_PROVIDER
    ? MARKET_DATA_PROVIDER_LABELS[DEFAULT_MARKET_DATA_PROVIDER]
    : provider;
}

function getOhlcSummary(candles: CandleRow[]) {
  const latest = candles.at(-1);
  if (!latest) {
    return "O --  H --  L --  C --";
  }

  const change = latest.close - latest.open;
  const changePercent = latest.open === 0 ? 0 : (change / latest.open) * 100;
  const sign = change >= 0 ? "+" : "";
  return [
    `O ${formatPrice(latest.open)}`,
    `H ${formatPrice(latest.high)}`,
    `L ${formatPrice(latest.low)}`,
    `C ${formatPrice(latest.close)}`,
    `${sign}${formatPrice(change)} (${sign}${changePercent.toFixed(2)}%)`
  ].join("  ");
}

function getTableFooter(page: number, pageSize: number, count: number, total: number | null | undefined) {
  if (count === 0) {
    return `0 / ${formatInteger(total ?? 0)}`;
  }

  const start = (page - 1) * pageSize + 1;
  const end = start + count - 1;
  return `${start.toLocaleString()} - ${end.toLocaleString()} / ${formatInteger(total ?? count)}`;
}

function getDataPageLocalCopy(messages: AppMessages) {
  const isEnglish = messages.data.title === "Market Data";

  return {
    rowsPerPage: isEnglish ? "Rows per page" : "每頁筆數",
    loadedRows: isEnglish ? "Loaded rows" : "已載入筆數",
    chartNoData: isEnglish ? "No chart data" : "尚無圖表資料",
    fillGapsNotice: isEnglish
      ? "Only missing ranges will be fetched and stored."
      : "只會抓取缺漏範圍並寫入資料庫。",
    confirmDangerTitle: isEnglish ? "Confirm re-fetch mode" : "確認重新抓取模式",
    confirmDangerContent: isEnglish
      ? "Overwrite or delete mode will change existing data in the selected range."
      : "覆蓋或刪除模式會修改選取範圍內的既有資料。",
    confirmDangerOk: isEnglish ? "Continue" : "繼續執行",
    confirmDangerCancel: isEnglish ? "Cancel" : "取消",
    backgroundRun: isEnglish ? "Background" : "背景任務",
    directRun: isEnglish ? "Direct" : "直接執行",
    chartShowingAll: (count: number) =>
      isEnglish ? `Showing ${count.toLocaleString()} candles` : `顯示 ${count.toLocaleString()} 根`,
    chartShowingLatest: (visibleCount: number, totalCount: number) =>
      isEnglish
        ? `Latest ${visibleCount.toLocaleString()} of ${totalCount.toLocaleString()}`
        : `最近 ${visibleCount.toLocaleString()} / 全部 ${totalCount.toLocaleString()} 根`
  };
}

function getChartWindowLabel(visibleCount: number, totalCount: number, copy: ReturnType<typeof getDataPageLocalCopy>) {
  if (totalCount === 0) {
    return copy.chartNoData;
  }

  if (visibleCount >= totalCount) {
    return copy.chartShowingAll(totalCount);
  }

  return copy.chartShowingLatest(visibleCount, totalCount);
}

function formatDetailNumber(value: number, fractionDigits = 8) {
  if (!Number.isFinite(value)) {
    return "--";
  }

  return value.toLocaleString(undefined, {
    maximumFractionDigits: fractionDigits
  });
}

function formatRawPayload(rawPayloadJson: string) {
  try {
    return JSON.stringify(JSON.parse(rawPayloadJson), null, 2);
  } catch {
    return rawPayloadJson || "--";
  }
}

function isAbortError(error: unknown) {
  return error instanceof Error && error.name === "AbortError";
}

function getFetchSummaryText(summary: FetchResultSummary, isEnglish: boolean) {
  if (isEnglish) {
    return [
      `Fetch completed at ${summary.completedAt}.`,
      `Fetched ${formatInteger(summary.fetchedCount)}, saved ${formatInteger(summary.savedCount)}, missing ${formatInteger(
        summary.missingCount
      )}, batches ${formatInteger(summary.batchCount)}.`
    ].join(" ");
  }

  return [
    `抓取完成：${summary.completedAt}`,
    `抓到 ${formatInteger(summary.fetchedCount)} 筆，寫入 ${formatInteger(summary.savedCount)} 筆，缺口 ${formatInteger(
      summary.missingCount
    )} 筆，批次 ${formatInteger(summary.batchCount)}。`
  ].join(" ");
}

function renderCandleDetails(row: DataCandleRow, detailState?: CandleDetailLoadState) {
  const detailItems = [
    ["Provider", row.source],
    ["Market", row.marketPair],
    ["Market Type", row.marketType],
    ["Exchange Symbol", row.exchangeSymbol],
    ["Interval", row.interval],
    ["Open Time", row.openTime],
    ["Close Time", row.closeTime],
    ["Open Time MS", row.openTimeMs.toLocaleString()],
    ["Close Time MS", row.closeTimeMs.toLocaleString()],
    ["Base Volume", formatDetailNumber(row.volume)],
    ["Quote Volume", formatDetailNumber(row.quoteVolume)],
    ["Trade Count", row.trades.toLocaleString()],
    ["Taker Buy Base", formatDetailNumber(row.takerBuyBaseVolume)],
    ["Taker Buy Quote", formatDetailNumber(row.takerBuyQuoteVolume)],
    ["Unused", row.unusedValue || "--"]
  ];
  const rawPayloadJson = detailState?.candle?.raw_payload_json ?? row.rawPayloadJson ?? "";
  const rawPayload = detailState?.loading
    ? "Loading raw payload..."
    : detailState?.errorMessage
      ? detailState.errorMessage
      : formatRawPayload(rawPayloadJson);

  return (
    <div className="candle-detail-panel">
      <div className="candle-detail-grid">
        {detailItems.map(([label, value]) => (
          <div className="candle-detail-item" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="candle-raw-payload">
        <span>Raw Payload</span>
        <pre>{rawPayload}</pre>
      </div>
    </div>
  );
}

function getDrawerFetchMode(mode: string): CandleFetchMode {
  if (mode === "fill-gaps") {
    return "fill_gaps";
  }
  if (mode === "overwrite-range") {
    return "overwrite_range";
  }
  if (mode === "delete-reload") {
    return "delete_reload";
  }

  return "auto";
}

function getJobRequestMode(mode: CandleFetchMode): Exclude<CandleFetchMode, "latest"> {
  return mode === "latest" ? "backfill" : mode;
}

function confirmDangerousFetch(
  fetchMode: CandleFetchMode,
  copy: ReturnType<typeof getDataPageLocalCopy>
): Promise<boolean> {
  if (fetchMode !== "overwrite_range" && fetchMode !== "delete_reload") {
    return Promise.resolve(true);
  }

  return new Promise((resolve) => {
    Modal.confirm({
      title: copy.confirmDangerTitle,
      content: copy.confirmDangerContent,
      okText: copy.confirmDangerOk,
      okType: "danger",
      cancelText: copy.confirmDangerCancel,
      onOk: () => resolve(true),
      onCancel: () => resolve(false)
    });
  });
}

function getProgressStatusFromJob(status: CandleFetchJobResponse["status"]): FetchProgressStatus {
  if (status === "success") {
    return "success";
  }
  if (status === "paused") {
    return "paused";
  }
  if (status === "cancelled") {
    return "cancelled";
  }
  if (status === "failed") {
    return "error";
  }

  return "running";
}

export function DataPage({ messages }: DataPageProps) {
  const [source, setSource] = useState("minute");
  const english = messages.data.title === "Market Data";
  return <div className="page-stack">
    <Segmented aria-label={english ? "Data source" : "資料來源模式"} value={source} onChange={value => setSource(String(value))} options={[
      { value: "minute", label: english ? "Derived from 1-minute data" : "1 分鐘資料彙整" },
      { value: "legacy", label: english ? "Original interval data" : "原始週期資料" }
    ]} />
    {source === "minute" ? <MinuteDataPage english={english} /> : <RawDataPage messages={messages} />}
  </div>;
}

function RawDataPage({ messages }: DataPageProps) {
  const storedPreferences = useMemo(() => getStoredDataPagePreferences(), []);
  const hasLoadedPrimaryRef = useRef(false);
  const chartCacheRef = useRef(new Map<string, ChartCacheEntry>());
  const tableRequestIdRef = useRef(0);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [tableLoading, setTableLoading] = useState(false);
  const [dataRefreshing, setDataRefreshing] = useState(false);
  const [gapLoading, setGapLoading] = useState(false);
  const [gapError, setGapError] = useState<string | null>(null);
  const [dataLoadToken, setDataLoadToken] = useState(0);
  const [mode, setMode] = useState<DrawerMode>(storedPreferences.mode);
  const [tableQuery, setTableQuery] = useState<TableQueryState>({
    marketPair: storedPreferences.marketPair,
    interval: storedPreferences.interval,
    page: 1,
    pageSize: storedPreferences.tablePageSize
  });
  const [limit, setLimit] = useState(storedPreferences.limit);
  const [startDate, setStartDate] = useState<DateValue>(null);
  const [marketPairOptions, setMarketPairOptions] = useState(() => {
    if (DEFAULT_MARKET_PAIR_OPTIONS.some((option) => option.value === storedPreferences.marketPair)) {
      return DEFAULT_MARKET_PAIR_OPTIONS;
    }
    return [{ value: storedPreferences.marketPair, label: storedPreferences.marketPair }, ...DEFAULT_MARKET_PAIR_OPTIONS];
  });
  const [timezone, setTimezone] = useState("Asia/Taipei");
  const [providerStatus, setProviderStatus] = useState<ProviderStatusResponse | null>(null);
  const [coverage, setCoverage] = useState<CandleCoverageResponse | null>(null);
  const [gapSummary, setGapSummary] = useState<DataGapSummaryResponse | null>(null);
  const [dataGaps, setDataGaps] = useState<DataGapResponse[]>([]);
  const [candleRows, setCandleRows] = useState<DataCandleRow[]>([]);
  const [chartCandleRows, setChartCandleRows] = useState<DataCandleRow[]>([]);
  const [candleDetails, setCandleDetails] = useState<Record<string, CandleDetailLoadState>>({});
  const [candleTotalCount, setCandleTotalCount] = useState(0);
  const [refetchVerifyContinuity, setRefetchVerifyContinuity] = useState(storedPreferences.refetchVerifyContinuity);

  const [requestLatencyMs, setRequestLatencyMs] = useState<number | null>(null);
  const [lastRequestAt, setLastRequestAt] = useState<string | null>(null);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [tableError, setTableError] = useState<string | null>(null);
  const [lastFetchSummary, setLastFetchSummary] = useState<FetchResultSummary | null>(null);
  const [fetchProgressModalOpen, setFetchProgressModalOpen] = useState(false);
  const [fetchProgress, setFetchProgress] = useState<FetchProgressState>(INITIAL_FETCH_PROGRESS);
  const [repairingGapId, setRepairingGapId] = useState<string | null>(null);

  const modeWarning = useMemo(() => mode !== "fill-gaps", [mode]);
  const candleColumns = getCandleColumns(messages);
  const dataPageCopy = getDataPageLocalCopy(messages);
  const isEnglish = messages.data.title === "Market Data";
  const selectedProvider = DEFAULT_MARKET_DATA_PROVIDER;
  const selectedProviderLabel = MARKET_DATA_PROVIDER_LABELS[selectedProvider];
  const { marketPair, interval, page: tablePage, pageSize: tablePageSize } = tableQuery;
  const updateMarketPair = useCallback((nextMarketPair: string) => {
    setTableQuery((current) =>
      current.marketPair === nextMarketPair ? current : { ...current, marketPair: nextMarketPair, page: 1 }
    );
  }, []);
  const updateInterval = useCallback((nextInterval: string) => {
    setTableQuery((current) =>
      current.interval === nextInterval ? current : { ...current, interval: nextInterval, page: 1 }
    );
  }, []);
  const updateTablePage = useCallback((nextPage: number) => {
    setTableQuery((current) => (current.page === nextPage ? current : { ...current, page: nextPage }));
  }, []);
  const updateTablePageSize = useCallback((nextPageSize: number) => {
    setTableQuery((current) => {
      if (current.pageSize === nextPageSize && current.page === 1) {
        return current;
      }
      return { ...current, pageSize: nextPageSize, page: 1 };
    });
  }, []);
  const chartRows = useMemo(() => chartCandleRows.slice(-CHART_VISIBLE_CANDLE_LIMIT), [chartCandleRows]);
  const chartWindowLabel = getChartWindowLabel(chartRows.length, candleTotalCount, dataPageCopy);
  const tablePageSizeOptions = useMemo(
    () => TABLE_PAGE_SIZE_OPTIONS.map((value) => ({ value, label: value.toLocaleString() })),
    []
  );
  const latestCandle = chartRows.at(-1) ?? candleRows.at(-1) ?? null;
  const missingCount = gapSummary?.active_missing_count ?? 0;
  const providerIsHealthy = providerStatus?.healthy === true && providerError === null;
  const providerStatusLabel = providerIsHealthy ? "OK" : providerError || providerStatus?.healthy === false ? "ERROR" : "--";
  const hasDataLoadError = providerError !== null || chartError !== null || tableError !== null || gapError !== null;
  const chartTitle = `${marketPair} - ${interval} - ${selectedProviderLabel}`;
  const candleRowsTitle = messages.data.candleRows.replace(DEFAULT_MARKET_PAIR, marketPair);
  const missingRangeLabel =
    gapLoading
      ? isEnglish
        ? "Checking gaps in background"
        : "背景檢查缺口中"
      : gapError
        ? isEnglish
          ? "Gap check failed"
          : "缺口檢查失敗"
        : missingCount === 0
          ? messages.data.noGapsDetected
          : `${missingCount.toLocaleString()} ${messages.common.gaps}`;
  const canStartFetch = startDate !== null;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const preferences: DataPagePreferences = {
      marketPair,
      interval,
      limit,
      tablePageSize,
      mode,
      refetchVerifyContinuity,
    };

    window.localStorage.setItem(DATA_PAGE_STORAGE_KEY, JSON.stringify(preferences));
  }, [interval, limit, marketPair, mode, refetchVerifyContinuity, tablePageSize]);

  useEffect(() => {
    let ignore = false;

    async function loadTimezone() {
      try {
        const settings = await getStorageSettings();
        if (!ignore) {
          setTimezone(normalizeTimezone(settings.timezone));
        }
      } catch (error) {
        console.error(error);
      }
    }

    void loadTimezone();

    return () => {
      ignore = true;
    };
  }, []);

  const loadDataPage = useCallback(async (options: { forceChartRefresh?: boolean } = {}) => {
    const isInitialLoad = !hasLoadedPrimaryRef.current;
    const chartCacheKey = getChartCacheKey(selectedProvider, marketPair, interval);
    const cachedChart = options.forceChartRefresh ? null : chartCacheRef.current.get(chartCacheKey) ?? null;

    if (cachedChart) {
      setChartCandleRows(cachedChart.candles.map((candle) => mapCandleToRow(candle, timezone)));
    }

    setChartLoading(cachedChart === null);
    setDataRefreshing(!isInitialLoad);
    const startedAt = performance.now();
    try {
      const [providerStatusResult, coverageResult, chartCandleResult] = await Promise.allSettled([
        getProviderStatus(selectedProvider),
        getCandleCoverage({ provider: selectedProvider, market_pair: marketPair, interval }),
        cachedChart
          ? Promise.resolve({ candles: cachedChart.candles, fromCache: true })
          : listChartCandles({
              provider: selectedProvider,
              market_pair: marketPair,
              interval,
              limit: CHART_VISIBLE_CANDLE_LIMIT
            }).then((response) => ({ candles: response.candles, fromCache: false }))
      ]);

      let hasPrimaryData = false;
      let nextChartError: string | null = null;
      const appendChartError = (message: string) => {
        nextChartError = nextChartError ? `${nextChartError} ${message}` : message;
      };

      if (providerStatusResult.status === "fulfilled") {
        setProviderStatus(providerStatusResult.value);
        setProviderError(
          providerStatusResult.value.healthy ? null : isEnglish ? "Data source is not healthy." : "資料來源目前異常。"
        );
      } else {
        console.error(providerStatusResult.reason);
        setProviderError(getDataLoadErrorMessage("provider", providerStatusResult.reason, isEnglish));
      }

      if (coverageResult.status === "fulfilled") {
        setCoverage(coverageResult.value);
        setCandleTotalCount(coverageResult.value.candle_count);
        hasPrimaryData = true;
      } else {
        console.error(coverageResult.reason);
        appendChartError(getDataLoadErrorMessage("coverage", coverageResult.reason, isEnglish));
      }

      if (chartCandleResult.status === "fulfilled") {
        if (!chartCandleResult.value.fromCache) {
          setChartCacheEntry(chartCacheRef.current, chartCacheKey, chartCandleResult.value.candles);
        }
        setChartCandleRows(chartCandleResult.value.candles.map((candle) => mapCandleToRow(candle, timezone)));
        hasPrimaryData = true;
      } else {
        console.error(chartCandleResult.reason);
        appendChartError(getDataLoadErrorMessage("chart", chartCandleResult.reason, isEnglish));
      }
      setChartError(nextChartError);

      if (hasPrimaryData) {
        hasLoadedPrimaryRef.current = true;
        setDataLoadToken((current) => current + 1);
      }
      setRequestLatencyMs(Math.round(performance.now() - startedAt));
      setLastRequestAt(toDisplayDateTime(new Date().toISOString(), timezone));
    } catch (error) {
      console.error(error);
      const errorMessage = getDataLoadErrorMessage("chart", error, isEnglish);
      setProviderError(errorMessage);
      setChartError(errorMessage);
      setRequestLatencyMs(null);
      setLastRequestAt(toDisplayDateTime(new Date().toISOString(), timezone));
    } finally {
      setChartLoading(false);
      setDataRefreshing(false);
    }
  }, [interval, isEnglish, marketPair, selectedProvider, timezone]);

  const loadTablePage = useCallback(async (signal?: AbortSignal) => {
    const requestId = tableRequestIdRef.current + 1;
    tableRequestIdRef.current = requestId;
    const tableOffset = (tablePage - 1) * tablePageSize;
    setTableLoading(true);
    try {
      const candleResult = await listCandles({
        provider: selectedProvider,
        market_pair: marketPair,
        interval,
        limit: tablePageSize,
        offset: tableOffset,
        include_count: false
      }, {
        signal
      });

      if (signal?.aborted || requestId !== tableRequestIdRef.current) {
        return;
      }
      setCandleRows(candleResult.candles.map((candle) => mapCandleToRow(candle, timezone)));
      setCandleDetails({});
      setTableError(null);
    } catch (error) {
      if (isAbortError(error) || signal?.aborted || requestId !== tableRequestIdRef.current) {
        return;
      }
      console.error(error);
      setTableError(getDataLoadErrorMessage("table", error, isEnglish));
    } finally {
      if (!signal?.aborted && requestId === tableRequestIdRef.current) {
        setTableLoading(false);
      }
    }
  }, [interval, isEnglish, marketPair, selectedProvider, tablePage, tablePageSize, timezone]);

  const loadCandleDetail = useCallback(async (row: DataCandleRow) => {
    const currentDetail = candleDetails[row.key];
    if (currentDetail?.loading || currentDetail?.candle) {
      return;
    }

    setCandleDetails((current) => ({
      ...current,
      [row.key]: { loading: true, candle: null, errorMessage: null }
    }));

    try {
      const candle = await getCandleDetail({
        provider: row.provider as typeof selectedProvider,
        market_pair: row.marketPair,
        interval: row.interval,
        open_time_ms: row.openTimeMs
      });
      setCandleDetails((current) => ({
        ...current,
        [row.key]: { loading: false, candle, errorMessage: null }
      }));
    } catch (error) {
      setCandleDetails((current) => ({
        ...current,
        [row.key]: { loading: false, candle: null, errorMessage: getErrorMessage(error) }
      }));
    }
  }, [candleDetails, selectedProvider]);

  useEffect(() => {
    let ignore = false;
    const timerId = window.setTimeout(() => {
      async function loadGapSummary() {
        setGapLoading(true);
        setGapError(null);
        try {
          const [summaryResponse, listResponse] = await Promise.all([
            getDataGapSummary({ provider: selectedProvider, market_pair: marketPair, interval }),
            listDataGaps({
              provider: selectedProvider,
              market_pair: marketPair,
              interval,
              status: "detected,repairing,failed",
              limit: 5,
              offset: 0
            })
          ]);
          if (!ignore) {
            setGapSummary(summaryResponse);
            setDataGaps(listResponse.gaps);
          }
        } catch (error) {
          console.error(error);
          if (!ignore) {
            setGapError(getDataLoadErrorMessage("gap", error, isEnglish));
          }
        } finally {
          if (!ignore) {
            setGapLoading(false);
          }
        }
      }

      void loadGapSummary();
    }, 250);

    return () => {
      ignore = true;
      window.clearTimeout(timerId);
    };
  }, [dataLoadToken, interval, isEnglish, marketPair, selectedProvider]);

  useEffect(() => {
    let ignore = false;

    async function loadMarketOptions() {
      try {
        const response = await listMarkets({ provider: selectedProvider, enabled: true, limit: 200 });
        if (!ignore && response.markets.length > 0) {
          const nextOptions = response.markets.map((market) => ({
            value: market.market_pair,
            label: market.market_pair
          }));
          if (!nextOptions.some((option) => option.value === marketPair)) {
            nextOptions.unshift({ value: marketPair, label: marketPair });
          }
          setMarketPairOptions(nextOptions);
        }
      } catch (error) {
        console.error(error);
      }
    }

    void loadMarketOptions();

    return () => {
      ignore = true;
    };
  }, [marketPair, selectedProvider]);

  useEffect(() => {
    void loadDataPage();
  }, [loadDataPage]);

  useEffect(() => {
    const controller = new AbortController();
    setTableLoading(true);
    const timerId = window.setTimeout(() => {
      void loadTablePage(controller.signal);
    }, TABLE_QUERY_DEBOUNCE_MS);

    return () => {
      controller.abort();
      window.clearTimeout(timerId);
    };
  }, [loadTablePage]);

  useEffect(() => {
    if (fetchProgress.status !== "running" || fetchProgress.startedAtMs === null) {
      return undefined;
    }

    const timerId = window.setInterval(() => {
      setFetchProgress((current) => {
        if (current.status !== "running" || current.startedAtMs === null) {
          return current;
        }

        const elapsedSeconds = (Date.now() - current.startedAtMs) / 1000;
        return {
          ...current,
          elapsedSeconds
        };
      });
    }, 300);

    return () => window.clearInterval(timerId);
  }, [fetchProgress.startedAtMs, fetchProgress.status]);

  useEffect(() => {
    const jobId = fetchProgress.job?.id;
    if (fetchProgress.status !== "running" || !jobId) {
      return undefined;
    }

    const activeJobId = jobId;
    let ignore = false;
    let inFlight = false;

    async function pollFetchJob() {
      if (inFlight || ignore) return;
      inFlight = true;
      try {
        const job = await getCandleFetchJob(activeJobId);
        if (ignore) {
          return;
        }

        const nextStatus = getProgressStatusFromJob(job.status);
        setFetchProgress((current) => {
          if (current.job?.id !== activeJobId) {
            return current;
          }

          return {
            ...current,
            status: nextStatus,
            percent:
              nextStatus === "error" || nextStatus === "cancelled"
                ? 100
                : Math.max(1, Math.min(100, job.progress_percent)),
            elapsedSeconds:
              current.startedAtMs === null ? current.elapsedSeconds : (Date.now() - current.startedAtMs) / 1000,
            job,
            errorMessage: nextStatus === "error" ? job.error_message ?? getErrorMessage(null) : null
          };
        });

        if (nextStatus !== "running") {
          setFetching(false);
          if (nextStatus === "success") {
            setLastFetchSummary({
              mode: fetchProgress.mode,
              fetchedCount: job.fetched_count,
              savedCount: job.saved_count,
              missingCount: job.missing_count,
              batchCount: job.completed_batch_count || job.total_batch_count,
              completedAt: toDisplayDateTime(new Date().toISOString(), timezone)
            });
            await Promise.all([loadDataPage({ forceChartRefresh: true }), loadTablePage()]);
          } else {
            setDataLoadToken((current) => current + 1);
          }
        }
      } catch (error) {
        if (!ignore) setTableError(getDataLoadErrorMessage("table", error, isEnglish));
      } finally {
        inFlight = false;
      }
    }

    void pollFetchJob();
    const timerId = window.setInterval(() => {
      void pollFetchJob();
    }, 1000);

    return () => {
      ignore = true;
      window.clearInterval(timerId);
    };
  }, [fetchProgress.job?.id, fetchProgress.mode, fetchProgress.status, loadDataPage, loadTablePage, timezone]);

  const handlePauseFetchJob = async () => {
    const jobId = fetchProgress.job?.id;
    if (!jobId) {
      return;
    }

    try {
      const job = await pauseCandleFetchJob(jobId);
      setFetching(job.status === "running" || job.status === "pausing");
      setFetchProgress((current) => ({
        ...current,
        status: getProgressStatusFromJob(job.status),
        percent: Math.max(1, Math.min(100, job.progress_percent)),
        job,
        errorMessage: null
      }));
    } catch (error) {
      console.error(error);
      setFetchProgress((current) => ({
        ...current,
        status: "error",
        percent: 100,
        errorMessage: getErrorMessage(error)
      }));
      setFetching(false);
    }
  };

  const handleCancelFetchJob = async () => {
    const jobId = fetchProgress.job?.id;
    if (!jobId) {
      return;
    }

    try {
      const job = await cancelCandleFetchJob(jobId);
      setFetching(job.status === "cancelling");
      if (job.status === "cancelled") {
        setDataLoadToken((current) => current + 1);
      }
      setFetchProgress((current) => ({
        ...current,
        status: getProgressStatusFromJob(job.status),
        percent: 100,
        job,
        errorMessage: null
      }));
    } catch (error) {
      console.error(error);
      setFetchProgress((current) => ({
        ...current,
        status: "error",
        percent: 100,
        errorMessage: getErrorMessage(error)
      }));
      setFetching(false);
    }
  };

  const handleResumeFetchJob = async () => {
    const jobId = fetchProgress.job?.id;
    if (!jobId) {
      return;
    }

    try {
      const job = await resumeCandleFetchJob(jobId);
      setFetching(true);
      setFetchProgress((current) => ({
        ...current,
        status: getProgressStatusFromJob(job.status),
        percent: Math.max(1, Math.min(100, job.progress_percent)),
        job,
        errorMessage: null
      }));
      setFetchProgressModalOpen(true);
    } catch (error) {
      console.error(error);
      setFetchProgress((current) => ({
        ...current,
        status: "error",
        percent: 100,
        errorMessage: getErrorMessage(error)
      }));
      setFetching(false);
    }
  };

  const handleFetch = async (fetchMode: CandleFetchMode) => {
    if (!canStartFetch) {
      return;
    }
    if (!(await confirmDangerousFetch(fetchMode, dataPageCopy))) {
      return;
    }

    const startedAtMs = Date.now();
    const fetchDateParams = getHistoryDateParams(startDate);
    if (!fetchDateParams.start_time) {
      return;
    }
    const requestMode = getJobRequestMode(fetchMode);

    setFetching(true);
    setFetchProgressModalOpen(true);
    setDrawerOpen(false);
    setFetchProgress({
      status: "running",
      mode: fetchMode,
      percent: 8,
      elapsedSeconds: 0,
      startedAtMs,
      job: null,
      directResult: null,
      errorMessage: null
    });

    try {
      const job = await createCandleFetchJob({
        provider: selectedProvider,
        market_type: "spot",
        market_pair: marketPair,
        interval,
        mode: requestMode,
        closed_only: true,
        batch_limit: limit,
        overlap_candles: 2,
        verify_continuity: refetchVerifyContinuity,
        retry_attempts: 2,
        retry_delay_seconds: 0.25,
        start_time: fetchDateParams.start_time,
        end_time: fetchDateParams.end_time
      });
      setFetchProgress({
        status: getProgressStatusFromJob(job.status),
        mode: fetchMode,
        percent: Math.max(1, Math.min(100, job.progress_percent)),
        elapsedSeconds: (Date.now() - startedAtMs) / 1000,
        startedAtMs,
        job,
        directResult: null,
        errorMessage: job.status === "failed" ? job.error_message ?? getErrorMessage(null) : null
      });
    } catch (error) {
      console.error(error);
      setTableError(getDataLoadErrorMessage("table", error, isEnglish));
      setLastRequestAt(toDisplayDateTime(new Date().toISOString(), timezone));
      setFetchProgress({
        status: "error",
        mode: fetchMode,
        percent: 100,
        elapsedSeconds: (Date.now() - startedAtMs) / 1000,
        startedAtMs,
        job: null,
        directResult: null,
        errorMessage: getErrorMessage(error)
      });
      setFetching(false);
    }
  };

  const handleRepairDataGap = useCallback(async (gap: DataGapResponse) => {
    if (!canRepairDataGap(gap)) {
      return;
    }

    const startedAtMs = Date.now();
    setRepairingGapId(gap.id);
    setFetching(true);
    setFetchProgressModalOpen(true);
    setFetchProgress({
      status: "running",
      mode: "fill_gaps",
      percent: 8,
      elapsedSeconds: 0,
      startedAtMs,
      job: null,
      directResult: null,
      errorMessage: null
    });

    try {
      const result = await repairDataGap(gap.id, {
        batch_limit: limit,
        overlap_candles: 2,
        verify_continuity: true,
        retry_attempts: 2,
        retry_delay_seconds: 0.25
      });
      const nextStatus = getProgressStatusFromJob(result.job.status);
      setDataGaps((current) => current.map((item) => (item.id === result.gap.id ? result.gap : item)));
      setFetchProgress({
        status: nextStatus,
        mode: "fill_gaps",
        percent: Math.max(1, Math.min(100, result.job.progress_percent)),
        elapsedSeconds: (Date.now() - startedAtMs) / 1000,
        startedAtMs,
        job: result.job,
        directResult: null,
        errorMessage: result.job.status === "failed" ? result.job.error_message ?? getErrorMessage(null) : null
      });
      setFetching(nextStatus === "running");
      setDataLoadToken((current) => current + 1);
    } catch (error) {
      console.error(error);
      setGapError(getDataLoadErrorMessage("gap", error, isEnglish));
      setFetchProgress({
        status: "error",
        mode: "fill_gaps",
        percent: 100,
        elapsedSeconds: (Date.now() - startedAtMs) / 1000,
        startedAtMs,
        job: null,
        directResult: null,
        errorMessage: getErrorMessage(error)
      });
      setFetching(false);
    } finally {
      setRepairingGapId(null);
    }
  }, [isEnglish, limit]);

  const dataGapColumns = useMemo(
    () => getDataGapColumns(isEnglish, timezone, handleRepairDataGap, repairingGapId),
    [handleRepairDataGap, isEnglish, repairingGapId, timezone]
  );

  const fetchSteps = getFetchSteps(fetchProgress);
  const fetchProgressPercent = Math.round(fetchProgress.percent);
  const fetchModalTitle =
    fetchProgress.status === "success"
      ? "重新抓取完成"
      : fetchProgress.status === "paused"
        ? "重新抓取已暫停"
        : fetchProgress.status === "cancelled"
          ? "重新抓取已中止"
          : fetchProgress.status === "error"
            ? "重新抓取失敗"
            : "正在重新抓取資料";
  const fetchProgressStatus =
    fetchProgress.status === "success"
      ? "success"
      : fetchProgress.status === "error" || fetchProgress.status === "cancelled"
        ? "exception"
        : "active";
  const fetchProgressStrokeColor =
    fetchProgress.status === "success" ? "#16a34a" : fetchProgress.status === "paused" ? "#d97706" : "#0f766e";
  const fetchResult = fetchProgress.directResult;
  const hasFetchJob = fetchProgress.job !== null;
  const lockProgressModal = fetchProgress.status === "running" && hasFetchJob;
  const fetchSummaryItems = [
    {
      label: "抓取筆數",
      value: fetchProgress.job
        ? formatInteger(fetchProgress.job.fetched_count)
        : fetchResult
          ? formatInteger(fetchResult.fetched_count)
          : "處理中"
    },
    {
      label: "寫入筆數",
      value: fetchProgress.job
        ? formatInteger(fetchProgress.job.saved_count)
        : fetchResult
          ? formatInteger(fetchResult.saved_count)
          : "等待中"
    },
    {
      label: "缺口",
      value: fetchProgress.job
        ? formatInteger(fetchProgress.job.missing_count)
        : fetchResult
          ? formatInteger(fetchResult.missing_count)
          : "驗證中"
    },
    {
      label: "批次",
      value: fetchProgress.job
        ? `${formatInteger(fetchProgress.job.completed_batch_count)} / ${formatInteger(fetchProgress.job.total_batch_count)}`
        : fetchResult
          ? formatInteger(fetchResult.plan.batch_count)
          : "等待中"
    },
    {
      label: "目前抓到",
      value: fetchProgress.job ? toDisplayDateTime(fetchProgress.job.current_cursor_time, timezone) : "--"
    },
    {
      label: "耗時",
      value: formatDuration(fetchProgress.elapsedSeconds)
    }
  ];

  return (
    <main className={`data-page ${drawerOpen ? "data-page-panel-open" : ""}`}>
      <div className="data-page-grid">
        <section className="data-main-stack">
          <div className="page-header">
            <div>
              <Typography.Title level={2}>{messages.data.title}</Typography.Title>
              <Typography.Text className="page-subtitle">{messages.data.subtitle}</Typography.Text>
            </div>
          </div>

          <Card className="toolbar-card" variant="borderless">
            <Form layout="vertical" className="query-toolbar">
              <Form.Item label={messages.data.exchange}>
                <Select
                  value={selectedProvider}
                  options={[{ value: selectedProvider, label: selectedProviderLabel }]}
                />
              </Form.Item>
              <Form.Item label={messages.data.symbol}>
                <Select value={marketPair} options={marketPairOptions} onChange={updateMarketPair} />
              </Form.Item>
              <Form.Item label={messages.data.interval}>
                <Segmented
                  options={["1m", "5m", "15m", "1h", "1d"]}
                  value={interval}
                  onChange={(value) => updateInterval(String(value))}
                />
              </Form.Item>
              <Form.Item label={messages.data.startDate} required>
                <DatePicker onChange={(value) => setStartDate(normalizeStartDate(value))} />
              </Form.Item>
              <Form.Item label={messages.data.limit}>
                <InputNumber
                  min={1}
                  max={MAX_LIMIT}
                  value={limit}
                  onChange={(value) => setLimit(typeof value === "number" ? value : DEFAULT_LIMIT)}
                />
              </Form.Item>
              <Form.Item className="query-actions-item">
                <Space className="query-actions">
                  <Button
                    type="primary"
                    icon={<DownloadOutlined />}
                    loading={fetching}
                    disabled={!canStartFetch}
                    onClick={() => void handleFetch("auto")}
                  >
                    {messages.data.fetchData}
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={() => setDrawerOpen(true)}>
                    {messages.data.refetch}
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>

          {dataRefreshing || hasDataLoadError || lastFetchSummary ? (
            <div className="data-feedback-row">
              {dataRefreshing ? (
                <Alert
                  type="info"
                  showIcon
                  message={isEnglish ? "Refreshing market data" : "正在更新市場資料"}
                />
              ) : null}
              {providerError ? <Alert type="error" showIcon message={providerError} /> : null}
              {chartError ? <Alert type="warning" showIcon message={chartError} /> : null}
              {tableError ? <Alert type="warning" showIcon message={tableError} /> : null}
              {gapError ? (
                <Alert type="warning" showIcon message={gapError} />
              ) : null}
              {lastFetchSummary ? (
                <Alert
                  type="success"
                  showIcon
                  message={getFetchSummaryText(lastFetchSummary, isEnglish)}
                  closable
                  onClose={() => setLastFetchSummary(null)}
                />
              ) : null}
            </div>
          ) : null}

          <Card className="data-metric-strip panel-card" variant="borderless">
            <div className="data-metric-item">
              <span className="metric-label">{messages.data.storedRows}</span>
              <strong>{formatInteger(coverage?.candle_count)}</strong>
              <small>{messages.data.storedRowsDetail}</small>
              <DatabaseOutlined />
            </div>
            <div className="data-metric-item">
              <span className="metric-label">{messages.data.latestCandle}</span>
              <strong className={latestCandle && latestCandle.close >= latestCandle.open ? "positive-text" : ""}>
                {formatPrice(latestCandle?.close ?? null)} <em>USDT</em>
              </strong>
              <small>{latestCandle?.time ?? "--"}</small>
              <CheckCircleOutlined />
            </div>
            <div className="data-metric-item">
              <span className="metric-label">{messages.data.missingRanges}</span>
              <strong>
                {gapLoading ? (
                  <LoadingOutlined className="spinning-icon" />
                ) : (
                  <>
                    {missingCount.toLocaleString()}{" "}
                    <CheckCircleOutlined className={missingCount === 0 && !gapError ? "positive-text" : "negative-text"} />
                  </>
                )}
              </strong>
              <small>{missingRangeLabel}</small>
            </div>
            <div className="data-metric-item">
              <span className="metric-label">{messages.data.lastSync}</span>
              <strong>{toDisplayDateTime(coverage?.last_fetched_at, timezone)}</strong>
              <small>
                <ClockCircleOutlined /> {lastRequestAt ?? "--"}
              </small>
            </div>
          </Card>

          <Card
            title={isEnglish ? "Data Gaps" : "資料缺口"}
            extra={
              <Space size={8}>
                <Typography.Text type="secondary">
                {gapLoading
                  ? isEnglish
                    ? "Refreshing"
                    : "更新中"
                  : isEnglish
                    ? "Saved checks"
                    : "已保存檢查"}
                </Typography.Text>
                <Button
                  icon={<SyncOutlined />}
                  loading={repairingGapId !== null}
                  disabled={fetching || !dataGaps.some(canRepairDataGap)}
                  size="small"
                  onClick={() => {
                    const targetGap = dataGaps.find(canRepairDataGap);
                    if (targetGap) {
                      void handleRepairDataGap(targetGap);
                    }
                  }}
                >
                  {isEnglish ? "Repair first" : "修補最早缺口"}
                </Button>
              </Space>
            }
            className="panel-card data-gap-card"
            variant="borderless"
          >
            <div className="data-gap-summary-grid">
              <div className="data-gap-summary-item">
                <span>{isEnglish ? "Active Missing" : "待處理缺口"}</span>
                <strong>{gapLoading ? <LoadingOutlined className="spinning-icon" /> : formatInteger(missingCount)}</strong>
              </div>
              <div className="data-gap-summary-item">
                <span>{isEnglish ? "Detected Ranges" : "偵測區段"}</span>
                <strong>{formatInteger(gapSummary?.detected_count)}</strong>
              </div>
              <div className="data-gap-summary-item">
                <span>{isEnglish ? "First Gap" : "第一個缺口"}</span>
                <strong>{toDisplayDateTime(gapSummary?.first_active_gap_start_time, timezone)}</strong>
              </div>
              <div className="data-gap-summary-item">
                <span>{isEnglish ? "Last Check" : "最後檢查"}</span>
                <strong>{toDisplayDateTime(gapSummary?.last_checked_at, timezone)}</strong>
              </div>
            </div>
            <Table<DataGapResponse>
              columns={dataGapColumns}
              dataSource={dataGaps}
              loading={gapLoading}
              locale={{ emptyText: isEnglish ? "No saved gaps" : "目前沒有已保存缺口" }}
              pagination={false}
              rowKey="id"
              scroll={{ x: 1040 }}
              size="small"
            />
          </Card>

          <Row gutter={[16, 16]} align="stretch" className="data-chart-row">
            <Col xs={24} xl={17}>
              <Card
                title={
                  <div className="chart-title-row">
                    <span>{chartTitle}</span>
                    <small>{getOhlcSummary(chartRows)}</small>
                    <em>{chartWindowLabel}</em>
                  </div>
                }
                extra={
                  <Space size={8}>
                    <Button icon={<SettingOutlined />} aria-label="Chart settings" />
                    <Button icon={<FullscreenOutlined />} aria-label="Fullscreen chart" />
                    <Button icon={<MoreOutlined />} aria-label="More chart actions" />
                  </Space>
                }
                className="panel-card chart-card"
                variant="borderless"
              >
                <CandlestickChart candles={chartRows} emptyText={dataPageCopy.chartNoData} loading={chartLoading} />
              </Card>
            </Col>
            <Col xs={24} xl={7}>
              <Card
                title={messages.data.apiStatus}
                className="panel-card status-fill-card api-status-card"
                variant="borderless"
              >
                <div className="api-status-list">
                  <div>
                    <span>{messages.data.provider}</span>
                    <strong>{providerStatus ? getProviderLabel(providerStatus.provider) : "--"}</strong>
                  </div>
                  <div>
                    <span>{messages.data.sourceMarket}</span>
                    <strong>{marketPair}</strong>
                  </div>
                  <div>
                    <span>{messages.data.status}</span>
                    <strong className={providerIsHealthy ? "positive-text" : "negative-text"}>
                      {providerStatusLabel}
                    </strong>
                  </div>
                  <div>
                    <span>{messages.data.latency}</span>
                    <strong className={providerIsHealthy ? "positive-text" : ""}>
                      {formatLatency(requestLatencyMs)}
                    </strong>
                  </div>
                  <div>
                    <span>{messages.data.lastRequest}</span>
                    <strong>{lastRequestAt ?? "--"}</strong>
                  </div>
                  <div>
                    <span>{messages.data.rowsReturned}</span>
                    <strong>{candleRows.length.toLocaleString()}</strong>
                  </div>
                </div>
              </Card>
            </Col>
          </Row>

          <Card
            title={candleRowsTitle}
            extra={
              <div className="table-page-size-control">
                <span>{dataPageCopy.rowsPerPage}</span>
                <Select
                  size="small"
                  value={tablePageSize}
                  options={tablePageSizeOptions}
                  onChange={updateTablePageSize}
                />
              </div>
            }
            className="panel-card data-table-card"
            variant="borderless"
          >
            <Table<DataCandleRow>
              columns={candleColumns}
              dataSource={candleRows}
              loading={tableLoading}
              size="middle"
              expandable={{
                expandedRowRender: (row) => renderCandleDetails(row, candleDetails[row.key]),
                onExpand: (expanded, row) => {
                  if (expanded) {
                    void loadCandleDetail(row);
                  }
                }
              }}
              pagination={{
                current: tablePage,
                pageSize: tablePageSize,
                total: candleTotalCount,
                showSizeChanger: false,
                showTotal: (total, range) => `${range[0]} - ${range[1]} / ${total.toLocaleString()}`,
                onChange: (page) => updateTablePage(page)
              }}
              scroll={{ x: 920 }}
            />
            <div className="table-footer">
              <span>
                {`${dataPageCopy.loadedRows}: ${getTableFooter(
                  tablePage,
                  tablePageSize,
                  candleRows.length,
                  candleTotalCount
                )}`}
              </span>
            </div>
          </Card>
        </section>

        {drawerOpen ? (
          <aside className="refetch-side-panel">
            <div className="refetch-side-header">
              <Typography.Title level={4}>{messages.data.drawerTitle}</Typography.Title>
              <Button icon={<CloseOutlined />} aria-label="Close re-fetch panel" onClick={() => setDrawerOpen(false)} />
            </div>
            <div className="refetch-side-body">
              <Form layout="vertical">
                <Form.Item label={messages.data.mode}>
                  <Radio.Group value={mode} onChange={(event) => setMode(normalizeDrawerMode(event.target.value))}>
                    <Space direction="vertical">
                      <Radio value="fill-gaps">{messages.data.fillGaps}</Radio>
                      <Radio value="overwrite-range">{messages.data.overwriteRange}</Radio>
                      <Radio value="delete-reload">{messages.data.deleteReload}</Radio>
                    </Space>
                  </Radio.Group>
                </Form.Item>
                <Form.Item label={messages.data.exchange}>
                  <Select
                    value={selectedProvider}
                    options={[{ value: selectedProvider, label: selectedProviderLabel }]}
                  />
                </Form.Item>
                <Form.Item label={messages.data.symbol}>
                  <Select value={marketPair} options={marketPairOptions} onChange={updateMarketPair} />
                </Form.Item>
                <Form.Item label={messages.data.interval}>
                  <Select
                    value={interval}
                    onChange={updateInterval}
                    options={["1m", "5m", "15m", "1h", "1d"].map((value) => ({ value, label: value }))}
                  />
                </Form.Item>
                <Form.Item label={messages.data.startDate} required>
                  <DatePicker className="full-width" onChange={(value) => setStartDate(normalizeStartDate(value))} />
                </Form.Item>
                <Form.Item label={messages.data.limit}>
                  <InputNumber
                    min={1}
                    max={MAX_LIMIT}
                    value={limit}
                    className="full-width"
                    onChange={(value) => setLimit(typeof value === "number" ? value : DEFAULT_LIMIT)}
                  />
                  <Typography.Text className="drawer-hint">{messages.data.maxRowsHint}</Typography.Text>
                </Form.Item>
                <Space direction="vertical" size={12}>
                  <Checkbox
                    checked={refetchVerifyContinuity}
                    onChange={(event) => setRefetchVerifyContinuity(event.target.checked)}
                  >
                    {messages.data.validateRows}
                  </Checkbox>

                </Space>
                <Alert
                  type={modeWarning ? "warning" : "info"}
                  showIcon
                  icon={<WarningOutlined />}
                  className="drawer-alert"
                  message={modeWarning ? messages.data.overwriteWarning : dataPageCopy.fillGapsNotice}
                />
              </Form>
            </div>
            <div className="drawer-footer">
              <Button onClick={() => setDrawerOpen(false)}>{messages.common.cancel}</Button>
              <Button
                type="primary"
                icon={<SyncOutlined />}
                loading={fetching}
                disabled={!canStartFetch}
                onClick={() => void handleFetch(getDrawerFetchMode(mode))}
              >
                {messages.data.startRefetch}
              </Button>
            </div>
          </aside>
        ) : null}
      </div>
      <Modal
        centered
        className="fetch-progress-modal"
        closable={!lockProgressModal}
        footer={null}
        maskClosable={!lockProgressModal}
        open={fetchProgressModalOpen}
        width={620}
        onCancel={() => setFetchProgressModalOpen(false)}
      >
        <div className="fetch-progress-content">
          <div className="fetch-progress-header">
            <div className={`fetch-progress-icon fetch-progress-icon-${fetchProgress.status}`}>
              {fetchProgress.status === "success" ? (
                <CheckCircleOutlined />
              ) : fetchProgress.status === "error" ||
                fetchProgress.status === "cancelled" ||
                fetchProgress.status === "paused" ? (
                <WarningOutlined />
              ) : (
                <LoadingOutlined />
              )}
            </div>
            <div className="fetch-progress-title-block">
              <Typography.Title level={3}>{fetchModalTitle}</Typography.Title>
              <Typography.Text>{`${marketPair} · ${interval} · ${selectedProviderLabel}`}</Typography.Text>
            </div>
          </div>

          <div className="fetch-progress-main">
            <div className="fetch-progress-percent-row">
              <strong>{fetchProgressPercent}%</strong>
              <span>{getProgressStatusText(fetchProgress, timezone)}</span>
            </div>
            <Progress
              percent={fetchProgressPercent}
              showInfo={false}
              status={fetchProgressStatus}
              strokeColor={fetchProgressStrokeColor}
            />
          </div>

          <div className="fetch-progress-summary-grid">
            {fetchSummaryItems.map((item) => (
              <div className="fetch-progress-summary-item" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>

          <div className="fetch-progress-steps">
            {fetchSteps.map((step) => (
              <div className={`fetch-progress-step fetch-progress-step-${step.status}`} key={step.label}>
                <span className="fetch-progress-step-icon">
                  {step.status === "done" ? (
                    <CheckCircleOutlined />
                  ) : step.status === "active" ? (
                    <LoadingOutlined />
                  ) : step.status === "error" ? (
                    <WarningOutlined />
                  ) : null}
                </span>
                <span>{step.label}</span>
                <strong>
                  {step.status === "done"
                    ? "完成"
                    : step.status === "active"
                      ? "進行中"
                      : step.status === "error"
                        ? "失敗"
                        : "等待中"}
                </strong>
              </div>
            ))}
          </div>

          <div className="fetch-progress-detail-row">
            <span>{`模式：${getFetchModeLabel(fetchProgress.mode)}`}</span>
            <span>{hasFetchJob ? dataPageCopy.backgroundRun : dataPageCopy.directRun}</span>
            <span>{`job_id: ${fetchProgress.job?.id ?? "--"}`}</span>
          </div>

          <div className="fetch-progress-footer">
            {fetchProgress.status === "running" ? (
              hasFetchJob ? (
                <>
                  <Button onClick={() => setFetchProgressModalOpen(false)}>背景執行</Button>
                  <Button disabled={fetchProgress.job?.status === "pausing" || fetchProgress.job?.status === "cancelling"} onClick={() => void handlePauseFetchJob()}>暫停</Button>
                  <Button danger disabled={fetchProgress.job?.status === "cancelling"} onClick={() => void handleCancelFetchJob()}>
                    中止
                  </Button>
                  <Button type="primary" icon={<LoadingOutlined />} loading>
                    抓取中
                  </Button>
                </>
              ) : (
                <>
                  <Button onClick={() => setFetchProgressModalOpen(false)}>關閉視窗</Button>
                  <Button type="primary" icon={<LoadingOutlined />} loading>
                    直接執行中
                  </Button>
                </>
              )
            ) : fetchProgress.status === "paused" ? (
              <>
                <Button onClick={() => setFetchProgressModalOpen(false)}>關閉</Button>
                <Button danger disabled={fetchProgress.job?.status === "cancelling"} onClick={() => void handleCancelFetchJob()}>
                  中止
                </Button>
                <Button type="primary" onClick={() => void handleResumeFetchJob()}>
                  恢復
                </Button>
              </>
            ) : fetchProgress.status === "success" ? (
              <>
                <Button onClick={() => setFetchProgressModalOpen(false)}>關閉</Button>
                <Button
                  type="primary"
                  onClick={() => {
                    updateTablePage(1);
                    setFetchProgressModalOpen(false);
                  }}
                >
                  查看最新資料
                </Button>
              </>
            ) : (
              <>
                <Button onClick={() => setFetchProgressModalOpen(false)}>關閉</Button>
                <Button type="primary" disabled={!canStartFetch} onClick={() => void handleFetch(fetchProgress.mode)}>
                  重試
                </Button>
              </>
            )}
          </div>
        </div>
      </Modal>
    </main>
  );
}
