# TradeBridge 專案指引

適用範圍：整個儲存庫。架構基準整理日期：2026-09-19；功能變更時同步更新相關描述。

## 專案定位與現況

- TradeBridge 是本機部署的行情 K 線資料管理工具，目前支援 Binance 現貨。
- 核心功能：市場管理、歷史回補、增量同步、缺口檢查與修補、排程、可恢復的背景任務、資料查詢及外部唯讀 API。
- 尚未有策略、回測、委託下單、持倉與交易風控引擎；描述產品時應區分已實作能力與未來構想。
- 通知目前有設定介面與儲存，尚未看到完整發送流程。資料重設提供可選備份，尚未有完整定期備份與還原流程。
- 多供應商介面已預留，但目前仍限定 Binance；存在 `market_type` 欄位不代表已支援現貨以外的市場。

完整分析見 [整體架構與未來方向](docs/architecture-and-direction.md)，任務設計以 [任務可靠性說明](docs/decisions/task-reliability.md) 為依據。

## 整體架構

- 前端：React 19、TypeScript、Vite、Ant Design。`frontend/src/pages/` 包含 Dashboard、Data、Jobs、Settings；共用請求在 `shared/api/`，行情 API 與元件在 `features/market-data/`。
- 後端：Python 3.11+、FastAPI，採模組化單體。`backend/src/app/main.py` 管理啟動、資料庫初始化與背景服務生命週期。
- `api/v1/`：API 路由與依賴組裝；`schemas/`：請求及回應格式。
- `application/services/`：使用案例與流程；`application/ports/`：供應商、儲存與任務執行介面；`application/models/`：應用資料模型。
- `domain/`：K 線實體、市場代碼、週期及供應商值物件。
- `infrastructure/external/`：Binance client、provider registry 與限流；`infrastructure/persistence/`：SQLite Repository、交易與升級；`infrastructure/scheduler/`：排程器與任務執行器。
- 核心服務透過 ports 使用外部能力，由 `api/v1/dependencies.py` 組裝具體實作。擴充時維持此依賴方向，避免將交易所請求或 SQLite 細節放入領域模型。
- 部署：Docker Compose 的 Nginx 前端代理 FastAPI，SQLite 存於持久化資料卷。排程器與 worker 仍位於同一後端進程。
- 自 0.2.0 起整站預設 `/tradebridge/`，公開 API 為 `/tradebridge/api/v1`。以根目錄 `.env` 的 `APP_BASE_PATH` 同步設定前端建置與後端 `root_path`；內部 `API_PREFIX` 維持 `/api/v1`。更改前綴需重建前端，勿在個別 API 呼叫硬編碼專案名稱。
- 外層反向代理保留專案前綴與公開 Host、覆寫轉送協定標頭。自 1.0.0 起公開入口僅限 `APP_BASE_PATH` 範圍，移除舊 API 代理、舊文件轉址及根目錄轉址。後端內部路由維持 `/api/v1`，健康檢查帶上專案前綴以支援 `/api` 等名稱。API 未知路徑不可落入前端 HTML fallback。共用網域使用部署檢查的 `--mode proxy`，不得請求專案外的其他服務。

## 任務與資料一致性

修改抓取、排程或儲存流程時，維持下列既有契約：

1. 抓取入口先持久化任務，回傳 202 與任務資訊；前端輪詢進度。
2. 排程器只建立任務，由 JobRunner 統一執行。預設最多同時執行兩個不同市場；同市場的不同週期依序執行。
3. 保留租約、心跳與 execution token 防護，阻止失效 worker 繼續寫入。
4. K 線、游標、計數與批次憑證須在同一資料庫交易提交；網路請求置於交易之外。
5. 保留建立任務的冪等鍵與排程觸發防重複機制。
6. 暫停、取消與重啟恢復保留已提交資料；使用者暫停的任務不自動恢復。
7. `delete_reload` 先取得並驗證一批資料，再於交易內替換該批，不先清空整個請求區間。
8. K 線唯一性包含 provider、market_type、exchange_symbol、interval、open_time_ms；保留原始供應商 payload。

## 部署與維護邊界

- 現有設計使用單一後端容器與單一 Uvicorn worker。未完成跨程序限流、維護鎖與排程協調前，不直接增加副本。
- 自 2.0.0 起，管理 API／文件以 `.env` 單一管理員帳密與 12 小時 Cookie session 保護。8080 僅本機免登入（Nginx 內部密鑰），8081 必須登入；兩者綁定 `127.0.0.1`，對外代理只可接 8081。不得以 APP_ENV、Host 或使用者傳入的轉送標頭繞過登入；登入端清除免登入標頭。外部唯讀 API 始終另驗 API Key。管理修改請求均檢查 Origin 與自訂標頭。帳密及密鑰不可進入前端建置或 Git。
- 資料庫升級與回復遵循任務可靠性文件；勿將刪除資料卷或重設使用者資料當成一般驗證步驟。
- 前端主要頁面已有 API 串接，個別元件仍保留模擬預設值。修改狀態呈現時區分真實健康狀態、載入中、空資料與錯誤。

## 未來目標與建議順序

