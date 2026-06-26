import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  EyeOutlined,
  PauseOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  StopOutlined,
  WarningOutlined
} from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Pagination,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelCandleFetchJob,
  createSchedule,
  DEFAULT_MARKET_DATA_PROVIDER,
  deleteSchedule,
  getCandleFetchJob,
  getCandleFetchJobOverview,
  getCandleFetchJobSummary,
  getSchedule,
  getStorageSettings,
  listMarkets,
  listCandleFetchJobs,
  listSchedules,
  MARKET_DATA_PROVIDER_LABELS,
  pauseCandleFetchJob,
  pauseSchedule,
  resumeCandleFetchJob,
  resumeSchedule,
  runScheduleNow,
  updateSchedule
} from "../features/market-data/api";
import type {
  CandleFetchJobResponse,
  CandleFetchJobListQuery,
  CandleFetchJobOverviewResponse,
  CandleFetchJobSummaryResponse,
  MarketResponse,
  MarketDataProviderName,
  ScheduleCreateRequest,
  ScheduleResponse
} from "../features/market-data/api";
import { ApiError } from "../shared/api/client";
import type { AppMessages, Language } from "../shared/i18n/messages";

type JobsPageProps = {
  messages: AppMessages;
  language: Language;
};

type JobStatus = CandleFetchJobResponse["status"];
type MarketPair = string;

type JobRow = {
  key: string;
  id: string;
  asset: MarketPair;
  sourceMarket: string;
  interval: string;
  mode: string;
  status: JobStatus;
  progress: number | null;
  startedAt: string;
  duration: string;
  scheduleId: string | null;
  scheduleName: string | null;
  triggerType: string;
};

type ExecutionRow = {
  key: string;
  time: string;
  id: string;
  asset: MarketPair;
  interval: string;
  mode: string;
  status: JobStatus;
  rows: string;
  duration: string;
};

type ScheduleFormValues = {
  provider: MarketDataProviderName;
  market_pair: string;
  interval: string;
  mode: ScheduleCreateRequest["mode"];
  cron_expression: string;
  start_time?: DateLikeValue;
  enabled: boolean;
  batch_limit: number;
  overlap_candles: number;
  verify_continuity: boolean;
  retry_attempts: number;
  retry_delay_seconds: number;
};

type DateLikeValue = Dayjs | { toISOString: () => string };

type MarketPairOption = {
  value: string;
  label: string;
  searchText: string;
};

const copy = {
  "zh-TW": {
    subtitle: "管理 cron 排程、背景抓取佇列與執行歷史。",
    stats: {
      running: "執行中",
      queued: "排隊中",
      completed: "今日完成",
      failed: "失敗"
    },
    queue: "任務佇列",
    asset: "資產",
    all: "全部",
    loadingAssets: "讀取資產中...",
    noAssets: "尚未設定可用資產",
    assetLoadFailed: "資產選項讀取失敗",
    status: "狀態",
    interval: "週期",
    search: "搜尋任務 ID",
    taskId: "任務 ID",
    sourceMarket: "來源市場",
    mode: "模式",
    progress: "進度",
    startedAt: "開始時間",
    duration: "耗時",
    currentTask: "目前任務",
    sourceMarketLabel: "來源市場",
    currentRange: "目前處理範圍",
    capturedRows: "已抓取資料筆數",
    retryCount: "重試次數",
    pause: "暫停",
    resume: "繼續",
    stop: "停止",
    schedule: "排程",
    scheduledTrigger: "排程",
    manualTrigger: "手動",
    addSchedule: "新增排程",
    frequency: "Cron",
    action: "操作",
    recentRuns: "最近執行紀錄",
    viewAllRecords: "查看全部紀錄",
    errorSummary: "錯誤摘要",
    viewAllErrors: "查看全部錯誤",
    noCurrentTask: "目前沒有執行中或排隊中的任務",
    noSchedules: "尚未設定排程",
    noErrors: "目前沒有失敗任務",
    runNow: "立即執行",
    viewDetails: "查看詳情",
    jobDetails: "任務詳情",
    loadingDetails: "讀取任務詳情中...",
    basicInfo: "基本資訊",
    fetchStatus: "抓取狀態",
    timeInfo: "時間資訊",
    fetchParameters: "抓取參數",
    errorMessage: "錯誤訊息",
    noErrorMessage: "沒有錯誤訊息",
    scheduleId: "排程 ID",
    triggerType: "觸發來源",
    jobType: "任務類型",
    marketType: "市場類型",
    exchangeSymbol: "來源代碼",
    requestedRange: "請求範圍",
    effectiveRange: "有效範圍",
    cursor: "目前游標",
    createdAt: "建立時間",
    finishedAt: "完成時間",
    updatedAt: "更新時間",
    batchProgress: "批次進度",
    missingCount: "缺口數",
    closedOnly: "只抓已收線",
    yes: "是",
    no: "否",
    delete: "刪除",
    edit: "編輯",
    createSchedule: "建立排程",
    editSchedule: "編輯排程",
    cancel: "取消",
    provider: "資料來源",
    startTime: "起始時間",
    batchLimit: "每批筆數",
    overlap: "重疊 K 線",
    validateRows: "驗證連續性",
    retryAttempts: "重試次數",
    retryDelay: "重試間隔秒數",
    apiLoadFailed: "任務資料讀取失敗，請確認後端 API 是否啟動。",
    lastUpdated: "最後更新",
    refresh: "重新整理",
    refreshCompleted: "任務資料已更新",
    detailLoadFailed: "任務詳情讀取失敗",
    pauseRequested: "已送出暫停任務",
    pauseFailed: "暫停任務失敗",
    resumeRequested: "已送出繼續任務",
    resumeFailed: "繼續任務失敗",
    stopRequested: "已送出停止任務",
    stopFailed: "停止任務失敗",
    scheduleCreated: "排程已建立",
    scheduleCreateFailed: "排程建立失敗",
    scheduleDuplicate: "這組排程已存在",
    scheduleUpdated: "排程已更新",
    scheduleEditFailed: "排程更新失敗",
    scheduleEnabled: "排程已啟用",
    scheduleDisabled: "排程已停用",
    scheduleUpdateFailed: "排程狀態更新失敗",
    scheduleRunStarted: "已送出立即執行",
    scheduleRunFailed: "立即執行失敗",
    scheduleDeleted: "排程已刪除",
    scheduleDeleteFailed: "排程刪除失敗",
    deleteScheduleConfirmTitle: "刪除此排程？",
    deleteScheduleConfirmDescription: "刪除後不會再自動建立新的抓取任務。",
    allRecordsTitle: "全部執行紀錄",
    allErrorsTitle: "全部錯誤",
    noRunRecords: "目前沒有執行紀錄",
    statusText: {
      pending: "排隊中",
      running: "執行中",
      pausing: "暫停中",
      paused: "已暫停",
      success: "成功",
      failed: "失敗",
      cancelled: "已取消"
    },
    modes: {
      auto: "自動",
      backfill: "回補資料",
      fill_gaps: "補齊缺口",
      overwrite_range: "覆寫區間",
      delete_reload: "刪除重抓"
    }
  },
  "en-US": {
    subtitle: "Manage cron schedules, background fetch queue, and execution history.",
    stats: {
      running: "Running",
      queued: "Queued",
      completed: "Completed Today",
      failed: "Failed"
    },
    queue: "Job Queue",
    asset: "Market",
    all: "All",
    loadingAssets: "Loading markets...",
    noAssets: "No enabled markets yet",
    assetLoadFailed: "Failed to load market options",
    status: "Status",
    interval: "Interval",
    search: "Search job ID",
    taskId: "Job ID",
    sourceMarket: "Source Market",
    mode: "Mode",
    progress: "Progress",
    startedAt: "Started At",
    duration: "Duration",
    currentTask: "Current Job",
    sourceMarketLabel: "Source Market",
    currentRange: "Current Range",
    capturedRows: "Captured Rows",
    retryCount: "Retries",
    pause: "Pause",
    resume: "Resume",
    stop: "Stop",
    schedule: "Schedule",
    scheduledTrigger: "Scheduled",
    manualTrigger: "Manual",
    addSchedule: "Add Schedule",
    frequency: "Cron",
    action: "Action",
    recentRuns: "Recent Runs",
    viewAllRecords: "View all records",
    errorSummary: "Error Summary",
    viewAllErrors: "View all errors",
    noCurrentTask: "No running or queued job",
    noSchedules: "No schedules yet",
    noErrors: "No failed jobs",
    runNow: "Run now",
    viewDetails: "View details",
    jobDetails: "Job Details",
    loadingDetails: "Loading job details...",
    basicInfo: "Basic Info",
    fetchStatus: "Fetch Status",
    timeInfo: "Time Info",
    fetchParameters: "Fetch Parameters",
    errorMessage: "Error Message",
    noErrorMessage: "No error message",
    scheduleId: "Schedule ID",
    triggerType: "Trigger Type",
    jobType: "Job Type",
    marketType: "Market Type",
    exchangeSymbol: "Exchange Symbol",
    requestedRange: "Requested Range",
    effectiveRange: "Effective Range",
    cursor: "Current Cursor",
    createdAt: "Created At",
    finishedAt: "Finished At",
    updatedAt: "Updated At",
    batchProgress: "Batch Progress",
    missingCount: "Missing Count",
    closedOnly: "Closed Only",
    yes: "Yes",
    no: "No",
    delete: "Delete",
    edit: "Edit",
    createSchedule: "Create Schedule",
    editSchedule: "Edit Schedule",
    cancel: "Cancel",
    provider: "Provider",
    startTime: "Start time",
    batchLimit: "Batch limit",
    overlap: "Overlap candles",
    validateRows: "Verify continuity",
    retryAttempts: "Retry attempts",
    retryDelay: "Retry delay seconds",
    apiLoadFailed: "Failed to load job data. Check whether the backend API is running.",
    lastUpdated: "Last updated",
    refresh: "Refresh",
    refreshCompleted: "Job data refreshed",
    detailLoadFailed: "Failed to load job details",
    pauseRequested: "Pause request sent",
    pauseFailed: "Failed to pause job",
    resumeRequested: "Resume request sent",
    resumeFailed: "Failed to resume job",
    stopRequested: "Stop request sent",
    stopFailed: "Failed to stop job",
    scheduleCreated: "Schedule created",
    scheduleCreateFailed: "Failed to create schedule",
    scheduleDuplicate: "This schedule already exists",
    scheduleUpdated: "Schedule updated",
    scheduleEditFailed: "Failed to update schedule",
    scheduleEnabled: "Schedule enabled",
    scheduleDisabled: "Schedule disabled",
    scheduleUpdateFailed: "Failed to update schedule status",
    scheduleRunStarted: "Run request sent",
    scheduleRunFailed: "Failed to run schedule",
    scheduleDeleted: "Schedule deleted",
    scheduleDeleteFailed: "Failed to delete schedule",
    deleteScheduleConfirmTitle: "Delete this schedule?",
    deleteScheduleConfirmDescription: "It will no longer create new fetch jobs automatically.",
    allRecordsTitle: "All Execution Records",
    allErrorsTitle: "All Errors",
    noRunRecords: "No execution records yet",
    statusText: {
      pending: "Queued",
      running: "Running",
      pausing: "Pausing",
      paused: "Paused",
      success: "Success",
      failed: "Failed",
      cancelled: "Cancelled"
    },
    modes: {
      auto: "Auto",
      backfill: "Backfill",
      fill_gaps: "Fill gaps",
      overwrite_range: "Overwrite range",
      delete_reload: "Delete and reload"
    }
  }
} as const;

