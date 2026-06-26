import { CalendarOutlined, CheckCircleOutlined, ExclamationCircleOutlined, InfoCircleOutlined } from "@ant-design/icons";
import { Card, Segmented, Space, Tag, Typography } from "antd";

import { coverageRows } from "../mockData";
import type { CoverageRow } from "../types";
import type { AppMessages } from "../../../shared/i18n/messages";

type CoveragePanelProps = {
  messages: AppMessages;
  rows?: CoverageRow[];
  interval?: string;
  coverageRange?: string;
  onIntervalChange?: (interval: string) => void;
};

const defaultCoverageDateLabels = ["06-12", "06-13", "06-14", "06-15", "06-16", "06-17", "06-18", "06-19"];

export function CoveragePanel({
  messages,
  rows = coverageRows,
  interval = "1m",
  coverageRange,
  onIntervalChange
}: CoveragePanelProps) {
  return (
    <Card title={messages.dashboard.dataCoverage} className="panel-card coverage-panel" variant="borderless">
      <div className="coverage-toolbar">
        <Segmented
          options={["1m", "5m", "15m", "1h", "1d"]}
          value={interval}
          onChange={(value) => onIntervalChange?.(String(value))}
        />
        <Tag icon={<CalendarOutlined />} className="coverage-range">
          {coverageRange ?? messages.dashboard.coverageRange}
        </Tag>
      </div>
      <div className="coverage-scroll-area">
        <Space direction="vertical" size={20} className="full-width coverage-scroll-content">
          {rows.map((row) => (
            <div className="coverage-row" key={`${row.symbol}-${row.interval}`}>
              <div className="coverage-meta">
                <div>
                  <Typography.Text className="coverage-symbol">{row.symbol}</Typography.Text>
                  <Typography.Text className={`coverage-percent coverage-percent-${row.health}`}>
                    {row.coveragePercent.toFixed(1)}%
                  </Typography.Text>
                </div>
                <Tag color={row.health === "healthy" ? "green" : row.health === "error" ? "red" : "gold"}>
                  {row.health === "healthy" ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                  <span className="tag-text">
                    {formatMissingRangesLabel(row.missingRanges, messages)}
                  </span>
                </Tag>
              </div>
              <div className="coverage-timeline" aria-label={`${row.symbol} ${row.coveragePercent}%`}>
                {row.segments.map((segment, index) => (
                  <span
                    className={`coverage-segment coverage-segment-${segment.status}`}
                    key={`${row.symbol}-${segment.status}-${index}`}
                    style={{ flexGrow: segment.width }}
                  />
                ))}
              </div>
              <div className="coverage-dates">
                {(row.dateLabels ?? defaultCoverageDateLabels).map((label, index) => (
                  <span key={`${row.symbol}-${row.interval}-${index}`}>{label}</span>
                ))}
              </div>
            </div>
          ))}
        </Space>
        <div className="coverage-legend">
          <span>
            <i className="legend-box legend-available" />
            {messages.common.available}
          </span>
          <span>
            <i className="legend-box legend-missing" />
            {messages.common.missing}
          </span>
          <span>
            <i className="legend-box legend-empty" />
            {messages.common.noData}
          </span>
          <InfoCircleOutlined className="coverage-info" />
        </div>
      </div>
    </Card>
  );
}

function formatMissingRangesLabel(
  missingRanges: CoverageRow["missingRanges"],
  messages: AppMessages
) {
  if (missingRanges === null) {
    return messages.common.warning;
  }
  if (missingRanges === 0) {
    return messages.common.complete;
  }
  return `${missingRanges} ${messages.common.gaps}`;
}
