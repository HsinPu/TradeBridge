# 全市場分鐘資料實作與驗證

目標建立：2026-09-21。基準：1.1.1 / `ab34599`。產品交付：1.2.0；資料庫 schema：2。原始方向見 [規劃](all-market-minute-data.md)。

使用者已授權依規劃實作；本次沒有啟動正式全市場下載，也沒有 push 或建立 Git tag。

## 已交付範圍

- 完整 Binance 現貨目錄：所有報價幣種、交易狀態及現貨資格；伺服器搜尋及游標分頁。交易所狀態、快照缺席與使用者 enabled 分開儲存。
- 目錄同步先建立持久化請求再回傳 202，有租約、心跳、execution token。一次缺席標記未確認，連續兩次才標記 missing；縮減超過 20% 必須明示接受。同步失敗保留上次完整目錄。
- 預設關閉的收集政策。啟用前確認目錄、可用空間及重疊的舊排程；暫停舊排程保留原設定，不因關閉政策而自動恢復。
- 逐市場探測最早可取得的已收盤 1m；先補近期 24 小時，再以固定歷史終點從最早資料回補。近期與歷史分開游標；每段最多 10,000 分鐘，待處理預設上限 100。
- 預設每 15 分鐘追近期、每 6 小時更新目錄；這是派工目標，不是全市場時效保證。每個協調回合最多探索 2 個市場、規劃 32 個市場，市場輪替避免前排獨占。
- 既有 JobRunner 公平輪流人工／近期／人工／歷史，最多兩個不同市場；同市場互斥。沿用租約、心跳、寫入 token、批次交易及可恢復游標。
- 歷史暫停、全部暫停、逐市場排除、區段重試。政策或市場暫停的工作轉 held，不占活躍佇列；使用者暫停／取消不會自動復活。失敗自動重試最多 3 次，後續須人工重試。`collection_attempts` 保存所有嘗試的 job ID。
- 官方月／日歷史 ZIP + SHA256；僅不存在的檔案退回較小檔案／REST，校驗或格式錯誤會讓任務失敗。2025-01 起現貨檔微秒轉毫秒，保留原始 CSV payload 及來源單位。
- 明確的區間重新匯入：最多 31 天，建立 1m overwrite 任務；重新下載檔案與校驗，值有變更時 `candle_revisions` 保存前後 payload 及來源 ID。一般補缺口不會擅自重寫已有資料。
- 所有自動行情收集固定 1m。查詢支援 1m、3m、5m、15m、30m、1h、2h、4h、6h、8h、12h、1d、3d、1w、1M；不提供無法從 1m 重建的 1s。
- 新 Data 圖表／表格／品質／缺口使用相同分鐘序列服務。缺口修補建立對應 1m 任務；已存在的原生週期資料及所有舊 API 保留。首頁預設使用收集 metadata 與任務紀錄，不掃描全歷史 K 線計數。

## 資料一致性與品質

`history_next_ms` 和 `tail_next_ms` 是**已掃描進度**，可跨過已記錄的不完整區段。`tail_complete_until_ms` 是從近期收集起點開始的**連續完整時間**，不能跨缺口，並不代表上市以來完整。

每個終態區段核對實際分鐘數；不完整段保留缺失數。手動補資料也會增加 minute revision；協調器每回合最多重查 4 個來源已變動的不完整段，修補後更新已知缺失及連續 watermark。未知源頭、失敗、取消及尚未掃描的部分不能因缺失計數為 0 就視為完整。

所有 K 線、source manifest、修訂 audit、minute revision、job 游標、計數及批次憑證仍走同一寫入交易。網路下載不占 SQLite 交易；失效 worker 不能繼續寫入或提交來源資訊。`delete_reload` 保持先抓到有效批次再替換。

彙整使用 Decimal：第一根 open、最大 high、最小 low、最後 close；各成交量與交易筆數相加。UTC 週一開週；3d 原點由官方樣本驗證為 Unix epoch + 1 天；1M 使用日曆月。`closed` 與 `complete` 分開；未收盤、首個不滿桶與未知缺少分鐘分別標記。無資料的桶不生成假 OHLC。

已知最早可取得時間之前不列為可修補缺口。沒有歷史停牌事件證據時，不把未知缺漏臆測為停牌；目前交易所狀態可由 coverage 的 catalog context 取得。圖表轉浮點僅用於繪圖，表格與 API 保持小數字串。

## API 契約

對外以下路徑加上 `APP_BASE_PATH`（預設 `/tradebridge`）；管理 API 的身分保護維持既有本機部署邊界。