type JobsCopy = (typeof copy)[Language];

const intervalOptions = ["1m", "5m", "15m", "1h", "1d"];
const DEFAULT_JOB_PAGE_SIZE = 10;
const DEFAULT_SCHEDULE_PAGE_SIZE = 5;
const DEFAULT_HISTORY_PAGE_SIZE = 10;
const DEFAULT_ERROR_PAGE_SIZE = 10;
const JOB_AUTO_REFRESH_MS = 5000;
const DEFAULT_DISPLAY_TIMEZONE = "UTC";
const AUTO_REFRESH_JOB_STATUSES = new Set<JobStatus>(["running", "pending", "pausing"]);
const modeOptions: ScheduleCreateRequest["mode"][] = [
  "auto",
  "backfill",
  "fill_gaps",
  "overwrite_range",
  "delete_reload"
];

const defaultScheduleFormValues: Omit<ScheduleFormValues, "start_time"> = {
  provider: DEFAULT_MARKET_DATA_PROVIDER,
  market_pair: "",
  interval: "1m",
  mode: "auto",
  cron_expression: "*/5 * * * *",
  enabled: true,
  batch_limit: 1000,
  overlap_candles: 2,
  verify_continuity: true,
  retry_attempts: 2,
  retry_delay_seconds: 0.25
};

function getProviderLabel(provider: string) {
  return provider === DEFAULT_MARKET_DATA_PROVIDER
    ? MARKET_DATA_PROVIDER_LABELS[DEFAULT_MARKET_DATA_PROVIDER]
    : provider;
}

function getBaseAsset(asset: MarketPair) {
  return asset.split("/")[0] || asset.slice(0, 3).toUpperCase();
}

function AssetMark({ asset }: { asset: MarketPair }) {
  const baseAsset = getBaseAsset(asset);
  const mark = baseAsset.slice(0, 1).toUpperCase();

  return <span className={`asset-mark asset-mark-${baseAsset.toLowerCase()}`}>{mark}</span>;
}

function AssetCell({ asset }: { asset: MarketPair }) {
  return (
    <span className="asset-cell">
      <AssetMark asset={asset} />
      <strong>{asset}</strong>
    </span>
  );
}

function getTriggerLabel(triggerType: string, t: JobsCopy) {
  return triggerType === "scheduled" ? t.scheduledTrigger : t.manualTrigger;
}

function JobSourceCell({ row, t }: { row: JobRow; t: JobsCopy }) {
  const isScheduled = row.triggerType === "scheduled" || Boolean(row.scheduleId);
  return (
    <div className="job-source-cell">
      <span>{row.sourceMarket}</span>
      <span className="job-source-meta">
        <Tag color={isScheduled ? "blue" : "default"}>{getTriggerLabel(row.triggerType, t)}</Tag>
        {row.scheduleId ? (
          <Typography.Text className="job-source-schedule" title={row.scheduleName ?? row.scheduleId}>
            {row.scheduleName ?? row.scheduleId}
          </Typography.Text>
        ) : null}
      </span>
    </div>
  );
}

function StatusTag({
  status,
  labels
}: {
  status: JobStatus;
  labels: Record<JobStatus, string>;
}) {
  const color =
    status === "running"
      ? "blue"
      : status === "pending"
        ? "orange"
        : status === "pausing" || status === "paused"
          ? "purple"
          : status === "success"
            ? "green"
            : "red";
  return <Tag color={color}>{labels[status]}</Tag>;
}

function JobProgress({ value, status }: { value: number | null; status: JobStatus }) {
  if (value === null) {
    return <span className="muted-label">-</span>;
  }

  const strokeColor = status === "failed" ? "#ef4444" : status === "success" ? "#16a34a" : "#2563eb";
  return (
    <span className="job-progress-cell">
      <span>{Math.round(value)}%</span>
      <Progress percent={Math.round(value)} showInfo={false} size="small" strokeColor={strokeColor} />
    </span>
  );
}

function getModeLabel(mode: string, t: JobsCopy) {
  return mode in t.modes ? t.modes[mode as keyof typeof t.modes] : mode;
}

function mapMarketToOption(market: MarketResponse): MarketPairOption {
  return {
    value: market.market_pair,
    label: market.market_pair,
    searchText: [
      market.market_pair,
      market.exchange_symbol,
      market.base_asset,
      market.quote_asset,
      market.provider,
      market.market_type
    ].join(" ")
  };
}

function addMarketPairOption(options: Map<string, MarketPairOption>, marketPair: string) {
  if (options.has(marketPair)) {
    return;
  }
  options.set(marketPair, {
    value: marketPair,
    label: marketPair,
    searchText: marketPair
  });
}

function getJobColumns(
  t: JobsCopy,
  onViewDetails: (jobId: string) => void,
  detailLoadingJobId: string | null
): ColumnsType<JobRow> {
  return [
    { title: t.taskId, dataIndex: "id", key: "id", width: 172 },
    {
      title: t.asset,
      dataIndex: "asset",
      key: "asset",
      width: 132,
      render: (asset: MarketPair) => <AssetCell asset={asset} />
    },
    {
      title: t.sourceMarket,
      dataIndex: "sourceMarket",
      key: "sourceMarket",
      width: 220,
      render: (_, row) => <JobSourceCell row={row} t={t} />
    },
    { title: t.interval, dataIndex: "interval", key: "interval", width: 78 },
    {
      title: t.mode,
      dataIndex: "mode",
      key: "mode",
      width: 112,
      render: (mode: string) => getModeLabel(mode, t)
    },
    {
      title: t.status,
      dataIndex: "status",
      key: "status",
      width: 96,
      render: (status: JobStatus) => <StatusTag status={status} labels={t.statusText} />
    },
    {
      title: t.progress,
      dataIndex: "progress",
      key: "progress",
      width: 132,
      render: (value: number | null, row) => <JobProgress value={value} status={row.status} />
    },
    { title: t.startedAt, dataIndex: "startedAt", key: "startedAt", width: 220 },
    { title: t.duration, dataIndex: "duration", key: "duration", width: 96 },
    {
      title: t.action,
      key: "action",
      width: 86,
      fixed: "right",
      render: (_, row) => (
        <Tooltip title={t.viewDetails}>
          <Button
            type="text"
            icon={<EyeOutlined />}
            aria-label={t.viewDetails}
            loading={detailLoadingJobId === row.id}
            onClick={() => onViewDetails(row.id)}
          />
        </Tooltip>
      )
    }
  ];
}