以下是架構檢視提出的建議方向，不代表功能已完成或所有項目已授權立即實作。依當次需求選擇工作範圍。

長期定位：把交易所行情轉成可靠、可追溯、可重複使用的資料，供研究、回測、報表與策略系統使用。

1. **運行可靠性與使用體驗**：真實健康狀態、拆分大型頁面、完成通知、定期備份與還原驗證；持續驗證管理端保護與部署隔離。
2. **資料服務能力**：完善外部 API 契約、分頁、版本與範例，加入 CSV／Parquet 匯出及資料新鮮度、覆蓋率、缺口品質資訊。
3. **多來源擴充**：以第二個供應商驗證抽象，同步調整型別、設定、前端、限流與測試；其他市場需完整檢查識別及查詢流程。
4. **按負載擴展**：先測量，再決定分離 API／worker、調整資料庫或引入即時行情。擴展後仍須保持任務及批次一致性。
5. **遠期整合**：讓獨立研究、回測與策略系統使用資料 API；實盤交易屬新的產品範圍，需要另行設計。

現階段優先維持模組化單體，逐步改善既有能力。不要僅因未來可能擴充就預先導入微服務或更換資料庫。

## 版本管理規則

版本格式為 `MAJOR.MINOR.PATCH`（大版.中版.小版），前後端採同一產品版本。初次建立本指引的 0.1.0 文件提交不升版；後續改動均適用下列規則。

- 每一批完成並交付的儲存庫改動都必須更新版本，包含程式、介面、設定、相依套件、測試與文件；僅閱讀或沒有檔案變更時不升版。
- 同一批工作包含多個檔案或多次修正，只升版一次；依該批影響最高的等級決定。不要每次存檔升版，也不要為版本號及變更日誌本身的更新遞迴升版。

| 等級 | 調整規則 | 範例 |
| --- | --- | --- |
| 大版 MAJOR | 不相容變更：移除或改變既有 API 契約、使既有客戶端或使用流程必須修改、無法透明升級的資料格式變更。主版加一，其餘歸零。 | `1.4.2 → 2.0.0` |
| 中版 MINOR | 向後相容的新功能或能力，例如新增供應商、匯出格式、API 或完整功能頁。次版加一，小版歸零。 | `1.4.2 → 1.5.0` |
| 小版 PATCH | 向後相容的錯誤修正、樣式微調、效能改善、內部重構、文件、測試或維護性設定／依賴更新。修訂版加一。 | `1.4.2 → 1.4.3` |

- 以相容性與功能影響判斷，不以修改行數判斷；依賴更新若造成不相容變更，仍歸大版。
- `0.x.y` 開發階段仍遵守以上專案規則：相容新功能升中版、修正升小版，不以尚未到 1.0 為由隱藏破壞性變更；首次穩定發布也可作為升至 `1.0.0` 的里程碑。
- 升版時同步更新 `pyproject.toml`、`uv.lock` 中 TradeBridge 自身的版本、`frontend/package.json`、`frontend/package-lock.json` 中根專案的版本、`backend/src/app/core/settings.py` 的版本預設值及 `env.example` 的 `APP_VERSION`。不要誤改第三方套件版本；若之後建立單一版本來源，改用該來源與產生流程。
- 每次升版同步維護根目錄 `CHANGELOG.md`（首次執行時建立），記錄版本、日期、改動摘要、相容性／遷移影響與實際驗證結果。
- 前端側欄顯示建置版本，由 Vite 讀取 `frontend/package.json` 注入 `__APP_VERSION__`，不可另寫固定字串。「安全與環境」分別顯示前端建置版本及 runtime API 回傳的後端運行版本（可能受 `APP_VERSION` 覆寫）；無法取得後端版本時不得改用前端版本代替。
- 每一批修改完成後，先完成相關驗證、版本與 CHANGELOG 更新，再主動 Git commit，最後回報交付；不需等待使用者另外要求 commit。這是本專案持續有效的提交授權，除非使用者當次明確要求暫不提交。
- 提交前檢查工作區及暫存差異，只納入本批工作，不混入無關或未完成的修改；沒有檔案變更時不建立空提交。若驗證或提交受阻，明確回報原因，不宣稱已完成提交。
- 交付時回報舊版、新版、升版原因與 commit 短碼。自動 commit 不包含 push 或建立 tag，這兩項另依使用者指示執行。

## 開發與驗證

以下指令均從專案根目錄執行；先依 README 在私有 `.env` 設定必要帳密及內部密鑰：

```sh
uv sync --extra dev
uv run --env-file env.example --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8025 --reload --reload-dir backend/src
npm --prefix frontend ci
npm --prefix frontend run dev
```

依變更範圍先執行相關測試；需要整體驗證時使用：

```sh
uv run --extra dev pytest backend/tests -q
npm --prefix frontend run build
```

任務可靠性改動需涵蓋 `backend/tests/integration/test_job_reliability.py`；前端建置包含 TypeScript 檢查，但不等同瀏覽器互動驗證。純文件修改檢查路徑、連結與格式即可。回報時區分已執行驗證與僅閱讀程式得到的判斷。
