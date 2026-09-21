import { Alert, Button, Card, Checkbox, Input, Space, Table, Tag, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";
import type { Language } from "../../shared/i18n/messages";
import { collectionApi, dateText, errorText } from "./api";
import type { CatalogMarket, CatalogRun, Page } from "./api";

export function CatalogPanel({ language }: { language: Language }) {
  const zh = language === "zh-TW";
  const [page, setPage] = useState<Page<CatalogMarket>>({ items: [], next_cursor: null });
  const [run, setRun] = useState<CatalogRun | null>(null);
  const [search, setSearch] = useState("");
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const cursor = cursors[cursors.length - 1];
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [allowChange, setAllowChange] = useState(false);
  const pending = run?.status === "pending" || run?.status === "running";
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [next, nextRun] = await Promise.all([collectionApi.catalog(search, cursor, signal), collectionApi.catalogRun(signal)]);
      if (!signal?.aborted) { setPage(next); setRun(nextRun); setError(null); }
    } catch (e) { if (!signal?.aborted) setError(errorText(e)); }
  }, [search, cursor]);
  useEffect(() => { const c = new AbortController(); void load(c.signal); const id = window.setInterval(() => void load(c.signal), 6000); return () => { c.abort(); window.clearInterval(id); }; }, [load]);
  async function sync() {
    setBusy(true);
    try { setRun(await collectionApi.sync(allowChange)); setAllowChange(false); setError(null); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  return <Card title={zh ? "交易所市場目錄" : "Exchange market catalog"} className="panel-card" variant="borderless">
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text>{zh ? "完整同步所有報價幣種與交易狀態。同步目錄只更新市場清單；啟動行情下載請到「任務」。下架或暫停不會刪除既有 K 線，手動停用也不會被覆寫。" : "Synchronizes all quote assets and trading states. Catalog sync updates the market list only; start downloads in Jobs. Delisting preserves candles and manual disabling is respected."}</Typography.Text>
      {error && <Alert type="error" showIcon message={error} action={<Button onClick={() => void load()}>{zh ? "重試" : "Retry"}</Button>} />}
      <Space wrap><Button type="primary" loading={busy || pending} onClick={() => void sync()}>{zh ? "同步全部市場" : "Sync all markets"}</Button><Tag>{run?.status ?? (zh ? "尚未同步" : "Not synced")}</Tag><Typography.Text>{zh ? "目錄總數：" : "Catalog total: "}{page.total ?? "—"} · {dateText(run?.finished_at_ms ?? null)}</Typography.Text></Space>
      {run?.status === "failed" && <Alert type="warning" message={zh ? "同步未發布" : "Sync not published"} description={run.error_message} />}
      {run?.status === "failed" && run.error_message?.includes("20%") && <Checkbox checked={allowChange} onChange={e => setAllowChange(e.target.checked)}>{zh ? "我已核對交易所狀態，允許此次市場數量減少超過 20%。" : "I have checked the exchange status and accept a decrease of more than 20% for this sync."}</Checkbox>}
      <Input.Search aria-label={zh ? "搜尋市場目錄" : "Search market catalog"} placeholder={zh ? "搜尋交易對或報價幣種" : "Search pair or quote asset"} allowClear onSearch={value => { setSearch(value.trim()); setCursors([null]); }} />
      <Table<CatalogMarket> rowKey="exchange_symbol" size="small" dataSource={page.items} pagination={false} scroll={{ x: 650 }} locale={{ emptyText: zh ? "尚無目錄或沒有符合的市場" : "No catalog or matching markets" }} columns={[
        { title: zh ? "交易對" : "Pair", dataIndex: "market_pair" },
        { title: zh ? "交易所狀態" : "Exchange state", dataIndex: "exchange_status" },
        { title: zh ? "目錄觀察" : "Observation", dataIndex: "observation" },
        { title: zh ? "現貨資格" : "Spot allowed", render: (_, r) => r.spot_allowed ? (zh ? "是" : "Yes") : (zh ? "否" : "No") },
        { title: zh ? "使用者設定" : "User preference", render: (_, r) => r.enabled === null ? "—" : r.enabled ? (zh ? "啟用" : "Enabled") : (zh ? "手動停用" : "Disabled") }
      ]} />
      <Space><Button disabled={cursors.length < 2} onClick={() => setCursors(c => c.slice(0, -1))}>{zh ? "上一頁" : "Previous"}</Button><Button disabled={!page.next_cursor} onClick={() => setCursors(c => [...c, page.next_cursor])}>{zh ? "下一頁" : "Next"}</Button></Space>
    </Space>
  </Card>;
}
