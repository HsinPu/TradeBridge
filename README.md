# TradeBridge

行情 K 線資料管理工具：FastAPI 後端、React 管理介面、SQLite 儲存，以及進程內資料抓取排程。目前支援 Binance 資料來源。

## Docker 一鍵啟動

先安裝並啟動 Docker Desktop（Linux containers），或 Docker Engine 與 Docker Compose 2.24+。
在**本檔案與 `compose.yaml` 所在的專案根目錄**執行：

```sh
docker compose up --build -d --wait
```

不需先安裝 Python、Node.js、建立 `.env` 或手動初始化資料庫。第一次建置需連網下載映像與依賴；`--wait` 會等待兩個服務通過健康檢查。

- 管理介面：<http://127.0.0.1:8080/tradebridge/>
- API 文件：<http://127.0.0.1:8080/tradebridge/docs>
- 健康檢查：<http://127.0.0.1:8080/tradebridge/api/v1/health>

前端由 Nginx 提供，整站位於 `/tradebridge/`，包含靜態資源、API 與文件；瀏覽器使用同一個網址，無需額外設定 API 位址或 CORS。後端不對主機發布連接埠。管理 API 沒有完整登入保護，因此預設只綁定 `127.0.0.1`，適合本機使用；外部唯讀 API 的 API Key 不等於管理介面的存取保護。

舊首頁 `/` 導向 `/tradebridge/`；舊 `/docs`、`/redoc`、`/openapi.json` 導向帶前綴的入口。舊 `/api/v1/...` 保留直接代理相容性，POST/PATCH 不經重新導向。

## 常用操作

以下命令都在專案根目錄執行：

```sh
docker compose ps                     # 查看服務與健康狀態
docker compose logs -f                # 查看日誌（Ctrl+C 離開日誌）
docker compose down                   # 停止並移除容器，保留資料
docker compose up --build -d --wait    # 重新啟動，或在修改程式後重新建置
```

SQLite 與相關檔案存放在 Docker 命名卷 `tradebridge_tradebridge-data`，掛載至後端 `/app/data`。容器重建和 `docker compose down` 都會保留資料；`docker compose down -v` **會刪除資料卷及資料**。若使用 `-p` 自訂專案名稱，資料卷前綴也會改變。主機原有的 `data/tradebridge.db` 不會自動匯入。

後端固定一個 Uvicorn worker，預設啟用排程。抓取任務先存入 SQLite，再由執行器處理；預設同時執行 2 個不同市場，同市場的不同週期依序執行。重啟後會接續已提交的進度，手動暫停的任務保持暫停。

請保持單一後端容器，不要增加 worker 或用 `--scale backend=...`，以免重複執行排程。

## 可選設定

需要調整時，在根目錄建立 `.env`，只填要覆寫的項目，例如：

```dotenv
WEB_PORT=8088
SCHEDULER_ENABLED=false
LOG_LEVEL=DEBUG
```

再次執行啟動命令即可套用；上述範例的介面網址是 <http://127.0.0.1:8088/tradebridge/>。其他後端選項見 `env.example`，Compose 會依序讀取 `env.example` 和可選的 `.env`。容器內 `APP_ENV=docker`、`API_PREFIX=/api/v1`、`DATABASE_PATH=/app/data/tradebridge.db` 固定由 Compose 設定；Docker 前端也固定使用同源 API，無需改 `VITE_API_BASE_URL`。若既有 `.env` 指定 `APP_VERSION`，升版時請同步更新或移除此覆寫。

## 專案路徑與反向代理

`APP_BASE_PATH` 預設 `/tradebridge`。要換成 `/tools/market-data`，請在根目錄 `.env` 設定 `APP_BASE_PATH=/tools/market-data`，再執行 `docker compose up --build -d --wait`。Compose 以該設定同時傳入前端建置與後端；尾端 `/` 會移除。路徑每一段只接受英文字母、數字、`_`、`-`，不接受根路徑、完整網址、空白、`.`、查詢參數或重複斜線。變更前綴必須重建前端，僅改容器環境不足以更新已建置的 JS/CSS；前端啟動時會檢查建置與運行前綴是否一致。

後端路由仍使用 `/api/v1`，FastAPI 的 `root_path` 表示對外專案前綴；不要將 `API_PREFIX` 改成包含 `/tradebridge` 的值。對外 API 為 `APP_BASE_PATH + API_PREFIX`，文件的 OpenAPI servers 也使用相同前綴。

共用網域上的外層 Nginx 範例（與 Docker 位於同一台主機）：

```nginx
location = /tradebridge {
    return 308 /tradebridge/;
}
location /tradebridge/ {
    # 不加尾端斜線：保留 /tradebridge/，不要在外層移除前綴。
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

TradeBridge 自身 Nginx 將公開路徑原樣送到後端，由 FastAPI 處理前綴；靜態檔案則在 Nginx 內對應至建置輸出。外層僅需映射 `/tradebridge/`，不需佔用共用網域的 `/api/` 或 `/docs`。外層代理須覆寫轉送標頭；保留預設本機綁定，僅讓可信任的代理接入。HTTPS 在外層終止時，`Host` 與 `X-Forwarded-Proto` 讓文件、重新導向及「安全與環境」使用公開網址。若外層代理在另一個容器，需另行配置受控的容器網路，不能直接使用此主機迴環範例。

若連接埠被佔用，可調整 `WEB_PORT`。若啟動或抓取失敗，先查看 `docker compose logs backend`；抓取行情另需能連線到設定的資料供應商，健康檢查成功不代表供應商一定可用。

## 不使用 Docker 的開發方式

後端使用 Python 3.11+ 與 uv，在根目錄執行：

```sh
uv sync --extra dev
uv run --env-file env.example uvicorn app.main:app --host 127.0.0.1 --port 8025 --reload --reload-dir backend/src
```

另開終端機，在 `frontend` 目錄執行 `npm ci`、`npm run dev`，並開啟 <http://127.0.0.1:5173/tradebridge/>。前端預設連接 `http://127.0.0.1:8025`；要覆寫可在 `frontend/.env.local` 設定 `VITE_API_BASE_URL`，只填來源網址，不含專案前綴。前端會由 Vite base 自動加入 `/tradebridge`。

自訂路徑時，前端會讀取根目錄 `.env` 的 `APP_BASE_PATH`；後端本身不會自動讀取 `.env`，請用 `uv run --env-file env.example --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8025 --reload --reload-dir backend/src` 載入同一設定。環境變數可覆寫前端建置設定；若使用 Vite 的 mode 環境檔，也需確保與後端前綴一致。

更多後端 API 說明見 [backend/README.md](backend/README.md)。

部署後可執行 `uv run python scripts/check_deployment.py`，唯讀檢查新舊 API、靜態資源、文件、重新導向與版本。自訂前綴可加 `--base-path /tools/market-data`，自訂位址可加 `--url http://127.0.0.1:8088`。`--disposable` 會建立、停用並撤銷測試 API Key，僅供獨立暫存資料庫使用，不要對既有資料環境加此選項。

任務狀態、API 變更、資料庫升級與回復步驟見 [任務可靠性說明](docs/decisions/task-reliability.md)。
