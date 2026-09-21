import { Alert, Button, Card, Checkbox, Collapse, Form, Input, InputNumber, Modal, Space, Statistic, Table, Tag, Typography } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Language } from "../../shared/i18n/messages";
import { collectionApi, dateText, errorText } from "./api";
import type { CatalogRun, CollectionMarket, CollectionPreview, CollectionStatus, Page } from "./api";

export function CollectionPanel({ language, compact = false }: { language: Language; compact?: boolean }) {
  const zh = language === "zh-TW";
  const text = (a: string, b: string) => zh ? a : b;
  const [status, setStatus] = useState<CollectionStatus | null>(null);
  const [catalog, setCatalog] = useState<CatalogRun | null>(null);
  const [page, setPage] = useState<Page<CollectionMarket>>({ items: [], next_cursor: null });
  const [search, setSearch] = useState("");
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const cursor = cursors[cursors.length - 1];
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<CollectionPreview | null>(null);
  const [pauseSchedules, setPauseSchedules] = useState(false);
  const [form] = Form.useForm<{ refresh_minutes: number; catalog_hours: number; queue_limit: number; free_gib: number }>();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const loading = useRef(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    if (loading.current) return;
    loading.current = true;
    try {
      const [next, run, markets] = await Promise.all([collectionApi.status(signal), collectionApi.catalogRun(signal), compact ? Promise.resolve(null) : collectionApi.markets(search, cursor, signal)]);
      if (signal?.aborted) return;
      setStatus(next); setCatalog(run); if (markets) setPage(markets); setError(null);
    } catch (e) { if (!signal?.aborted) setError(errorText(e)); }
    finally { loading.current = false; }
  }, [compact, cursor, search]);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    const id = window.setInterval(() => void load(controller.signal), 4000);
    return () => { controller.abort(); window.clearInterval(id); };
  }, [load]);
  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setNotice(null);
    try { setError(null); await fn(); await load(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  const policy = status?.policy;
  const runPending = catalog?.status === "pending" || catalog?.status === "running";
  const state = !policy ? text("讀取中", "Loading") : !policy.enabled ? text("未啟用／已暫停", "Disabled / paused") : policy.blocked_reason === "catalog_stale" ? text("等待更新市場目錄與校時", "Waiting for fresh catalog and clock") : policy.blocked_reason ? text("空間不足，已暫停派工", "Storage low; collection blocked") : policy.history_paused ? text("只更新最新資料", "Recent data only") : text("自動收集中", "Collecting automatically");
  return <Card title={text("全市場自動收集", "All-market collection")} className="panel-card" variant="borderless" extra={<Tag color={policy?.enabled && !policy.blocked_reason ? "processing" : "default"}>{state}</Tag>}>
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Paragraph style={{ margin: 0 }}>{text("自動追蹤 Binance 所有可交易現貨與後續新增市場，只儲存 1 分鐘 K 線；先補近期資料，再從各市場最早可取得的時間分段回補。", "Tracks all tradable Binance spot pairs and new listings. Stores 1-minute candles, fills recent data first, then backfills each market from its earliest available history.")}</Typography.Paragraph>
      {error && <Alert type="error" showIcon message={text("更新失敗，以下可能是上次資料", "Update failed; displayed data may be stale")} description={error} action={<Button onClick={() => void load()}>{text("重試", "Retry")}</Button>} />}
      {notice && <Alert type="info" showIcon message={notice} />}
      <Space wrap size="large">
        <Statistic title={text("目錄／目前可交易", "Catalog / tradable")} value={status?.catalog.total ?? "—"} suffix={status ? `/ ${status.catalog.tradable}` : undefined} />
        <Statistic title={text("納入市場", "Enrolled markets")} value={status?.markets.total_markets ?? "—"} />
        <Statistic title={text("歷史已掃描", "History scanned")} value={status?.markets.history_scanned ?? "—"} suffix={status ? `/ ${status.markets.total_markets}` : undefined} />
        <Statistic title={text("待處理區段", "Pending segments")} value={status?.segments.pending ?? (status ? 0 : "—")} />
        <Statistic title={text("需檢查區段", "Segments needing attention")} value={status ? (status.segments.failed ?? 0) + (status.segments.cancelled ?? 0) + (status.segments.incomplete ?? 0) : "—"} />
      </Space>
      <Typography.Text type="secondary">{text("歷史已掃描不等於資料完整。已知缺失分鐘：", "Scanned history is not a completeness guarantee. Known missing minutes: ")}{status?.missing_minutes ?? "—"} · {text("最新協調時間：", "Last coordinator cycle: ")}{dateText(policy?.last_cycle_ms ?? null)}</Typography.Text>
      <Typography.Text type="secondary">{text("最慢市場的近期掃描時間：", "Oldest recent scan: ")}{dateText(status?.markets.oldest_tail_next_ms ?? null)} · {text("近期連續完整時間：", "Recent continuous watermark: ")}{dateText(status?.markets.oldest_tail_complete_until_ms ?? null)}</Typography.Text>
      {!!status?.segments.held && <Typography.Text>{text("暫存等待區段：", "Held segments: ")}{status.segments.held} · {text("市場恢復或解除政策暫停後才會重新排入；使用者暫停的任務仍須手動恢復。", "Requeued when markets and policy allow. User-paused jobs still need a manual resume.")}</Typography.Text>}
      {compact ? <Typography.Text>{text("到「任務」管理啟停、到「設定」查看完整市場目錄。", "Manage collection in Jobs and browse the complete market catalog in Settings.")}</Typography.Text> : <>
        <Space wrap>
          <Button disabled={busy || runPending} loading={runPending} onClick={() => void action(() => collectionApi.sync())}>{text("同步全部市場目錄", "Sync full market catalog")}</Button>
          {policy?.enabled ? <Button disabled={busy} onClick={() => void action(() => collectionApi.control("all", true))}>{text("暫停全部收集", "Pause all collection")}</Button> : <Button type="primary" disabled={busy || !policy} onClick={() => void action(async () => { setPauseSchedules(false); setPreview(await collectionApi.preview()); })}>{text("預覽並啟動", "Preview and start")}</Button>}
          <Button disabled={busy || !policy?.enabled} onClick={() => void action(() => collectionApi.control("history", !policy?.history_paused))}>{policy?.history_paused ? text("恢復歷史回補", "Resume history") : text("只暫停歷史回補", "Pause history only")}</Button>
          <Button disabled={busy || !policy} onClick={() => { if (policy) form.setFieldsValue({ ...policy, free_gib: policy.min_free_bytes / 1024 ** 3 }); setSettingsOpen(true); }}>{text("收集設定", "Collection settings")}</Button>
          <Button disabled={busy || !policy?.enabled} onClick={() => void action(async () => { const r = await collectionApi.retry(); setNotice(text(`已排入 ${r.job_ids.length} 個重試任務`, `Queued ${r.job_ids.length} retries`)); })}>{text("重試問題區段", "Retry problem segments")}</Button>
        </Space>
        {catalog?.status === "failed" && <Alert type="warning" showIcon message={text("市場目錄同步失敗", "Market catalog sync failed")} description={catalog.error_message} />}
        <Typography.Text type="secondary">{text("市場目錄：", "Catalog: ")}{catalog ? `${catalog.status} · ${catalog.symbol_count ?? "—"}` : text("尚未同步", "Not synced")} · {text("更新目標：每", "Refresh target: every ")}{policy?.refresh_minutes ?? "—"}{text(" 分鐘（實際延遲取決於佇列）", " minutes (actual lag depends on queue)")}</Typography.Text>
        <Collapse items={[{ key: "markets", label: text("逐市場進度與排除設定", "Per-market progress and exclusions"), children: <Space direction="vertical" style={{ width: "100%" }}>
          <Input.Search aria-label={text("搜尋收集市場", "Search collection markets")} placeholder="BTC/USDT" allowClear onSearch={value => { setSearch(value.trim()); setCursors([null]); }} />
          <Table<CollectionMarket> size="small" dataSource={page.items} rowKey="exchange_symbol" pagination={false} scroll={{ x: 950 }} locale={{ emptyText: text("尚無收集市場，請先同步目錄並啟動收集。", "No enrolled markets. Sync the catalog and start collection.") }} columns={[
            { title: text("市場", "Market"), dataIndex: "market_pair" },
            { title: text("狀態", "State"), render: (_, r) => r.excluded ? text("已排除", "Excluded") : !r.enabled ? text("手動停用", "Manually disabled") : `${r.exchange_status ?? "—"} / ${r.observation ?? "—"}` },
            { title: text("源頭", "Earliest"), render: (_, r) => dateText(r.first_open_time_ms) },
            { title: text("歷史游標", "History cursor"), render: (_, r) => dateText(r.history_next_ms) },
            { title: text("近期掃描游標", "Recent scan cursor"), render: (_, r) => dateText(r.tail_next_ms) },
            { title: text("近期連續完整至", "Recent continuous through"), render: (_, r) => dateText(r.tail_complete_until_ms) },
            { title: text("問題區段", "Problems"), dataIndex: "problem_segments" },
            { title: text("操作", "Actions"), render: (_, r) => <Space><Button size="small" disabled={busy} onClick={() => void action(() => collectionApi.exclude(r.exchange_symbol, !r.excluded))}>{r.excluded ? text("重新納入", "Include") : text("排除", "Exclude")}</Button><Button size="small" disabled={busy || !r.problem_segments || !policy?.enabled} onClick={() => void action(() => collectionApi.retry(r.exchange_symbol))}>{text("重試", "Retry")}</Button></Space> }
          ]} expandable={{ expandedRowRender: r => <Typography.Text>{r.last_error ?? text("沒有記錄錯誤", "No recorded error")}</Typography.Text> }} />
          <Space><Button disabled={cursors.length === 1} onClick={() => setCursors(c => c.slice(0, -1))}>{text("上一頁", "Previous")}</Button><Button disabled={!page.next_cursor} onClick={() => setCursors(c => [...c, page.next_cursor])}>{text("下一頁", "Next")}</Button></Space>
        </Space> }]} />
      </>}
    </Space>
    <Modal title={text("啟動全市場收集", "Start all-market collection")} open={preview !== null} onCancel={() => setPreview(null)} confirmLoading={busy} okText={text("確認啟動", "Start collection")} cancelText={text("取消", "Cancel")}
      okButtonProps={{ disabled: !preview?.catalog_sync || !preview?.eligible_markets || !preview?.scheduler_enabled || preview.free_bytes < preview.policy.min_free_bytes || (preview.conflicting_schedules.length > 0 && !pauseSchedules) }}
      onOk={() => void action(async () => { if (!preview) return; await collectionApi.start(preview.policy.revision, pauseSchedules ? preview.conflicting_schedules.map(s => s.id) : []); setPreview(null); })}>
      {error && <Alert type="error" message={error} />}
      {preview && <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        <Typography.Paragraph>{text(`共 ${preview.eligible_markets} 個目前可交易市場，僅抓取 1m；每個市場從最早可取得的歷史補起。`, `${preview.eligible_markets} tradable markets, 1m only, backfilled from earliest available history.`)}</Typography.Paragraph>
        <Typography.Text>{text("可用空間：", "Free storage: ")}{(preview.free_bytes / 1024 ** 3).toFixed(1)} GiB · {text("保留：", "Reserve: ")}{(preview.policy.min_free_bytes / 1024 ** 3).toFixed(1)} GiB</Typography.Text>
        <Alert type="info" showIcon message={text("全量歷史可能需要大量空間與時間", "Full history can require substantial storage and time")} description={text("10 萬筆合成資料測量約 68 MB，真實資料與來源憑證可能更大。空間降到保留值時會停止派工，不會自動刪除歷史。", "A 100,000-row synthetic sample used about 68 MB; real data and provenance may use more. Collection stops at the storage reserve without deleting history.")} />
        {!preview.catalog_sync && <Alert type="warning" message={text("請先同步市場目錄。", "Sync the catalog first.")} />}
        {!preview.scheduler_enabled && <Alert type="warning" message={text("背景排程未啟用。", "Background scheduler is disabled.")} />}
        {!!preview.conflicting_schedules.length && <><Typography.Paragraph>{preview.conflicting_schedules.map(s => `${s.name} (${s.market_pair} ${s.interval})`).join("、")}</Typography.Paragraph><Checkbox checked={pauseSchedules} onChange={e => setPauseSchedules(e.target.checked)}>{text(`同時暫停以上 ${preview.conflicting_schedules.length} 個排程，保留設定與任務紀錄。`, `Pause these ${preview.conflicting_schedules.length} schedules, retaining settings and job history.`)}</Checkbox></>}
      </Space>}
    </Modal>
    <Modal title={text("收集設定", "Collection settings")} open={settingsOpen} onCancel={() => setSettingsOpen(false)} confirmLoading={busy} okText={text("儲存", "Save")} cancelText={text("取消", "Cancel")} onOk={() => void action(async () => { const values = await form.validateFields(); if (!policy) return; const { free_gib, ...rest } = values; await collectionApi.configure(policy.revision, { ...rest, min_free_bytes: Math.round(free_gib * 1024 ** 3) }); setSettingsOpen(false); })}>
      {error && <Alert type="error" message={error} />}
      <Form form={form} layout="vertical">
        <Form.Item name="refresh_minutes" label={text("最新資料更新目標（分鐘）", "Recent refresh target (minutes)")} rules={[{ required: true }]}><InputNumber min={1} max={1440} /></Form.Item>
        <Form.Item name="catalog_hours" label={text("市場目錄更新間隔（小時）", "Catalog refresh interval (hours)")} rules={[{ required: true }]}><InputNumber min={1} max={168} /></Form.Item>
        <Form.Item name="queue_limit" label={text("待處理區段上限", "Maximum pending segments")} rules={[{ required: true }]}><InputNumber min={2} max={500} /></Form.Item>
        <Form.Item name="free_gib" label={text("磁碟保留空間（GiB）", "Free storage reserve (GiB)")} rules={[{ required: true }]}><InputNumber min={1} max={10240} /></Form.Item>
      </Form>
    </Modal>
  </Card>;
}