| 路徑 | 行為 |
| --- | --- |
| `POST /api/v1/market-catalog/sync` | 202，同步目錄；支援 Idempotency-Key，不下載 K 線 |
| `GET /api/v1/market-catalog` | search、cursor、limit；完整目錄分頁 |
| `GET /api/v1/market-catalog/syncs/latest` | 最近目錄任務狀態，不洩漏 token |
| `GET /api/v1/collection` | 政策、目錄及納管數、區段狀態、已知缺失、游標 |
| `GET /api/v1/collection/preview` | 市場數、空間、衝突排程；不建立抓取任務 |
| `POST /api/v1/collection/start` | 使用 preview 的 revision 與明示暫停排程清單啟用政策 |
| `PATCH /api/v1/collection/policy` | 調整更新頻率、佇列、磁碟保留；不隱含啟用 |
| `POST /api/v1/collection/control` | all/history，paused true/false |
| `GET/PATCH /api/v1/collection/markets[/symbol]` | 逐市場進度／排除 |
| `POST /api/v1/collection/retry` | 202，建立有限區段重試；回傳 job_ids |
| `GET /api/v1/candle-series` | UTC 分桶的分鐘衍生序列 |
| `GET /api/v1/candle-series/gaps` | 同一窗口與游標的來源分鐘缺口 |
| `GET /api/v1/candle-series/coverage` | 儲存首尾、收集游標與市場 context；首尾不是完整率 |
| `POST /api/v1/candle-series/reimport` | 202，明確 start_ms/end_ms，至多 31 天，支援 Idempotency-Key |
| `GET /api/v1/external/candle-series[/coverage,/gaps]` | 對應唯讀序列端點，沿用 X-API-Key |

序列請求：`market_pair`、`interval`、`start_ms`、`end_ms`、`limit`（1–1000）、`cursor`、`complete_only`（預設 true）、`include_open`（預設 false）。時間條件是桶開盤時間的 `[start_ms,end_ms)`；起點不在桶邊界時向上對齊。不指定時間預設最近有資料的範圍。

每頁至多掃描 44,640 根來源分鐘。長範圍回傳 `next_cursor`，客戶端保持原篩選條件逐頁讀取；`count` 是本頁實際輸出根數，不是全區間 COUNT。即使沒有符合品質的桶，仍可有下一頁。`quality.gaps` 使用結束時間不含的分鐘範圍；查詢不回傳交易所 raw_payload。

### 與草稿的實作選擇

- 將 P1–P3 合為同一個相容功能批次 1.2.0，沒有另外產生草稿中的 1.3.0。
- 長查詢採有限來源窗口與 cursor，沒有引入非必要的非同步查詢工作系統。跨頁固定 as_of；若來源中途修訂，每頁附 source_revision，跨頁不宣稱同一歷史資料快照。
- 快取採**市場 minute revision**，沒有 dirty-range 細分；最多 20,000 個桶。讀取快照後，發布快取再次比對 revision。這較保守但可避免修補競爭導致舊值復活。
- 每個歷史 job 至多持有一個月解析資料（44,640 根）；ZIP 32 MiB、解壓 CSV 128 MiB 上限，不落地解壓。兩 worker 共享 archive origin 限流與 Retry-After 冷卻。不同區段可能重下同一月檔，尚無跨 job 檔案快取。
- 全量的意思是當前可交易與後續新上市現貨，包含非 USDT；不宣稱能復原官方已不可得的歷史，或自動找到啟用前已消失的全部下架市場。

## 容量與官方核對證據

2026-09-21，Windows 10、Python 3.13.15、SQLite 3.53.1，獨立暫存 DB，一百萬根合成分鐘線：

| 測量 | 結果 |
| --- | ---: |
| DB 含索引 | 681,861,120 bytes |
| 每根增量平均 | 681.48 bytes |
| 寫入 1,000,000 根 | 93.079 秒，10,744 根／秒 |
| 最近 1,000 根查詢 p95，20 次 | 33.18 ms |
| 31 天 → 1h 查詢 p95，20 次 | 800.49 ms |
| 同時寫入時控制操作 p95，20 次 | 50.18 ms |
| 百萬根串流缺口掃描 | 15.625 秒 |
| 缺口掃描 Python 配置記憶體峰值 | 548,858 bytes |
| 固定讀取快照期間觀測 WAL | 2,710,992 bytes |
| SQLite backup + integrity_check | 15.499 秒 |

命令：`.venv/Scripts/python.exe scripts/benchmark_minute_storage.py --rows 1000000 --temp-dir .runtime`。合成價格固定寬度、單市場、讀取已暖機、一個並行 writer；不等同完整市場壓測，記憶體數字不是進程 RSS。腳本只建立並清理自己的暫存 DB。