function getExecutionColumns(t: JobsCopy): ColumnsType<ExecutionRow> {
  return [
    { title: t.startedAt, dataIndex: "time", key: "time", width: 220 },
    { title: t.taskId, dataIndex: "id", key: "id", width: 176 },
    {
      title: t.asset,
      dataIndex: "asset",
      key: "asset",
      width: 132,
      render: (asset: MarketPair) => <AssetCell asset={asset} />
    },
    { title: t.interval, dataIndex: "interval", key: "interval", width: 80 },
    {
      title: t.mode,
      dataIndex: "mode",
      key: "mode",
      width: 112,
      render: (mode: string) => getModeLabel(mode, t)
    },
    {
      title: t.status,
      dataIndex: "status",
      key: "status",
      width: 96,
      render: (status: JobStatus) => <StatusTag status={status} labels={t.statusText} />
    },
    { title: t.capturedRows, dataIndex: "rows", key: "rows", width: 120 },
    { title: t.duration, dataIndex: "duration", key: "duration", width: 96 }
  ];
}

function parseBackendDate(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
  const date = new Date(hasTimezone ? normalized : `${normalized}+00:00`);
  return Number.isFinite(date.getTime()) ? date : null;
}

function normalizeDisplayTimezone(timezone: string | null | undefined) {
  const selectedTimezone = timezone || DEFAULT_DISPLAY_TIMEZONE;
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: selectedTimezone }).format(new Date());
    return selectedTimezone;
  } catch {
    return DEFAULT_DISPLAY_TIMEZONE;
  }
}

function getTimezoneOffsetLabel(date: Date, timezone: string) {
  try {
    const timeZoneName = new Intl.DateTimeFormat("en-US", {
      timeZone: timezone,
      timeZoneName: "shortOffset"
    })
      .formatToParts(date)
      .find((part) => part.type === "timeZoneName")?.value;
    if (!timeZoneName || timeZoneName === "GMT") {
      return "UTC";
    }
    const match = /^GMT([+-])(\d{1,2})(?::?(\d{2}))?$/.exec(timeZoneName);
    if (!match) {
      return timeZoneName;
    }
    const [, sign, hours, minutes = "00"] = match;
    return `UTC${sign}${hours.padStart(2, "0")}:${minutes.padStart(2, "0")}`;
  } catch {
    return timezone;
  }
}

