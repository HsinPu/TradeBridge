import { ArrowDownOutlined, ArrowUpOutlined, LineChartOutlined } from "@ant-design/icons";
import { Card, Typography } from "antd";

import type { PriceSnapshot } from "../types";

type SummaryCardProps = {
  snapshot: PriceSnapshot;
};

const toneIcon = {
  neutral: <LineChartOutlined />,
  success: <ArrowUpOutlined />,
  warning: <LineChartOutlined />,
  danger: <ArrowDownOutlined />
};

function Sparkline({ values, tone }: { values: number[]; tone: PriceSnapshot["tone"] }) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * 96;
      const y = 34 - ((value - min) / range) * 28;

      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className={`summary-sparkline summary-sparkline-${tone}`} viewBox="0 0 96 38" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points={`0,38 ${points} 96,38`} className="summary-sparkline-fill" />
    </svg>
  );
}

export function SummaryCard({ snapshot }: SummaryCardProps) {
  return (
    <Card className={`summary-card summary-card-${snapshot.tone}`} variant="borderless">
      <div className="summary-card-content">
        <div className="summary-card-heading">
          <Typography.Text className="muted-label">{snapshot.label}</Typography.Text>
          <span className="summary-card-icon">{toneIcon[snapshot.tone]}</span>
        </div>
        <div className="summary-card-main">
          <div className="summary-card-text">
            <Typography.Title level={3} className="summary-card-value">
              {snapshot.value}
            </Typography.Title>
            <Typography.Text className={`summary-card-trend summary-card-trend-${snapshot.tone}`}>
              {snapshot.trend}
            </Typography.Text>
            <Typography.Text className="summary-card-detail">{snapshot.detail}</Typography.Text>
          </div>
          <Sparkline values={snapshot.sparkline} tone={snapshot.tone} />
        </div>
      </div>
    </Card>
  );
}
