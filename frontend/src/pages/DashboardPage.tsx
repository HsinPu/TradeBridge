import { RightOutlined } from "@ant-design/icons";
import { Alert, Badge, Button, Card, Col, Row, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";

import { CoveragePanel } from "../features/market-data/components/CoveragePanel";
import { ProviderStatusPanel } from "../features/market-data/components/ProviderStatusPanel";
import { SummaryCard } from "../features/market-data/components/SummaryCard";
import {
  DEFAULT_MARKET_DATA_PROVIDER,
  getDashboardOverview,
  MARKET_DATA_PROVIDER_LABELS
} from "../features/market-data/api";
import type {
  CandleFetchJobResponse,
  DashboardCoverageItemResponse,
  DashboardMetricsResponse,
  DashboardOverviewResponse,
  MarketDataProviderName
} from "../features/market-data/api";
import type { CoverageRow, PriceSnapshot, SyncActivity } from "../features/market-data/types";
import type { AppMessages } from "../shared/i18n/messages";

type DashboardPageProps = {
  messages: AppMessages;
};

const DEFAULT_DASHBOARD_INTERVAL = "1m";

function getDashboardSnapshots(
  messages: AppMessages,
  overview: DashboardOverviewResponse | null
): PriceSnapshot[] {
  const metrics = overview?.metrics;
  const providerHealthy = overview?.provider_status.healthy ?? true;
  const hasLatestSync = Boolean(metrics?.latest_sync_at);
  const hasLatestCandle = Boolean(metrics?.latest_candle_time);
  return [
    {
      label: messages.dashboard.kpis.trackedSymbols.label,
      value: metrics ? formatInteger(metrics.tracked_market_count) : "--",
      detail: formatMarketDetail(overview?.coverage) ?? messages.dashboard.kpis.trackedSymbols.detail,
      trend: `+${metrics?.tracked_market_count ?? 0}`,
      sparkline: [24, 28, 24, 31, 35, 30, 42, 48],
      tone: "success"
    },
    {
      label: messages.dashboard.kpis.storedCandles.label,
      value: metrics ? formatCompactNumber(metrics.stored_candle_count) : "--",
      detail: hasLatestCandle
        ? formatDateTime(metrics?.latest_candle_time) ?? messages.dashboard.kpis.storedCandles.detail
        : messages.common.noData,
      trend: overview?.interval ?? DEFAULT_DASHBOARD_INTERVAL,
      sparkline: [32, 34, 41, 35, 45, 48, 42, 58],
      tone: hasLatestCandle ? "success" : "neutral"
    },
    {
      label: messages.dashboard.kpis.latestSync.label,
      value: formatTime(metrics?.latest_sync_at) ?? "--",
      detail: hasLatestSync
        ? formatDateTime(metrics?.latest_sync_at) ?? messages.dashboard.kpis.latestSync.detail
        : messages.common.noData,
      trend: hasLatestSync
        ? providerHealthy ? messages.common.success : messages.common.warning
        : messages.common.noData,
      sparkline: [22, 43, 27, 31, 24, 44, 38, 51],
      tone: hasLatestSync ? providerHealthy ? "success" : "warning" : "neutral"
    },
    {
      label: messages.dashboard.kpis.dataGaps.label,
      value: metrics?.data_gap_count === null || metrics?.data_gap_count === undefined
        ? "--"
        : formatInteger(metrics.data_gap_count),
      detail: formatDataGapDetail(metrics, messages),
      trend: formatDataGapTrend(metrics, messages),
      sparkline: [20, 24, 28, 22, 21, 26, 33, 42],
      tone: resolveDataGapTone(metrics)
    }
  ];
}

function getActivityColumns(messages: AppMessages): ColumnsType<SyncActivity> {
  const statusLabel = {
    success: messages.common.success,
    warning: messages.common.warning,
    failed: messages.common.failed
  };

  return [
    { title: messages.dashboard.table.time, dataIndex: "time", key: "time", width: 96 },
    {
      title: messages.dashboard.table.source,
      dataIndex: "source",
      key: "source",
      width: 120,
      render: (source: string) => (
        <span className="source-cell">
          <span className="source-icon">{source.slice(0, 1) || "?"}</span>
          {source}
        </span>
      )
    },
    { title: messages.dashboard.table.symbol, dataIndex: "symbol", key: "symbol", width: 136 },
    { title: messages.dashboard.table.interval, dataIndex: "interval", key: "interval", width: 90 },
    {
      title: messages.dashboard.table.rows,
      dataIndex: "rows",
      key: "rows",
      width: 90,
      render: (rows: number) => rows.toLocaleString()
    },
    {
      title: messages.dashboard.table.status,
      dataIndex: "status",
      key: "status",
      width: 112,
      render: (status: SyncActivity["status"]) => (
        <Tag color={status === "success" ? "green" : status === "warning" ? "gold" : "red"}>
          {statusLabel[status]}
        </Tag>
      )
    },
    { title: messages.dashboard.table.duration, dataIndex: "duration", key: "duration", width: 110 }
  ];
}

export function DashboardPage({ messages }: DashboardPageProps) {
  const [coverageInterval, setCoverageInterval] = useState(DEFAULT_DASHBOARD_INTERVAL);
  const [dashboardOverview, setDashboardOverview] = useState<DashboardOverviewResponse | null>(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(false);
  const dashboardSnapshots = useMemo(
    () => getDashboardSnapshots(messages, dashboardOverview),
    [dashboardOverview, messages]
  );
  const activityColumns = useMemo(() => getActivityColumns(messages), [messages]);
  const coverageRows = useMemo(
    () => mapCoverageRows(dashboardOverview?.coverage ?? []),
    [dashboardOverview]
  );
  const activityRows = useMemo(
    () => mapRecentJobs(dashboardOverview?.recent_jobs ?? []),
    [dashboardOverview]
  );
  const coverageRangeLabel = useMemo(
    () => dashboardOverview ? formatCoverageRange(dashboardOverview.coverage) ?? "--" : undefined,
    [dashboardOverview]
  );
  const alertCount = dashboardOverview?.job_summary.failed_count ?? 0;

  useEffect(() => {
    let isActive = true;
    setIsDashboardLoading(true);
    getDashboardOverview({
      provider: DEFAULT_MARKET_DATA_PROVIDER,
      interval: coverageInterval,
      market_limit: 20,
      activity_limit: 8
    })
      .then((overview) => {
        if (isActive) {
          setDashboardOverview(overview);
        }
      })
      .catch(() => {
        if (isActive) {
          setDashboardOverview(null);
        }
      })
      .finally(() => {
        if (isActive) {
          setIsDashboardLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [coverageInterval]);

  return (
    <main className="page-stack">
      <div className="page-header">
        <div>
          <Typography.Title level={2}>{messages.dashboard.title}</Typography.Title>
          <Typography.Text className="page-subtitle">{messages.dashboard.subtitle}</Typography.Text>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        {dashboardSnapshots.map((snapshot) => (
          <Col xs={24} sm={12} xl={12} xxl={6} key={snapshot.label}>
            <SummaryCard snapshot={snapshot} />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} align="stretch" className="dashboard-status-row">
        <Col xs={24} xl={15}>
          <CoveragePanel
            messages={messages}
            rows={coverageRows}
            interval={coverageInterval}
            coverageRange={coverageRangeLabel}
            onIntervalChange={setCoverageInterval}
          />
        </Col>
        <Col xs={24} xl={9}>
          <ProviderStatusPanel messages={messages} status={dashboardOverview?.provider_status} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card title={messages.dashboard.recentSyncActivity} className="panel-card" variant="borderless">
            <Table
              columns={activityColumns}
              dataSource={activityRows}
              loading={isDashboardLoading && activityRows.length === 0}
              size="middle"
              pagination={false}
              scroll={{ x: 720 }}
              className="activity-table"
            />
            <Button type="link" className="view-all-button">
              {messages.dashboard.viewAllActivities}
            </Button>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Space direction="vertical" size={16} className="full-width">
            <Card
              className="panel-card alerts-card"
              variant="borderless"
              title={
                <span className="alerts-title">
                  {messages.dashboard.alerts}
                  <Badge count={alertCount} />
                </span>
              }
              extra={<Button type="link" icon={<RightOutlined />}>{messages.dashboard.viewAllAlerts}</Button>}
            >
              <Space direction="vertical" size={10} className="full-width">
                <Alert
                  type={dashboardOverview?.latest_failed_job ? "warning" : "info"}
                  showIcon
                  message={formatLatestFailure(messages, dashboardOverview?.latest_failed_job)}
                />
                <Alert type="info" showIcon message={messages.dashboard.noScheduledJobs} />
              </Space>
            </Card>
          </Space>
        </Col>
      </Row>
    </main>
  );
}

function mapCoverageRows(items: DashboardCoverageItemResponse[]): CoverageRow[] {
  return items.map((item) => ({
    symbol: item.market_pair,
    interval: item.interval,
    coveragePercent: Math.max(0, Math.min(100, item.coverage_percent)),
    latestCandle: item.last_open_time ?? "--",
    missingRanges: item.missing_count,
    health: normalizeCoverageHealth(item.health),
    segments: buildCoverageSegments(item),
    dateLabels: buildCoverageDateLabels(item.first_open_time_ms, item.last_open_time_ms)
  }));
}

function buildCoverageSegments(item: DashboardCoverageItemResponse): CoverageRow["segments"] {
  const candleCount = Math.max(0, item.candle_count);
  const missingCount = Math.max(0, item.missing_count ?? 0);
  if (candleCount === 0 && missingCount === 0) {
    return [{ status: "empty", width: 1 }];
  }
  if (missingCount === 0) {
    return [{ status: "available", width: 1 }];
  }
  if (candleCount === 0) {
    return [{ status: "missing", width: 1 }];
  }
  return [
    { status: "available", width: candleCount },
    { status: "missing", width: Math.max(missingCount, 1) }
  ];
}

function normalizeCoverageHealth(health: DashboardCoverageItemResponse["health"]): CoverageRow["health"] {
  if (health === "healthy" || health === "error") {
    return health;
  }
  return "warning";
}

function formatDataGapDetail(metrics: DashboardMetricsResponse | null | undefined, messages: AppMessages) {
  if (!metrics) {
    return messages.common.noData;
  }
  if (metrics.gap_check_status === "complete") {
    return messages.common.complete;
  }
  if (metrics.gap_check_status === "not_checked") {
    return messages.common.warning;
  }
  return formatDateTime(metrics.first_data_gap_time) ?? messages.dashboard.kpis.dataGaps.detail;
}

function formatDataGapTrend(metrics: DashboardMetricsResponse | null | undefined, messages: AppMessages) {
  if (!metrics) {
    return "--";
  }
  if (metrics.gap_check_status === "repair_failed") {
    return `${formatInteger(metrics.data_gap_failed_count)} ${messages.common.failed}`;
  }
  if (metrics.gap_check_status === "repairing") {
    return `${formatInteger(metrics.data_gap_repairing_count)} ${messages.common.warning}`;
  }
  if (metrics.gap_check_status === "gaps_detected") {
    return `${formatInteger(metrics.data_gap_count)} ${messages.common.gaps}`;
  }
  if (metrics.gap_check_status === "complete") {
    return messages.common.success;
  }
  return messages.common.warning;
}

function resolveDataGapTone(metrics: DashboardMetricsResponse | null | undefined): PriceSnapshot["tone"] {
  if (!metrics) {
    return "neutral";
  }
  if (metrics.gap_check_status === "repair_failed" || metrics.data_gap_failed_count > 0) {
    return "danger";
  }
  if (metrics.gap_check_status === "repairing" || metrics.gap_check_status === "gaps_detected") {
    return "warning";
  }
  if (metrics.gap_check_status === "not_checked") {
    return "warning";
  }
  return "success";
}

function mapRecentJobs(jobs: CandleFetchJobResponse[]): SyncActivity[] {
  return jobs.map((job) => ({
    key: job.id,
    time: formatTime(job.finished_at ?? job.started_at ?? job.created_at) ?? "--",
    source: getProviderLabel(job.provider),
    symbol: job.market_pair,
    interval: job.interval,
    rows: job.saved_count || job.fetched_count,
    status: mapJobStatus(job.status),
    duration: formatJobDuration(job)
  }));
}

function mapJobStatus(status: CandleFetchJobResponse["status"]): SyncActivity["status"] {
  if (status === "success") {
    return "success";
  }
  if (status === "failed" || status === "cancelled") {
    return "failed";
  }
  return "warning";
}

function formatJobDuration(job: CandleFetchJobResponse) {
  if (!job.started_at || !job.finished_at) {
    return `${Math.round(job.progress_percent)}%`;
  }
  const finishedAt = parseBackendDate(job.finished_at);
  const startedAt = parseBackendDate(job.started_at);
  if (!finishedAt || !startedAt) {
    return "--";
  }
  const durationMs = finishedAt.getTime() - startedAt.getTime();
  if (!Number.isFinite(durationMs) || durationMs < 0) {
    return "--";
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  return `${(durationMs / 1000).toFixed(2)} s`;
}

function formatLatestFailure(messages: AppMessages, job: CandleFetchJobResponse | null | undefined) {
  if (!job) {
    return messages.common.complete;
  }
  return `${job.market_pair} ${job.interval} ${messages.common.failed}${job.error_message ? `: ${job.error_message}` : ""}`;
}

function formatCoverageRange(items: DashboardCoverageItemResponse[] | undefined) {
  if (!items || items.length === 0) {
    return undefined;
  }
  const firstTime = minNumber(items.map((item) => item.first_open_time_ms));
  const lastTime = maxNumber(items.map((item) => item.last_open_time_ms));
  if (firstTime === null || lastTime === null) {
    return undefined;
  }
  return `${formatMonthDay(firstTime)} ~ ${formatMonthDay(lastTime)}`;
}

function buildCoverageDateLabels(firstTimeMs: number | null, lastTimeMs: number | null) {
  if (firstTimeMs === null || lastTimeMs === null || firstTimeMs > lastTimeMs) {
    return ["--", "--", "--", "--", "--", "--", "--", "--"];
  }
  if (firstTimeMs === lastTimeMs) {
    return Array.from({ length: 8 }, () => formatMonthDay(firstTimeMs));
  }
  const step = (lastTimeMs - firstTimeMs) / 7;
  return Array.from({ length: 8 }, (_, index) => formatMonthDay(firstTimeMs + step * index));
}

function formatMarketDetail(items: DashboardCoverageItemResponse[] | undefined) {
  if (!items || items.length === 0) {
    return null;
  }
  const symbols = items.map((item) => item.market_pair);
  const visibleSymbols = symbols.slice(0, 2).join(" / ");
  const hiddenCount = symbols.length - 2;
  return hiddenCount > 0 ? `${visibleSymbols} +${hiddenCount}` : visibleSymbols;
}

function formatInteger(value: number | null | undefined) {
  return (value ?? 0).toLocaleString();
}

function formatCompactNumber(value: number | null | undefined) {
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 2
  }).format(value ?? 0);
}

function formatDateTime(value: string | null | undefined) {
  const date = parseBackendDate(value);
  if (!date) {
    return value;
  }
  return date.toLocaleString(undefined, {
    hour12: false
  });
}

function formatTime(value: string | null | undefined) {
  const date = parseBackendDate(value);
  if (!date) {
    return value;
  }
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
}

function parseBackendDate(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
  const date = new Date(hasTimezone ? normalized : `${normalized}+00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatMonthDay(value: number) {
  const date = new Date(value);
  return date.toLocaleDateString(undefined, {
    month: "2-digit",
    day: "2-digit"
  });
}

function minNumber(values: Array<number | null>) {
  return values.reduce<number | null>((selected, value) => {
    if (value === null) {
      return selected;
    }
    return selected === null ? value : Math.min(selected, value);
  }, null);
}

function maxNumber(values: Array<number | null>) {
  return values.reduce<number | null>((selected, value) => {
    if (value === null) {
      return selected;
    }
    return selected === null ? value : Math.max(selected, value);
  }, null);
}

function getProviderLabel(provider: string) {
  return MARKET_DATA_PROVIDER_LABELS[provider as MarketDataProviderName] ?? provider;
}
