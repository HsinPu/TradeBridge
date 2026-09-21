import { Alert, Button, Card, Checkbox, DatePicker, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd";
import type { Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiJobRequest, apiRequest, buildQueryString } from "../../shared/api/client";
import { createCandleFetchJob } from "../market-data/api";
import { CandlestickChart } from "../market-data/components/CandlestickChart";
import { collectionApi, dateText, errorText } from "./api";

type SeriesCandle = { open_time_ms: number; open_time: string; open_price: string; high_price: string; low_price: string; close_price: string; base_volume: string; quote_volume: string; trade_count: number; complete: boolean; closed: boolean; observed_minutes: number; expected_minutes: number };
type SeriesPage = { candles: SeriesCandle[]; next_cursor: string | null; window_start_ms: number; window_end_ms: number; as_of_ms: number; quality: { missing_minutes: number; expected_closed_minutes: number; observed_minutes: number; gaps: { start_ms: number; end_ms: number; missing_minutes: number }[] } };
const intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"];

export function MinuteDataPage({ english }: { english: boolean }) {
  const text = (zh: string, en: string) => english ? en : zh;
  const [pair, setPair] = useState("BTC/USDT");
  const [interval, setInterval] = useState("1m");
  const [search, setSearch] = useState("");
  const [options, setOptions] = useState<{ label: string; value: string }[]>([]);
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [completeOnly, setCompleteOnly] = useState(true);
  const [includeOpen, setIncludeOpen] = useState(false);
  const [page, setPage] = useState<SeriesPage | null>(null);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const cursor = cursors[cursors.length - 1];
  const [error, setError] = useState<string | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reimportOpen, setReimportOpen] = useState(false);
  const request = useRef<AbortController | null>(null);
  const start = range?.[0]?.valueOf();
  const end = range?.[1]?.valueOf();
  useEffect(() => {
    const controller = new AbortController();
    const id = window.setTimeout(() => {
      void collectionApi.catalog(search, null, controller.signal).then(result => {
        if (!controller.signal.aborted) { setOptions(result.items.map(m => ({ label: m.market_pair, value: m.market_pair }))); setCatalogError(null); }
      }).catch(e => { if (!controller.signal.aborted) setCatalogError(errorText(e)); });
    }, 250);
    return () => { controller.abort(); window.clearTimeout(id); };
  }, [search]);
  const load = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setLoading(true);
    try {
      const result = await apiRequest<SeriesPage>(`/api/v1/candle-series${buildQueryString({ market_pair: pair, interval, start_ms: start, end_ms: end, limit: 1000, cursor, complete_only: completeOnly, include_open: includeOpen })}`, { signal: controller.signal });
      if (!controller.signal.aborted) { setPage(result); setError(null); }
    } catch (e) { if (!controller.signal.aborted) setError(errorText(e)); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }, [pair, interval, start, end, cursor, completeOnly, includeOpen]);
  useEffect(() => { void load(); return () => request.current?.abort(); }, [load]);
  function resetPage() { setPage(null); setCursors([null]); setJobId(null); }
  async function fillWindow() {
    if (!page || page.window_end_ms <= page.window_start_ms) return;
    setSubmitting(true);
    try {
      const job = await createCandleFetchJob({ provider: "binance", market_type: "spot", market_pair: pair,
        interval: "1m", mode: "fill_gaps", start_time: new Date(page.window_start_ms).toISOString(),
        end_time: new Date(Math.min(page.window_end_ms, Math.floor((page.as_of_ms - 2000) / 60000) * 60000) - 1).toISOString(),
        closed_only: true, batch_limit: 1000, overlap_candles: 0, verify_continuity: true,
        retry_attempts: 3, retry_delay_seconds: 1 });
      setJobId(job.id); setError(null);
    } catch (e) { setError(errorText(e)); }
    finally { setSubmitting(false); }
  }
  async function reimportWindow() {
    if (!page) return;
    setSubmitting(true);
    try {
      const job = await apiJobRequest<{ id: string }>("/api/v1/candle-series/reimport", { market_pair: pair, start_ms: page.window_start_ms, end_ms: Math.min(page.window_end_ms, Math.floor((page.as_of_ms - 2000) / 60000) * 60000) });
      setJobId(job.id); setError(null); setReimportOpen(false);
    } catch (e) { setError(errorText(e)); }
    finally { setSubmitting(false); }
  }
  const chart = useMemo(() => (page?.candles ?? []).slice(-80).map(c => ({ key: String(c.open_time_ms), time: dateText(c.open_time_ms), open: Number(c.open_price), high: Number(c.high_price), low: Number(c.low_price), close: Number(c.close_price), volume: Number(c.base_volume), trades: c.trade_count, source: "1m" })), [page]);
  return <main className="page-stack">
    <div className="page-header"><div><Typography.Title level={2}>{text("市場資料", "Market Data")}</Typography.Title><Typography.Text className="page-subtitle">{text("所有週期由已儲存的 1 分鐘 K 線組成；以 UTC 對齊，月線依日曆月計算。", "Every interval is derived from stored 1-minute candles, aligned to UTC with calendar months.")}</Typography.Text></div></div>
    <Card className="toolbar-card" variant="borderless">
      <Form layout="vertical"><Space wrap align="start" size="middle">
        <Form.Item label={text("交易對（可搜尋全部目錄）", "Pair (search complete catalog)")}><Select aria-label={text("彙整交易對", "Series pair")} showSearch filterOption={false} value={pair} onSearch={setSearch} options={options.some(o => o.value === pair) ? options : [{ label: pair, value: pair }, ...options]} onChange={value => { setPair(value); resetPage(); }} style={{ minWidth: 210 }} /></Form.Item>
        <Form.Item label={text("週期", "Interval")}><Select aria-label={text("彙整週期", "Series interval")} value={interval} options={intervals.map(value => ({ value, label: value }))} onChange={value => { setInterval(value); resetPage(); }} style={{ width: 110 }} /></Form.Item>
        <Form.Item label={text("時間範圍（本機時區，結束時間不含）", "Range (local time, end exclusive)")}><DatePicker.RangePicker showTime value={range} onChange={value => { setRange(value); resetPage(); }} /></Form.Item>
        <Form.Item label={text("查詢", "Query")}><Button loading={loading} onClick={() => void load()}>{text("重新查詢", "Refresh")}</Button></Form.Item>
      </Space><Space wrap><Checkbox checked={completeOnly} onChange={e => { setCompleteOnly(e.target.checked); resetPage(); }}>{text("只顯示完整資料", "Complete candles only")}</Checkbox><Checkbox checked={includeOpen} onChange={e => { setIncludeOpen(e.target.checked); resetPage(); }}>{text("包含尚未收盤的週期", "Include open buckets")}</Checkbox></Space></Form>
      {catalogError && <Typography.Paragraph type="warning">{text("目錄讀取失敗：", "Catalog unavailable: ")}{catalogError}</Typography.Paragraph>}
    </Card>
    {error && <Alert type="error" showIcon message={text("查詢失敗", "Query failed")} description={error} />}
    {jobId && <Alert type="info" showIcon message={text("補齊任務已建立，可到「任務」查看進度，完成後重新查詢。", "Fill job queued. Track it in Jobs and refresh after completion.")} description={jobId} />}
    {page && <Card className="panel-card" variant="borderless"><Space direction="vertical" style={{ width: "100%" }}>
      <Space wrap><Tag color="blue">1m → {interval}</Tag><Typography.Text>{dateText(page.window_start_ms)} — {dateText(page.window_end_ms)}</Typography.Text><Typography.Text>{text("本頁已收盤分鐘：", "Closed source minutes: ")}{page.quality.observed_minutes} / {page.quality.expected_closed_minutes} · {text("缺少：", "Missing: ")}{page.quality.missing_minutes}</Typography.Text></Space>
      <Typography.Text type="secondary">{text("每頁最多掃描 31 天分鐘資料。大範圍請使用下一頁；空白時段不會生成假的 K 線。查詢預設顯示最近可取得資料。", "Each page scans at most 31 days of minute data. Use Next for wider ranges; empty periods never produce fabricated candles. Without a range, queries show the latest stored data.")}</Typography.Text>
      <Button disabled={loading || page.window_end_ms <= page.window_start_ms || !page.quality.missing_minutes} loading={submitting} onClick={() => void fillWindow()}>{text("補齊本頁的 1 分鐘資料", "Fill this page's missing 1-minute data")}</Button>
      <Button disabled={loading || !page.candles.length} onClick={() => setReimportOpen(true)}>{text("重新匯入本頁來源", "Reimport this source window")}</Button>
    </Space></Card>}
    <Card className="panel-card" variant="borderless"><CandlestickChart candles={chart} loading={loading && !page} emptyText={text("此範圍沒有符合品質條件的分鐘彙整資料。", "No minute-derived candles matching these quality filters.")} /></Card>
    <Card className="panel-card" variant="borderless" title={text("彙整結果", "Derived candles")}>
      <Table<SeriesCandle> rowKey="open_time_ms" dataSource={page?.candles ?? []} loading={loading && !page} scroll={{ x: 950 }} pagination={{ pageSize: 20 }} columns={[
        { title: text("開盤時間", "Open time"), render: (_, c) => dateText(c.open_time_ms) },
        ...(["open_price", "high_price", "low_price", "close_price", "base_volume"] as const).map((key, i) => ({ title: [text("開", "Open"), text("高", "High"), text("低", "Low"), text("收", "Close"), text("成交量", "Volume")][i], dataIndex: key })),
        { title: text("品質", "Quality"), render: (_, c) => <Space><Tag color={c.complete ? "success" : "warning"}>{c.observed_minutes}/{c.expected_minutes}</Tag><Tag>{c.closed ? text("已收盤", "Closed") : text("未收盤", "Open")}</Tag></Space> }
      ]} />
      <Space wrap><Button disabled={loading || cursors.length < 2} onClick={() => setCursors(c => c.slice(0, -1))}>{text("上一頁資料", "Previous data page")}</Button><Button disabled={loading || !page?.next_cursor} onClick={() => setCursors(c => [...c, page?.next_cursor ?? null])}>{text("下一頁資料", "Next data page")}</Button><Typography.Text type="secondary">{text("表格價格保留原始精度；圖表僅作視覺預覽。", "Table prices retain exact decimal precision; the chart is a visual preview.")}</Typography.Text></Space>
    </Card>
    <Modal title={text("重新匯入 1 分鐘來源", "Reimport 1-minute source")} open={reimportOpen} onCancel={() => setReimportOpen(false)} onOk={() => void reimportWindow()} confirmLoading={submitting} okText={text("建立重新匯入任務", "Queue reimport")} cancelText={text("取消", "Cancel")}>
      <Typography.Paragraph>{text("重新核對官方歷史檔與 SHA256，歷史檔不存在時使用 REST。僅更新本頁範圍；數值變更保留前後原始資料及來源紀錄，其他週期會隨來源更新。", "Rechecks official archives and SHA256, using REST when unavailable. Updates this page's window; changed values retain both original payloads and source records. Derived intervals update with the source.")}</Typography.Paragraph>
      {error && <Alert type="error" message={error} />}
    </Modal>
  </main>;
}