官方小樣本：BTCUSDT 2017-08-18、BTCUSDT／ETHBTC／LTCBTC 2025-01-01，共 5,760 根；ZIP 約 33–69 KB／日，SQLite 增量約 704 bytes／根。校驗 SHA256、微秒格式及 5m OHLCV／各成交量／交易筆數與官方 REST 精確相符。3d 測試覆蓋 2017、2024、2025；週／月界線亦核對。可重現命令：`python scripts/verify_minute_sources.py`（固定小樣本，需要外網）。

以 704 bytes／根推算，單對平年約 370 MB；**假設** 1,000 對各 5 年約 1.85 TB，尚未含 WAL、修訂、備份等空間。不是目前市場年齡的總容量預估。預設保留 10 GiB，低於保留停止自動工作；不刪歷史。Docker 量測是容器資料卷檔案系統空間，薄配置虛擬磁碟仍需檢查宿主機實際餘量。需要全量運行時依實際市場起點、吞吐及磁碟調整政策。

官方規格：[歷史檔及修訂](https://github.com/binance/binance-public-data)、[Spot API](https://developers.binance.com/en/docs/binance-spot-api-docs/rest-api)。

## 驗收紀錄

| 項目 | 證據與結果 |
| --- | --- |
| 全後端回歸 | `python -m pytest backend/tests -q`：273 passed；包含原 job reliability 崩潰、租約、重啟、批次原子性測試 |
| 大目錄／公平性 | 2,501 筆目錄跨頁無截斷；1,000 市場仍維持 100 個待處理上限，人工／近期／歷史公平 claim |
| 控制及一致性 | exclude、HALT、政策暫停的寫入防護；user pause/cancel、held容量、stale catalog、時鐘偏差、排程明示衝突、連續 watermark及重試追溯 |
| 來源及彙整 | SHA256 失敗、CSV 格式、ms/us、改檔重匯及交易回滾；Decimal、3d/週/月、空桶/未收盤/首桶、跨頁、修補/重設與快取競爭 |
| 舊版升級／還原 | `python scripts/verify_minute_upgrade.py --baseline ab34599`：真實舊版程式建立 schema 1，升級 schema 2、重入及原版程式還原備份全部通過 |
| 前端 | TypeScript + Vite 正式建置通過；既有大 bundle 提示保留 |
| 隔離部署 | 8088、`tradebridge-minute-verify-final-data`；Compose 健康及 `check_deployment.py --disposable` 42 項通過 |
| 真實目錄 | 2026-09-21 同步 3,665 筆，當時 1,368 可交易；政策仍關閉，未排任何自動抓取 |
| 瀏覽器 | 無目錄時啟動禁用；空資料、設定保存/重載、1,000 根有限 BTC 回補、5m 表格/圖表、重匯確認；單市場延後探索 fixture 驗證啟動/只暫停歷史/全部暫停 |
| 鍵盤／窄螢幕 | 用鍵盤切 5m；390px viewport 檢查，頁面 clientWidth=scrollWidth=375，表格可橫向捲動；已清除 viewport override。不是完整 WCAG 審核 |
| 外部 API | 隔離臨時 Key 讀取 199 根完整 5m 與既有原生 API 均 200；無 Key 401；Key 清理完成 |

已有 Starlette/httpx 棄用提示不影響通過。未實際下載全市場多年歷史；沒有宣稱此電腦能在固定時間完成或容納所有資料。新版政策預設關閉，隔離驗證後亦已暫停。

## 升級與回復

先停止派工／後端並以 SQLite backup API 或完整停機資料卷備份，確認 integrity_check。部署前後端同版本並先執行 schema 2 初始化，再開 worker；`.env` 若覆寫 APP_VERSION 需同步修改。預設關閉新政策，舊 API、原生資料、排程與使用者暫停紀錄保留。

回復時停止新版、保存當前資料副本，還原升級前備份並使用 1.1.1 程式。備份後新增資料不包含在舊備份內；不要用 Git revert 直接讓舊程式讀 schema 2，不刪除正式資料卷。


### 本次運行狀態

原本 8080 服務仍為 **1.1.1**，沒有切換。自動核准審查拒絕停止原後端：功能實作授權未明確包含會中斷現有服務的部署切換，需使用者另行批准。已採不中斷的 SQLite backup API 建立 `/app/data/tradebridge.pre-minute-1.2.0.20260921T144401Z.db`，integrity_check 通過；schema 1，原庫當時 0 根 K 線、0 個工作。備份位於原 `tradebridge_tradebridge-data` 資料卷。

1.2.0 的容器及瀏覽器驗收在獨立 8088／`tradebridge-minute-verify-final-data` 完成，不以測試資料取代原庫。單市場控制測試曾手動限制測試庫的市場設定及延後探索，不能把該測試卷當作正式資料卷部署。驗證後已停止該獨立測試專案並保留測試卷；原 8080 仍正常運行。Git 提交後不 push、不 tag。