function toDisplayDateTime(value: string | null | undefined, timezone: string) {
  const date = parseBackendDate(value);
  if (!date) {
    return "-";
  }

  const selectedTimezone = normalizeDisplayTimezone(timezone);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: selectedTimezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    hourCycle: "h23"
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}:${values.second} ${getTimezoneOffsetLabel(date, selectedTimezone)}`;
}

function toTimestamp(value: string | null | undefined) {
  return parseBackendDate(value)?.getTime() ?? null;
}

function formatDuration(start: string | null | undefined, end: string | null | undefined) {
  const startMs = toTimestamp(start);
  const endMs = toTimestamp(end);
  if (startMs === null || endMs === null || endMs < startMs) {
    return "-";
  }

  const seconds = Math.floor((endMs - startMs) / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

function formatInteger(value: number | null | undefined) {
  return (value ?? 0).toLocaleString();
}

function getClientTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

function mapJobToRow(
  job: CandleFetchJobResponse,
  scheduleById: Map<string, ScheduleResponse>,
  timezone: string
): JobRow {
  const schedule = job.schedule_id ? scheduleById.get(job.schedule_id) : null;
  return {
    key: job.id,
    id: job.id,
    asset: job.market_pair,
    sourceMarket: `${getProviderLabel(job.provider)} (${job.market_pair})`,
    interval: job.interval,
    mode: job.mode,
    status: job.status,
    progress: job.status === "pending" ? null : job.progress_percent,
    startedAt: toDisplayDateTime(job.started_at ?? job.created_at, timezone),
    duration: formatDuration(
      job.started_at,
      job.finished_at ?? (job.status === "running" || job.status === "pausing" ? new Date().toISOString() : job.updated_at)
    ),
    scheduleId: job.schedule_id,
    scheduleName: schedule?.name ?? null,
    triggerType: job.trigger_type
  };
}

function mapJobToExecutionRow(job: CandleFetchJobResponse, timezone: string): ExecutionRow {
  return {
    key: job.id,
    time: toDisplayDateTime(job.started_at ?? job.created_at, timezone),
    id: job.id,
    asset: job.market_pair,
    interval: job.interval,
    mode: job.mode,
    status: job.status,
    rows: formatInteger(job.saved_count),
    duration: formatDuration(job.started_at, job.finished_at ?? job.updated_at)
  };
}

function toIsoString(value: DateLikeValue | undefined) {
  return value?.toISOString();
}

function isDuplicateScheduleError(error: unknown) {
  return error instanceof ApiError && error.status === 409;
}

function scheduleToFormValues(schedule: ScheduleResponse): ScheduleFormValues {
  return {
    provider: schedule.provider as MarketDataProviderName,
    market_pair: schedule.market_pair,
    interval: schedule.interval,
    mode: schedule.mode,
    cron_expression: schedule.cron_expression,
    start_time: dayjs(schedule.start_time),
    enabled: schedule.enabled,
    batch_limit: schedule.batch_limit,
    overlap_candles: schedule.overlap_candles,
    verify_continuity: schedule.verify_continuity,
    retry_attempts: schedule.retry_attempts,
    retry_delay_seconds: schedule.retry_delay_seconds
  };
}

function formatDateRange(start: string | null | undefined, end: string | null | undefined, timezone: string) {
  return `${toDisplayDateTime(start, timezone)} ~ ${toDisplayDateTime(end, timezone)}`;
}

function formatBoolean(value: boolean, t: JobsCopy) {
  return value ? t.yes : t.no;
}

function DetailItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="job-detail-item">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function DetailSection({
  title,
  children
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="job-detail-section">
      <Typography.Title level={5}>{title}</Typography.Title>
      <dl>{children}</dl>
    </section>
  );
}

export function JobsPage({ messages, language }: JobsPageProps) {
  const t = copy[language];
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<ScheduleFormValues>();
  const [jobs, setJobs] = useState<CandleFetchJobResponse[]>([]);
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<ScheduleResponse | null>(null);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [selectedInterval, setSelectedInterval] = useState<string>("all");
  const [searchText, setSearchText] = useState("");
  const [debouncedSearchText, setDebouncedSearchText] = useState("");
  const [jobPage, setJobPage] = useState(1);
  const [jobPageSize, setJobPageSize] = useState(DEFAULT_JOB_PAGE_SIZE);
  const [jobTotalCount, setJobTotalCount] = useState(0);
  const [jobSummary, setJobSummary] = useState<CandleFetchJobSummaryResponse | null>(null);
  const [jobOverview, setJobOverview] = useState<CandleFetchJobOverviewResponse | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [schedulePage, setSchedulePage] = useState(1);
  const [schedulePageSize, setSchedulePageSize] = useState(DEFAULT_SCHEDULE_PAGE_SIZE);
  const [scheduleTotalCount, setScheduleTotalCount] = useState(0);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [apiError, setApiError] = useState(false);
  const [displayTimezone, setDisplayTimezone] = useState(DEFAULT_DISPLAY_TIMEZONE);
  const [stoppingJobId, setStoppingJobId] = useState<string | null>(null);
  const [pausingJobId, setPausingJobId] = useState<string | null>(null);
  const [resumingJobId, setResumingJobId] = useState<string | null>(null);
  const [updatingScheduleId, setUpdatingScheduleId] = useState<string | null>(null);
  const [runningScheduleId, setRunningScheduleId] = useState<string | null>(null);
  const [deletingScheduleId, setDeletingScheduleId] = useState<string | null>(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [selectedDetailJob, setSelectedDetailJob] = useState<CandleFetchJobResponse | null>(null);
  const [selectedDetailSchedule, setSelectedDetailSchedule] = useState<ScheduleResponse | null>(null);
  const [detailScheduleLoading, setDetailScheduleLoading] = useState(false);
  const [detailLoadingJobId, setDetailLoadingJobId] = useState<string | null>(null);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [errorModalOpen, setErrorModalOpen] = useState(false);
  const [historyJobs, setHistoryJobs] = useState<CandleFetchJobResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(DEFAULT_HISTORY_PAGE_SIZE);
  const [historyTotalCount, setHistoryTotalCount] = useState(0);
  const [errorJobs, setErrorJobs] = useState<CandleFetchJobResponse[]>([]);
  const [errorLoading, setErrorLoading] = useState(false);
  const [errorPage, setErrorPage] = useState(1);
  const [errorPageSize, setErrorPageSize] = useState(DEFAULT_ERROR_PAGE_SIZE);
  const [errorTotalCount, setErrorTotalCount] = useState(0);
  const [marketOptionsLoading, setMarketOptionsLoading] = useState(false);
  const [marketPairOptions, setMarketPairOptions] = useState<MarketPairOption[]>([]);

  const selectedProvider = DEFAULT_MARKET_DATA_PROVIDER;
  const executionColumns = getExecutionColumns(t);
  const isEditingSchedule = editingSchedule !== null;
  const autoRefreshInFlightRef = useRef(false);

  const visibleMarketPairOptions = useMemo(() => {
    const options = new Map(marketPairOptions.map((option) => [option.value, option]));
    jobs.forEach((job) => addMarketPairOption(options, job.market_pair));
    schedules.forEach((schedule) => addMarketPairOption(options, schedule.market_pair));
    return Array.from(options.values());
  }, [jobs, marketPairOptions, schedules]);

  const scheduleMarketPairOptions = useMemo(() => {
    const options = new Map(marketPairOptions.map((option) => [option.value, option]));
    if (editingSchedule) {
      addMarketPairOption(options, editingSchedule.market_pair);
    }
    return Array.from(options.values());
  }, [editingSchedule, marketPairOptions]);

  const scheduleById = useMemo(
    () => new Map(schedules.map((schedule) => [schedule.id, schedule])),
    [schedules]
  );

  const defaultMarketPair = marketPairOptions[0]?.value ?? "";
  const scheduleInfoLabels = useMemo(
    () =>
      language === "zh-TW"
        ? {
            mode: "模式",
            timezone: "時區",
            lastRun: "上次執行",
            nextRun: "下次執行"
          }
        : {
            mode: "Mode",
            timezone: "Timezone",
            lastRun: "Last run",
            nextRun: "Next run"
          },
    [language]
  );

  useEffect(() => {
    const nextSearchText = searchText.trim();
    if (nextSearchText === debouncedSearchText) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setJobPage(1);
      setDebouncedSearchText(nextSearchText);
    }, 350);

    return () => window.clearTimeout(timeoutId);
  }, [debouncedSearchText, searchText]);

  const buildJobListQuery = useCallback(
    (statusOverride?: string): CandleFetchJobListQuery => ({
      provider: selectedProvider,
      status: statusOverride ?? (selectedStatus === "all" ? undefined : selectedStatus),
      market_pair: selectedMarket === "all" ? undefined : selectedMarket,
      interval: selectedInterval === "all" ? undefined : selectedInterval,
      search: debouncedSearchText || undefined
    }),
    [debouncedSearchText, selectedInterval, selectedMarket, selectedProvider, selectedStatus]
  );

  const buildJobSummaryQuery = useCallback(
    () => ({
      provider: selectedProvider,
      market_pair: selectedMarket === "all" ? undefined : selectedMarket,
      interval: selectedInterval === "all" ? undefined : selectedInterval,
      search: debouncedSearchText || undefined,
      timezone: displayTimezone
    }),
    [debouncedSearchText, displayTimezone, selectedInterval, selectedMarket, selectedProvider]
  );

  const buildJobOverviewQuery = useCallback(
    () => ({
      provider: selectedProvider,
      recent_limit: 8
    }),
    [selectedProvider]
  );

  useEffect(() => {
    let ignore = false;

    async function loadStorageTimezone() {
      try {
        const settings = await getStorageSettings();
        if (!ignore) {
          setDisplayTimezone(normalizeDisplayTimezone(settings.timezone));
        }
      } catch (error) {
        console.error(error);
        if (!ignore) {
          setDisplayTimezone(normalizeDisplayTimezone(getClientTimezone()));
        }
      }
    }

    void loadStorageTimezone();

    return () => {
      ignore = true;
    };
  }, []);

  const loadJobSummary = useCallback(async (options: { background?: boolean } = {}) => {
    try {
      const summary = await getCandleFetchJobSummary(buildJobSummaryQuery());
      setJobSummary(summary);
      setApiError(false);
    } catch (error) {
      console.error(error);
      if (!options.background) {
        setApiError(true);
      }
    }
  }, [buildJobSummaryQuery]);

  const loadJobOverview = useCallback(async (options: { background?: boolean } = {}) => {
    setOverviewLoading(true);
    try {
      const overview = await getCandleFetchJobOverview(buildJobOverviewQuery());
      setJobOverview(overview);
      setApiError(false);
    } catch (error) {
      console.error(error);
      if (!options.background) {
        setApiError(true);
      }
    } finally {
      setOverviewLoading(false);
    }
  }, [buildJobOverviewQuery]);

  const loadJobsPage = useCallback(async (options: { notify?: boolean; background?: boolean } = {}) => {
    if (options.background && autoRefreshInFlightRef.current) {
      return;
    }

    if (options.background) {
      autoRefreshInFlightRef.current = true;
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const offset = (jobPage - 1) * jobPageSize;
      const jobResponse = await listCandleFetchJobs({
        ...buildJobListQuery(),
        limit: jobPageSize,
        offset
      });
      const lastPage = Math.max(1, Math.ceil(jobResponse.count / jobPageSize));
      if (jobPage > lastPage) {
        setJobTotalCount(jobResponse.count);
        setJobPage(lastPage);
        return;
      }
      setJobs(jobResponse.jobs);
      setJobTotalCount(jobResponse.count);
      setApiError(false);
      if (options.notify) {
        void messageApi.success(t.refreshCompleted);
      }
    } catch (error) {
      console.error(error);
      setApiError(true);
      if (options.notify) {
        void messageApi.error(t.apiLoadFailed);
      }
    } finally {
      if (options.background) {
        autoRefreshInFlightRef.current = false;
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  }, [
    buildJobListQuery,
    jobPage,
    jobPageSize,
    messageApi,
    t.apiLoadFailed,
    t.refreshCompleted
  ]);

  const loadSchedulesPage = useCallback(async () => {
    setScheduleLoading(true);
    try {
      const offset = (schedulePage - 1) * schedulePageSize;
      const response = await listSchedules({
        provider: selectedProvider,
        limit: schedulePageSize,
        offset
      });
      const lastPage = Math.max(1, Math.ceil(response.count / schedulePageSize));
      if (schedulePage > lastPage) {
        setScheduleTotalCount(response.count);
        setSchedulePage(lastPage);
        return;
      }
      setSchedules(response.schedules);
      setScheduleTotalCount(response.count);
      setApiError(false);
    } catch (error) {
      console.error(error);
      setApiError(true);
    } finally {
      setScheduleLoading(false);
    }
  }, [schedulePage, schedulePageSize, selectedProvider]);

  const loadHistoryJobsPage = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const offset = (historyPage - 1) * historyPageSize;
      const response = await listCandleFetchJobs({
        ...buildJobListQuery(),
        limit: historyPageSize,
        offset
      });
      const lastPage = Math.max(1, Math.ceil(response.count / historyPageSize));
      if (historyPage > lastPage) {
        setHistoryTotalCount(response.count);
        setHistoryPage(lastPage);
        return;
      }
      setHistoryJobs(response.jobs);
      setHistoryTotalCount(response.count);
      setApiError(false);
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.apiLoadFailed);
    } finally {
      setHistoryLoading(false);
    }
  }, [buildJobListQuery, historyPage, historyPageSize, messageApi, t.apiLoadFailed]);

  const loadErrorJobsPage = useCallback(async () => {
    setErrorLoading(true);
    try {
      const offset = (errorPage - 1) * errorPageSize;
      const response = await listCandleFetchJobs({
        ...buildJobListQuery("failed"),
        limit: errorPageSize,
        offset
      });
      const lastPage = Math.max(1, Math.ceil(response.count / errorPageSize));
      if (errorPage > lastPage) {
        setErrorTotalCount(response.count);
        setErrorPage(lastPage);
        return;
      }
      setErrorJobs(response.jobs);
      setErrorTotalCount(response.count);
      setApiError(false);
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.apiLoadFailed);
    } finally {
      setErrorLoading(false);
    }
  }, [buildJobListQuery, errorPage, errorPageSize, messageApi, t.apiLoadFailed]);

  useEffect(() => {
    let ignore = false;

    async function loadMarketPairOptions() {
      setMarketOptionsLoading(true);
      try {
        const response = await listMarkets({
          provider: selectedProvider,
          enabled: true,
          limit: 200
        });
        if (!ignore) {
          setMarketPairOptions(response.markets.map(mapMarketToOption));
        }
      } catch (error) {
        console.error(error);
        if (!ignore) {
          void messageApi.error(t.assetLoadFailed);
        }
      } finally {
        if (!ignore) {
          setMarketOptionsLoading(false);
        }
      }
    }

    void loadMarketPairOptions();

    return () => {
      ignore = true;
    };
  }, [messageApi, selectedProvider, t.assetLoadFailed]);

  useEffect(() => {
    void loadJobsPage();
  }, [loadJobsPage]);

  useEffect(() => {
    void loadJobSummary();
  }, [loadJobSummary]);

  useEffect(() => {
    void loadJobOverview();
  }, [loadJobOverview]);

  useEffect(() => {
    void loadSchedulesPage();
  }, [loadSchedulesPage]);

  useEffect(() => {
    if (!historyModalOpen) {
      return;
    }
    void loadHistoryJobsPage();
  }, [historyModalOpen, loadHistoryJobsPage]);

  useEffect(() => {
    if (!errorModalOpen) {
      return;
    }
    void loadErrorJobsPage();
  }, [errorModalOpen, loadErrorJobsPage]);

  useEffect(() => {
    if (!scheduleModalOpen || isEditingSchedule) {
      return;
    }

    const currentMarketPair = form.getFieldValue("market_pair");
    if (!currentMarketPair && defaultMarketPair) {
      form.setFieldValue("market_pair", defaultMarketPair);
    }
  }, [defaultMarketPair, form, isEditingSchedule, scheduleModalOpen]);

  const replaceJob = useCallback((nextJob: CandleFetchJobResponse) => {
    setJobs((currentJobs) => {
      const hasJob = currentJobs.some((job) => job.id === nextJob.id);
      if (!hasJob) {
        return [nextJob, ...currentJobs];
      }
      return currentJobs.map((job) => (job.id === nextJob.id ? nextJob : job));
    });
  }, []);

  const handleOpenJobDetails = useCallback(
    async (jobId: string) => {
      const cachedJob = jobs.find((job) => job.id === jobId) ?? null;
      const cachedSchedule = cachedJob?.schedule_id ? scheduleById.get(cachedJob.schedule_id) ?? null : null;
      setSelectedDetailJob(cachedJob);
      setSelectedDetailSchedule(cachedSchedule);
      setDetailScheduleLoading(false);
      setDetailDrawerOpen(true);
      setDetailLoadingJobId(jobId);
      try {
        const latestJob = await getCandleFetchJob(jobId);
        setSelectedDetailJob(latestJob);
        replaceJob(latestJob);
        if (latestJob.schedule_id) {
          const currentSchedule = scheduleById.get(latestJob.schedule_id);
          if (currentSchedule) {
            setSelectedDetailSchedule(currentSchedule);
          } else {
            setDetailScheduleLoading(true);
            try {
              setSelectedDetailSchedule(await getSchedule(latestJob.schedule_id));
            } catch (scheduleError) {
              console.error(scheduleError);
              setSelectedDetailSchedule(null);
            } finally {
              setDetailScheduleLoading(false);
            }
          }
        } else {
          setSelectedDetailSchedule(null);
        }
        setApiError(false);
      } catch (error) {
        console.error(error);
        setApiError(true);
        void messageApi.error(t.detailLoadFailed);
      } finally {
        setDetailLoadingJobId(null);
      }
    },
    [jobs, messageApi, replaceJob, scheduleById, t.detailLoadFailed]
  );

  const closeJobDetails = () => {
    setDetailDrawerOpen(false);
    setSelectedDetailSchedule(null);
    setDetailScheduleLoading(false);
  };

  const openHistoryModal = () => {
    setHistoryPage(1);
    setHistoryModalOpen(true);
  };

  const openErrorModal = () => {
    setErrorPage(1);
    setErrorModalOpen(true);
  };

  const handleRefreshJobs = () => {
    void Promise.all([loadJobsPage({ notify: true }), loadJobSummary(), loadJobOverview()]);
  };

  const jobColumns = useMemo(
    () => getJobColumns(t, (jobId) => void handleOpenJobDetails(jobId), detailLoadingJobId),
    [detailLoadingJobId, handleOpenJobDetails, t]
  );

  const jobRows = useMemo(
    () => jobs.map((job) => mapJobToRow(job, scheduleById, displayTimezone)),
    [displayTimezone, jobs, scheduleById]
  );
  const executionRows = useMemo(
    () => (jobOverview?.recent_jobs ?? []).map((job) => mapJobToExecutionRow(job, displayTimezone)),
    [displayTimezone, jobOverview]
  );
  const allExecutionRows = useMemo(
    () => historyJobs.map((job) => mapJobToExecutionRow(job, displayTimezone)),
    [displayTimezone, historyJobs]
  );
  const failedExecutionRows = useMemo(
    () => errorJobs.map((job) => mapJobToExecutionRow(job, displayTimezone)),
    [displayTimezone, errorJobs]
  );
  const activeJob =
    jobs.find((job) => job.status === "running") ??
    jobs.find((job) => job.status === "pausing") ??
    jobs.find((job) => job.status === "paused") ??
    jobs.find((job) => job.status === "pending");
  const failedJob = jobOverview?.latest_failed_job ?? null;
  const hasAutoRefreshJob = useMemo(
    () => jobs.some((job) => AUTO_REFRESH_JOB_STATUSES.has(job.status)),
    [jobs]
  );
  const canPauseActiveJob = activeJob?.status === "running" || activeJob?.status === "pending";
  const canResumeActiveJob = activeJob?.status === "paused" || activeJob?.status === "pausing";
  const canStopActiveJob =
    activeJob?.status === "running" ||
    activeJob?.status === "pending" ||
    activeJob?.status === "pausing" ||
    activeJob?.status === "paused";

  useEffect(() => {
    if (!hasAutoRefreshJob) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      if (document.visibilityState === "hidden") {
        return;
      }
      void Promise.all([
        loadJobsPage({ background: true }),
        loadJobSummary({ background: true }),
        loadJobOverview({ background: true })
      ]);
    }, JOB_AUTO_REFRESH_MS);

    return () => window.clearInterval(intervalId);
  }, [hasAutoRefreshJob, loadJobOverview, loadJobSummary, loadJobsPage]);

  const statCards = [
    {
      label: t.stats.running,
      value: formatInteger(jobSummary?.running_count),
      icon: <PlayCircleOutlined />,
      tone: "blue"
    },
    {
      label: t.stats.queued,
      value: formatInteger(jobSummary?.queued_count),
      icon: <ClockCircleOutlined />,
      tone: "orange"
    },
    {
      label: t.stats.completed,
      value: formatInteger(jobSummary?.completed_today_count),
      icon: <CheckCircleOutlined />,
      tone: "green"
    },
    {
      label: t.stats.failed,
      value: formatInteger(jobSummary?.failed_count),
      icon: <WarningOutlined />,
      tone: "red"
    }
  ];

  const openCreateScheduleModal = () => {
    setEditingSchedule(null);
    form.resetFields();
    form.setFieldsValue({
      ...defaultScheduleFormValues,
      market_pair: defaultMarketPair
    });
    setScheduleModalOpen(true);
  };

  const openEditScheduleModal = (schedule: ScheduleResponse) => {
    setEditingSchedule(schedule);
    form.setFieldsValue(scheduleToFormValues(schedule));
    setScheduleModalOpen(true);
  };

  const openDetailScheduleModal = () => {
    if (!selectedDetailSchedule) {
      return;
    }

    setDetailDrawerOpen(false);
    openEditScheduleModal(selectedDetailSchedule);
  };

  const closeScheduleModal = () => {
    setScheduleModalOpen(false);
    setEditingSchedule(null);
    form.resetFields();
  };

  const handleSubmitSchedule = async (values: ScheduleFormValues) => {
    const startTime = toIsoString(values.start_time);
    if (!startTime) {
      return;
    }

    setSavingSchedule(true);
    try {
      const request = {
        provider: values.provider,
        market_type: "spot",
        market_pair: values.market_pair,
        interval: values.interval,
        mode: values.mode,
        cron_expression: values.cron_expression.trim(),
        timezone: editingSchedule?.timezone ?? "UTC",
        start_time: startTime,
        enabled: values.enabled,
        batch_limit: values.batch_limit,
        overlap_candles: values.overlap_candles,
        verify_continuity: values.verify_continuity,
        retry_attempts: values.retry_attempts,
        retry_delay_seconds: values.retry_delay_seconds
      } satisfies ScheduleCreateRequest;
      if (editingSchedule) {
        await updateSchedule(editingSchedule.id, request);
        void messageApi.success(t.scheduleUpdated);
      } else {
        await createSchedule(request);
        void messageApi.success(t.scheduleCreated);
      }
      closeScheduleModal();
      if (!editingSchedule && schedulePage !== 1) {
        setSchedulePage(1);
      } else {
        await loadSchedulesPage();
      }
    } catch (error) {
      console.error(error);
      setApiError(true);
      if (isDuplicateScheduleError(error)) {
        void messageApi.warning(t.scheduleDuplicate);
      } else {
        void messageApi.error(editingSchedule ? t.scheduleEditFailed : t.scheduleCreateFailed);
      }
    } finally {
      setSavingSchedule(false);
    }
  };

  const handleToggleSchedule = async (schedule: ScheduleResponse, enabled: boolean) => {
    setUpdatingScheduleId(schedule.id);
    try {
      await (enabled ? resumeSchedule(schedule.id) : pauseSchedule(schedule.id));
      void messageApi.success(enabled ? t.scheduleEnabled : t.scheduleDisabled);
      await loadSchedulesPage();
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.scheduleUpdateFailed);
    } finally {
      setUpdatingScheduleId(null);
    }
  };

  const handleDeleteSchedule = async (schedule: ScheduleResponse) => {
    setDeletingScheduleId(schedule.id);
    try {
      await deleteSchedule(schedule.id);
      void messageApi.success(t.scheduleDeleted);
      await loadSchedulesPage();
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.scheduleDeleteFailed);
    } finally {
      setDeletingScheduleId(null);
    }
  };

  const handleRunNow = async (schedule: ScheduleResponse) => {
    setRunningScheduleId(schedule.id);
    try {
      const job = await runScheduleNow(schedule.id);
      replaceJob(job);
      void messageApi.success(`${t.scheduleRunStarted}: ${job.id}`);
      await Promise.all([loadJobsPage(), loadJobSummary(), loadJobOverview(), loadSchedulesPage()]);
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.scheduleRunFailed);
    } finally {
      setRunningScheduleId(null);
    }
  };

  const handlePauseJob = async (job: CandleFetchJobResponse) => {
    setPausingJobId(job.id);
    try {
      const nextJob = await pauseCandleFetchJob(job.id);
      replaceJob(nextJob);
      void messageApi.success(t.pauseRequested);
      await Promise.all([loadJobsPage(), loadJobSummary(), loadJobOverview()]);
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.pauseFailed);
    } finally {
      setPausingJobId(null);
    }
  };

  const handleResumeJob = async (job: CandleFetchJobResponse) => {
    setResumingJobId(job.id);
    try {
      const nextJob = await resumeCandleFetchJob(job.id);
      replaceJob(nextJob);
      void messageApi.success(t.resumeRequested);
      await Promise.all([loadJobsPage(), loadJobSummary(), loadJobOverview()]);
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.resumeFailed);
    } finally {
      setResumingJobId(null);
    }
  };

  const handleStopJob = async (job: CandleFetchJobResponse) => {
    setStoppingJobId(job.id);
    try {
      await cancelCandleFetchJob(job.id);
      void messageApi.success(t.stopRequested);
      await Promise.all([loadJobsPage(), loadJobSummary(), loadJobOverview()]);
    } catch (error) {
      console.error(error);
      setApiError(true);
      void messageApi.error(t.stopFailed);
    } finally {
      setStoppingJobId(null);
    }
  };

  const handleSelectedMarketChange = (value: string) => {
    setJobPage(1);
    setSelectedMarket(value);
  };

  const handleSelectedStatusChange = (value: string) => {
    setJobPage(1);
    setSelectedStatus(value);
  };

  const handleSelectedIntervalChange = (value: string) => {
    setJobPage(1);
    setSelectedInterval(value);
  };

  return (
    <main className="page-stack jobs-page">
      {contextHolder}
      <div className="page-header">
        <div>
          <Typography.Title level={2}>{messages.jobs.title}</Typography.Title>
          <Typography.Text className="page-subtitle">{t.subtitle}</Typography.Text>
        </div>
      </div>

      {apiError ? <Typography.Text type="danger">{t.apiLoadFailed}</Typography.Text> : null}

      <Row gutter={[16, 16]}>
        {statCards.map((item) => (
          <Col xs={24} sm={12} xl={6} key={item.label}>
            <Card className={`panel-card job-stat-card job-stat-${item.tone}`} variant="borderless">
              <span className="job-stat-icon">{item.icon}</span>
              <span>
                <Typography.Text>{item.label}</Typography.Text>
                <strong>{item.value}</strong>
              </span>
            </Card>
          </Col>
        ))}
      </Row>

      <section className="jobs-layout">
        <Card title={t.queue} className="panel-card jobs-queue-card" variant="borderless">
          <div className="job-filter-bar">
            <label>
              <span>{t.asset}</span>
              <Select
                value={selectedMarket}
                showSearch
                loading={marketOptionsLoading}
                optionFilterProp="searchText"
                options={[
                  { label: t.all, value: "all", searchText: t.all },
                  ...visibleMarketPairOptions
                ]}
                onChange={handleSelectedMarketChange}
              />
            </label>
            <label>
              <span>{t.status}</span>
              <Select
                value={selectedStatus}
                options={[
                  { label: t.all, value: "all" },
                  { label: t.statusText.running, value: "running" },
                  { label: t.statusText.pausing, value: "pausing" },
                  { label: t.statusText.paused, value: "paused" },
                  { label: t.statusText.pending, value: "pending" },
                  { label: t.statusText.success, value: "success" },
                  { label: t.statusText.failed, value: "failed" },
                  { label: t.statusText.cancelled, value: "cancelled" }
                ]}
                onChange={handleSelectedStatusChange}
              />
            </label>
            <label>
              <span>{t.interval}</span>
              <Select
                value={selectedInterval}
                options={[{ label: t.all, value: "all" }, ...intervalOptions.map((value) => ({ label: value, value }))]}
                onChange={handleSelectedIntervalChange}
              />
            </label>
            <Input
              placeholder={t.search}
              prefix={<SearchOutlined />}
              allowClear
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
            />
            <Tooltip title={t.refresh}>
              <Button
                icon={<ReloadOutlined />}
                aria-label={t.refresh}
                loading={loading || refreshing}
                onClick={handleRefreshJobs}
              />
            </Tooltip>
          </div>

          <Table
            columns={jobColumns}
            dataSource={jobRows}
            loading={loading}
            size="middle"
            scroll={{ x: 1210 }}
            pagination={{
              current: jobPage,
              pageSize: jobPageSize,
              total: jobTotalCount,
              showSizeChanger: true,
              showTotal: (total, range) => `${range[0]}-${range[1]} / ${total}`,
              onChange: (nextPage, nextPageSize) => {
                setJobPage(nextPage);
                setJobPageSize(nextPageSize);
              }
            }}
          />
        </Card>

        <aside className="jobs-side-stack">
          <Card title={t.currentTask} className="panel-card current-job-card" variant="borderless">
            {activeJob ? (
              <>
                <div className="current-job-title">
                  <AssetMark asset={activeJob.market_pair} />
                  <strong>
                    {activeJob.market_pair} {activeJob.interval} {getModeLabel(activeJob.mode, t)}
                  </strong>
                  <StatusTag status={activeJob.status} labels={t.statusText} />
                </div>
                <Progress percent={Math.round(activeJob.progress_percent)} strokeColor="#2563eb" />
                <dl className="job-detail-list">
                  <div>
                    <dt>{t.sourceMarketLabel}</dt>
                    <dd>{`${getProviderLabel(activeJob.provider)} (${activeJob.market_pair})`}</dd>
                  </div>
                  <div>
                    <dt>{t.currentRange}</dt>
                    <dd>
                      {toDisplayDateTime(activeJob.requested_start_time, displayTimezone)} ~{" "}
                      {toDisplayDateTime(activeJob.current_cursor_time ?? activeJob.effective_end_time, displayTimezone)}
                    </dd>
                  </div>
                  <div>
                    <dt>{t.capturedRows}</dt>
                    <dd>
                      {formatInteger(activeJob.fetched_count)} / {formatInteger(activeJob.total_estimated_count)}
                    </dd>
                  </div>
                  <div>
                    <dt>{t.retryCount}</dt>
                    <dd>
                      {formatInteger(activeJob.failed_count)} / {formatInteger(activeJob.retry_attempts)}
                    </dd>
                  </div>
                </dl>
              </>
            ) : (
              <Typography.Text type="secondary">{t.noCurrentTask}</Typography.Text>
            )}
            <div className="job-card-actions">
              <Button
                icon={canResumeActiveJob ? <PlayCircleOutlined /> : <PauseOutlined />}
                disabled={!canPauseActiveJob && !canResumeActiveJob}
                loading={activeJob ? pausingJobId === activeJob.id || resumingJobId === activeJob.id : false}
                onClick={
                  activeJob
                    ? () => void (canResumeActiveJob ? handleResumeJob(activeJob) : handlePauseJob(activeJob))
                    : undefined
                }
              >
                {canResumeActiveJob ? t.resume : t.pause}
              </Button>
              <Button
                danger
                icon={<StopOutlined />}
                disabled={!canStopActiveJob}
                loading={activeJob ? stoppingJobId === activeJob.id : false}
                onClick={activeJob ? () => void handleStopJob(activeJob) : undefined}
              >
                {t.stop}
              </Button>
            </div>
          </Card>

          <Card
            title={t.schedule}
            className="panel-card schedule-card"
            variant="borderless"
            loading={scheduleLoading && schedules.length === 0}
            extra={
              <Button type="primary" ghost icon={<PlusOutlined />} onClick={openCreateScheduleModal}>
                {t.addSchedule}
              </Button>
            }
          >
            <div className="schedule-list" aria-busy={scheduleLoading}>
              {schedules.length === 0 ? (
                <div className="schedule-empty">
                  <Typography.Text type="secondary">{t.noSchedules}</Typography.Text>
                </div>
              ) : (
                schedules.map((schedule) => (
                  <div className="schedule-row" key={schedule.id}>
                    <div className="schedule-row-main">
                      <div className="schedule-row-title">
                        <AssetCell asset={schedule.market_pair} />
                        <Typography.Text className="schedule-row-name" title={schedule.name}>
                          {schedule.name}
                        </Typography.Text>
                      </div>
                      <Switch
                        checked={schedule.enabled}
                        loading={updatingScheduleId === schedule.id}
                        size="small"
                        aria-label={t.status}
                        onChange={(checked) => void handleToggleSchedule(schedule, checked)}
                      />
                    </div>
                    <dl className="schedule-row-meta">
                      <div>
                        <dt>{t.interval}</dt>
                        <dd>{schedule.interval}</dd>
                      </div>
                      <div>
                        <dt>{scheduleInfoLabels.mode}</dt>
                        <dd>{getModeLabel(schedule.mode, t)}</dd>
                      </div>
                      <div>
                        <dt>{t.frequency}</dt>
                        <dd>{schedule.cron_expression}</dd>
                      </div>
                      <div>
                        <dt>{scheduleInfoLabels.timezone}</dt>
                        <dd>{schedule.timezone}</dd>
                      </div>
                      <div>
                        <dt>{scheduleInfoLabels.lastRun}</dt>
                        <dd>{toDisplayDateTime(schedule.last_triggered_at, displayTimezone)}</dd>
                      </div>
                      <div>
                        <dt>{scheduleInfoLabels.nextRun}</dt>
                        <dd>{toDisplayDateTime(schedule.next_run_at, displayTimezone)}</dd>
                      </div>
                    </dl>
                    <div className="schedule-row-actions">
                      <Space size={4}>
                        <Button
                          type="text"
                          icon={<EditOutlined />}
                          aria-label={t.edit}
                          disabled={
                            savingSchedule ||
                            runningScheduleId === schedule.id ||
                            deletingScheduleId === schedule.id ||
                            updatingScheduleId === schedule.id
                          }
                          onClick={() => openEditScheduleModal(schedule)}
                        />
                        <Button
                          type="text"
                          icon={<PlayCircleOutlined />}
                          aria-label={t.runNow}
                          loading={runningScheduleId === schedule.id}
                          disabled={
                            savingSchedule ||
                            deletingScheduleId === schedule.id ||
                            updatingScheduleId === schedule.id
                          }
                          onClick={() => void handleRunNow(schedule)}
                        />
                        <Popconfirm
                          title={t.deleteScheduleConfirmTitle}
                          description={t.deleteScheduleConfirmDescription}
                          okText={t.delete}
                          cancelText={t.cancel}
                          okButtonProps={{ danger: true, loading: deletingScheduleId === schedule.id }}
                          onConfirm={() => void handleDeleteSchedule(schedule)}
                        >
                          <Button
                            type="text"
                            danger
                            icon={<DeleteOutlined />}
                            aria-label={t.delete}
                            loading={deletingScheduleId === schedule.id}
                            disabled={
                              savingSchedule ||
                              runningScheduleId === schedule.id ||
                              updatingScheduleId === schedule.id
                            }
                          />
                        </Popconfirm>
                      </Space>
                    </div>
                  </div>
                ))
              )}
            </div>
            {scheduleTotalCount > 0 ? (
              <div className="schedule-pagination">
                <Pagination
                  size="small"
                  current={schedulePage}
                  pageSize={schedulePageSize}
                  total={scheduleTotalCount}
                  disabled={scheduleLoading}
                  showSizeChanger
                  pageSizeOptions={["5", "10", "20"]}
                  showTotal={(total, range) => `${range[0]}-${range[1]} / ${total}`}
                  onChange={(nextPage, nextPageSize) => {
                    setSchedulePage(nextPage);
                    setSchedulePageSize(nextPageSize);
                  }}
                />
              </div>
            ) : null}
          </Card>
        </aside>
      </section>

      <section className="jobs-bottom-grid">
        <Card
          title={t.recentRuns}
          className="panel-card"
          variant="borderless"
          extra={<Button type="link" onClick={openHistoryModal}>{t.viewAllRecords}</Button>}
        >
          <Table
            columns={executionColumns}
            dataSource={executionRows}
            loading={overviewLoading && !jobOverview}
            size="middle"
            pagination={false}
            scroll={{ x: 940 }}
          />
        </Card>

        <Card
          title={
            <span className="error-card-title">
              <ExclamationCircleOutlined />
              {t.errorSummary}
            </span>
          }
          className="panel-card error-summary-card"
          variant="borderless"
          extra={<Button type="link" onClick={openErrorModal}>{t.viewAllErrors}</Button>}
        >
          {failedJob ? (
            <>
              <div className="error-summary-box">
                <Tag color="red">{t.statusText.failed}</Tag>
                <div className="error-summary-row">
                  <strong>{failedJob.id}</strong>
                  <span>
                    {failedJob.market_pair} {failedJob.interval} {getModeLabel(failedJob.mode, t)}
                  </span>
                  <StatusTag status={failedJob.status} labels={t.statusText} />
                </div>
                <Typography.Text type="secondary">{toDisplayDateTime(failedJob.finished_at ?? failedJob.updated_at, displayTimezone)}</Typography.Text>
                <Typography.Paragraph>{failedJob.error_message ?? "-"}</Typography.Paragraph>
              </div>
              <div className="error-summary-footer">
                <span>
                  {t.stats.failed}: {formatInteger(jobOverview?.failed_count)}
                </span>
                <span>
                  {t.lastUpdated}: {toDisplayDateTime(failedJob.updated_at, displayTimezone)}
                </span>
                <Button
                  type="text"
                  icon={<ReloadOutlined />}
                  aria-label={t.refresh}
                  loading={loading || refreshing || overviewLoading}
                  onClick={handleRefreshJobs}
                />
              </div>
            </>
          ) : (
            <Typography.Text type="secondary">{t.noErrors}</Typography.Text>
          )}
        </Card>
      </section>

      <Drawer
        title={
          selectedDetailJob ? (
            <span className="job-detail-drawer-title">
              <AssetMark asset={selectedDetailJob.market_pair} />
              <span>
                {selectedDetailJob.market_pair} {selectedDetailJob.interval}
              </span>
              <StatusTag status={selectedDetailJob.status} labels={t.statusText} />
            </span>
          ) : (
            t.jobDetails
          )
        }
        className="job-detail-drawer"
        open={detailDrawerOpen}
        width={720}
        onClose={closeJobDetails}
      >
        {selectedDetailJob ? (
          <div className="job-detail-drawer-content">
            <div className="job-detail-summary">
              <div>
                <Typography.Text type="secondary">{t.taskId}</Typography.Text>
                <Typography.Title level={4}>{selectedDetailJob.id}</Typography.Title>
              </div>
              <Progress percent={Math.round(selectedDetailJob.progress_percent)} strokeColor="#2563eb" />
            </div>

            <DetailSection title={t.basicInfo}>
              <DetailItem label={t.jobType} value={selectedDetailJob.job_type} />
              <DetailItem label={t.triggerType} value={selectedDetailJob.trigger_type} />
              <DetailItem
                label={t.scheduleId}
                value={
                  selectedDetailJob.schedule_id ? (
                    <div className="job-detail-schedule-link">
                      <Tag color="blue">{selectedDetailJob.schedule_id}</Tag>
                      {detailScheduleLoading ? (
                        <Typography.Text type="secondary">{t.loadingDetails}</Typography.Text>
                      ) : selectedDetailSchedule ? (
                        <>
                          <Typography.Text>{selectedDetailSchedule.name}</Typography.Text>
                          <Button type="link" size="small" onClick={openDetailScheduleModal}>
                            {t.editSchedule}
                          </Button>
                        </>
                      ) : null}
                    </div>
                  ) : (
                    "-"
                  )
                }
              />
              <DetailItem label={t.provider} value={getProviderLabel(selectedDetailJob.provider)} />
              <DetailItem label={t.marketType} value={selectedDetailJob.market_type} />
              <DetailItem label={t.exchangeSymbol} value={selectedDetailJob.exchange_symbol} />
              <DetailItem label={t.mode} value={getModeLabel(selectedDetailJob.mode, t)} />
            </DetailSection>

            <DetailSection title={t.fetchStatus}>
              <DetailItem label={t.status} value={<StatusTag status={selectedDetailJob.status} labels={t.statusText} />} />
              <DetailItem
                label={t.capturedRows}
                value={`${formatInteger(selectedDetailJob.fetched_count)} / ${formatInteger(selectedDetailJob.total_estimated_count)}`}
              />
              <DetailItem
                label={t.batchProgress}
                value={`${formatInteger(selectedDetailJob.completed_batch_count)} / ${formatInteger(selectedDetailJob.total_batch_count)}`}
              />
              <DetailItem label={t.missingCount} value={formatInteger(selectedDetailJob.missing_count)} />
              <DetailItem
                label={t.retryCount}
                value={`${formatInteger(selectedDetailJob.failed_count)} / ${formatInteger(selectedDetailJob.retry_attempts)}`}
              />
            </DetailSection>

            <DetailSection title={t.timeInfo}>
              <DetailItem
                label={t.requestedRange}
                value={formatDateRange(
                  selectedDetailJob.requested_start_time,
                  selectedDetailJob.requested_end_time,
                  displayTimezone
                )}
              />
              <DetailItem
                label={t.effectiveRange}
                value={formatDateRange(
                  selectedDetailJob.effective_start_time,
                  selectedDetailJob.effective_end_time,
                  displayTimezone
                )}
              />
              <DetailItem label={t.cursor} value={toDisplayDateTime(selectedDetailJob.current_cursor_time, displayTimezone)} />
              <DetailItem label={t.createdAt} value={toDisplayDateTime(selectedDetailJob.created_at, displayTimezone)} />
              <DetailItem label={t.startedAt} value={toDisplayDateTime(selectedDetailJob.started_at, displayTimezone)} />
              <DetailItem label={t.finishedAt} value={toDisplayDateTime(selectedDetailJob.finished_at, displayTimezone)} />
              <DetailItem label={t.updatedAt} value={toDisplayDateTime(selectedDetailJob.updated_at, displayTimezone)} />
              <DetailItem
                label={t.duration}
                value={formatDuration(selectedDetailJob.started_at, selectedDetailJob.finished_at ?? selectedDetailJob.updated_at)}
              />
            </DetailSection>

            <DetailSection title={t.fetchParameters}>
              <DetailItem label={t.batchLimit} value={formatInteger(selectedDetailJob.batch_limit)} />
              <DetailItem label={t.overlap} value={formatInteger(selectedDetailJob.overlap_candles)} />
              <DetailItem label={t.validateRows} value={formatBoolean(selectedDetailJob.verify_continuity, t)} />
              <DetailItem label={t.closedOnly} value={formatBoolean(selectedDetailJob.closed_only, t)} />
              <DetailItem label={t.retryAttempts} value={formatInteger(selectedDetailJob.retry_attempts)} />
              <DetailItem label={t.retryDelay} value={selectedDetailJob.retry_delay_seconds.toLocaleString()} />
            </DetailSection>

            <DetailSection title={t.errorMessage}>
              <Typography.Paragraph className="job-detail-error">
                {selectedDetailJob.error_message ?? t.noErrorMessage}
              </Typography.Paragraph>
            </DetailSection>
          </div>
        ) : (
          <Typography.Text type="secondary">{t.loadingDetails}</Typography.Text>
        )}
      </Drawer>

      <Modal
        title={isEditingSchedule ? t.editSchedule : t.createSchedule}
        open={scheduleModalOpen}
        okText={isEditingSchedule ? t.editSchedule : t.createSchedule}
        cancelText={t.cancel}
        confirmLoading={savingSchedule}
        onCancel={closeScheduleModal}
        onOk={() => void form.submit()}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={defaultScheduleFormValues}
          onFinish={(values) => void handleSubmitSchedule(values)}
        >
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="provider" label={t.provider} rules={[{ required: true }]}>
                <Select options={[{ value: selectedProvider, label: getProviderLabel(selectedProvider) }]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="market_pair" label={t.asset} rules={[{ required: true }]}>
                <Select
                  showSearch
                  loading={marketOptionsLoading}
                  optionFilterProp="searchText"
                  options={scheduleMarketPairOptions}
                  placeholder={marketOptionsLoading ? t.loadingAssets : t.noAssets}
                  notFoundContent={marketOptionsLoading ? t.loadingAssets : t.noAssets}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="interval" label={t.interval} rules={[{ required: true }]}>
                <Select options={intervalOptions.map((value) => ({ value, label: value }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="mode" label={t.mode} rules={[{ required: true }]}>
                <Select options={modeOptions.map((value) => ({ value, label: getModeLabel(value, t) }))} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="cron_expression" label={t.frequency} rules={[{ required: true }]}>
            <Input placeholder="*/5 * * * *" />
          </Form.Item>
          <Form.Item name="start_time" label={t.startTime} rules={[{ required: true }]}>
            <DatePicker showTime className="full-width" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="batch_limit" label={t.batchLimit} rules={[{ required: true }]}>
                <InputNumber min={1} max={1000} className="full-width" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="overlap_candles" label={t.overlap} rules={[{ required: true }]}>
                <InputNumber min={0} max={20} className="full-width" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="retry_attempts" label={t.retryAttempts} rules={[{ required: true }]}>
                <InputNumber min={0} max={5} className="full-width" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="retry_delay_seconds" label={t.retryDelay} rules={[{ required: true }]}>
                <InputNumber min={0} max={5} step={0.25} className="full-width" />
              </Form.Item>
            </Col>
          </Row>
          <Space>
            <Form.Item name="enabled" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Typography.Text>{t.status}</Typography.Text>
            <Form.Item name="verify_continuity" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Typography.Text>{t.validateRows}</Typography.Text>
          </Space>
        </Form>
      </Modal>

      <Modal
        title={t.allRecordsTitle}
        open={historyModalOpen}
        footer={null}
        width={980}
        onCancel={() => setHistoryModalOpen(false)}
      >
        <Table
          columns={executionColumns}
          dataSource={allExecutionRows}
          loading={historyLoading}
          locale={{ emptyText: t.noRunRecords }}
          pagination={{
            current: historyPage,
            pageSize: historyPageSize,
            total: historyTotalCount,
            showSizeChanger: true,
            showTotal: (total, range) => `${range[0]}-${range[1]} / ${total}`,
            onChange: (nextPage, nextPageSize) => {
              setHistoryPage(nextPage);
              setHistoryPageSize(nextPageSize);
            }
          }}
          scroll={{ x: 940 }}
          size="middle"
        />
      </Modal>

      <Modal
        title={t.allErrorsTitle}
        open={errorModalOpen}
        footer={null}
        width={980}
        onCancel={() => setErrorModalOpen(false)}
      >
        <Table
          columns={executionColumns}
          dataSource={failedExecutionRows}
          loading={errorLoading}
          locale={{ emptyText: t.noErrors }}
          pagination={{
            current: errorPage,
            pageSize: errorPageSize,
            total: errorTotalCount,
            showSizeChanger: true,
            showTotal: (total, range) => `${range[0]}-${range[1]} / ${total}`,
            onChange: (nextPage, nextPageSize) => {
              setErrorPage(nextPage);
              setErrorPageSize(nextPageSize);
            }
          }}
          scroll={{ x: 940 }}
          size="middle"
        />
      </Modal>
    </main>
  );
}
