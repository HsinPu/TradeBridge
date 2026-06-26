import type { CandleRow } from "../types";

type CandlestickChartProps = {
  candles: CandleRow[];
  loading?: boolean;
  emptyText?: string;
};

function formatPrice(value: number | null, fractionDigits = 2) {
  if (value === null || !Number.isFinite(value)) {
    return "--";
  }

  return value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits
  });
}

function formatVolume(value: number | null) {
  if (value === null || !Number.isFinite(value)) {
    return "--";
  }

  return value.toLocaleString(undefined, {
    maximumFractionDigits: 3
  });
}

function formatAxisTime(value: string) {
  const [, time = value] = value.split(" ");
  return time.slice(0, 5);
}

function getAxisLabels(candles: CandleRow[]) {
  if (candles.length === 0) {
    return Array.from({ length: 9 }, () => "--");
  }

  const labelCount = Math.min(9, candles.length);
  if (labelCount === 1) {
    return [formatAxisTime(candles[0].time)];
  }

  return Array.from({ length: labelCount }, (_, index) => {
    const candleIndex = Math.round((index * (candles.length - 1)) / (labelCount - 1));
    return formatAxisTime(candles[candleIndex].time);
  });
}

export function CandlestickChart({ candles, loading = false, emptyText = "No chart data" }: CandlestickChartProps) {
  const latestCandle = candles.at(-1) ?? null;
  const chartColumnCount = Math.max(candles.length, 1);
  const minLow = candles.length > 0 ? Math.min(...candles.map((candle) => candle.low)) : 0;
  const maxHigh = candles.length > 0 ? Math.max(...candles.map((candle) => candle.high)) : 1;
  const priceRange = Math.max(maxHigh - minLow, 1);
  const paddedMin = minLow - priceRange * 0.08;
  const paddedMax = maxHigh + priceRange * 0.08;
  const paddedRange = Math.max(paddedMax - paddedMin, 1);
  const maxVolume = candles.length > 0 ? Math.max(...candles.map((candle) => candle.volume)) : 1;
  const axisPrices = Array.from(
    { length: 6 },
    (_, index) => paddedMax - (index * paddedRange) / 5
  );

  const priceToTop = (price: number) => ((paddedMax - price) / paddedRange) * 100;

  return (
    <div className="chart-shell" aria-busy={loading} aria-label="Candlestick chart preview">
      {loading ? (
        <div className="chart-state chart-state-loading">Loading chart...</div>
      ) : null}
      {!loading && candles.length === 0 ? <div className="chart-state">{emptyText}</div> : null}
      <div className="chart-price-line">
        <span>{formatPrice(latestCandle?.close ?? null)}</span>
      </div>
      <div
        className="chart-grid"
        style={{ gridTemplateColumns: `repeat(${chartColumnCount}, minmax(0, 1fr))` }}
      >
        {candles.map((candle) => {
          const isPositive = candle.close >= candle.open;
          const high = priceToTop(candle.high);
          const low = priceToTop(candle.low);
          const bodyTop = priceToTop(Math.max(candle.open, candle.close));
          const bodyBottom = priceToTop(Math.min(candle.open, candle.close));
          const volumeHeight = Math.max((candle.volume / Math.max(maxVolume, 1)) * 100, 3);

          return (
            <div
              className="candle-column"
              key={candle.key}
              title={`${candle.time} O ${formatPrice(candle.open)} H ${formatPrice(candle.high)} L ${formatPrice(
                candle.low
              )} C ${formatPrice(candle.close)} Volume ${formatVolume(candle.volume)}`}
            >
              <div
                className={`candle-wick ${isPositive ? "up" : "down"}`}
                style={{ top: `${high}%`, height: `${Math.max(low - high, 2)}%` }}
              />
              <div
                className={`candle-body ${isPositive ? "up" : "down"}`}
                style={{
                  top: `${bodyTop}%`,
                  height: `${Math.max(bodyBottom - bodyTop, 4)}%`
                }}
              />
              <div className="volume-track">
                <div
                  className={`volume-bar ${isPositive ? "up" : "down"}`}
                  style={{ height: `${volumeHeight}%` }}
                />
              </div>
            </div>
          );
        })}
        <div className="chart-y-axis" aria-hidden="true">
          {axisPrices.map((price) => (
            <span key={price}>{formatPrice(price)}</span>
          ))}
        </div>
        <span className="chart-volume-label">Volume {formatVolume(latestCandle?.volume ?? null)}</span>
      </div>
      <div className="chart-axis">
        {getAxisLabels(candles).map((label, index) => (
          <span key={`${label}-${index}`}>{label}</span>
        ))}
      </div>
    </div>
  );
}
