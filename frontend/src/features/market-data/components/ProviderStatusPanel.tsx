import {
  ApiOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FieldTimeOutlined,
  SafetyCertificateOutlined,
  WarningOutlined
} from "@ant-design/icons";
import { Card, Progress, Space, Tag, Typography } from "antd";

import { MARKET_DATA_PROVIDER_LABELS } from "../api";
import type { DashboardProviderStatusResponse, MarketDataProviderName } from "../api";
import type { AppMessages } from "../../../shared/i18n/messages";

type ProviderStatusPanelProps = {
  messages: AppMessages;
  status?: DashboardProviderStatusResponse;
};

export function ProviderStatusPanel({ messages, status }: ProviderStatusPanelProps) {
  const providerLabel = getProviderLabel(status?.provider);
  const quotaPercent = status?.request_quota_percent ?? 0;
  const isHealthy = status?.healthy ?? true;

  return (
    <Card
      title={messages.dashboard.providerStatus}
      className="panel-card status-fill-card provider-status-card"
      variant="borderless"
    >
      <Space direction="vertical" size={0} className="full-width provider-table">
        <div className="provider-health">
          <span className="provider-logo"><ApiOutlined /></span>
          <div>
            <Typography.Text className="provider-title">{providerLabel}</Typography.Text>
            <Typography.Text className="provider-subtitle">
              {messages.provider.marketEndpoint}
            </Typography.Text>
          </div>
          <Tag color={isHealthy ? "green" : "gold"}>
            {isHealthy ? messages.common.healthy : messages.common.warning}
          </Tag>
        </div>
        <div className="provider-row">
          <span><FieldTimeOutlined /> {messages.provider.latency}</span>
          <strong className="positive-text">{formatLatency(status?.latency_ms)}</strong>
        </div>
        <div className="provider-row provider-row-progress">
          <span><ApiOutlined /> {messages.provider.requestQuota}</span>
          <strong>{formatPercent(status?.request_quota_percent)}</strong>
          <Progress percent={quotaPercent} showInfo={false} strokeColor="#16a34a" />
        </div>
        <div className="provider-row">
          <span><WarningOutlined /> {messages.provider.errorRate}</span>
          <strong className="positive-text">{formatPercent(status?.error_rate_percent)}</strong>
        </div>
        <div className="provider-row">
          <span><SafetyCertificateOutlined /> {messages.provider.lastSuccessfulResponse}</span>
          <strong>{formatDateTime(status?.last_successful_response)}</strong>
        </div>
        <div className="provider-row">
          <span><ClockCircleOutlined /> {messages.provider.status}</span>
          <strong className="positive-text">
            {isHealthy ? messages.provider.allSystemsOperational : messages.common.warning}
          </strong>
        </div>
        <div className="provider-row provider-row-mobile-only">
          <span>{messages.provider.lastSuccessfulResponse}</span>
          <strong>{formatTime(status?.last_successful_response)}</strong>
        </div>
      </Space>
    </Card>
  );
}

function getProviderLabel(provider: string | undefined) {
  if (!provider) {
    return MARKET_DATA_PROVIDER_LABELS.binance;
  }
  return MARKET_DATA_PROVIDER_LABELS[provider as MarketDataProviderName] ?? provider;
}

function formatLatency(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : `${value} ms`;
}

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : `${value.toFixed(1)}%`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleString();
}

function formatTime(value: string | null | undefined) {
  if (!value) {
    return "--";
  }
  return new Date(value).toLocaleTimeString();
}
