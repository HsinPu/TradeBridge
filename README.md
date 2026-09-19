# TradeBridge

行情 K 線資料管理工具：FastAPI 後端、React 管理介面、SQLite 儲存，以及進程內資料抓取排程。目前支援 Binance 資料來源。

## Docker 一鍵啟動

先安裝並啟動 Docker Desktop（Linux containers），或 Docker Engine 與 Docker Compose 2.24+。
在**本檔案與 `compose.yaml` 所在的專案根目錄**執行：

```sh
docker compose up --build -d --wait
```

不需先安裝 Python、Node.js、建立 `.env` 或手動初始化資料庫。第一次建置需連網下載映像與依賴；`--wait` 會等待兩個服務通過健康檢查。

- 管理介面：<http://127.0.0.1:8080>
- API 文件：<http://127.0.0.1:8080/docs>
- 健康檢查：<http://127.0.0.1:8080/api/v1/health>

前端由 Nginx 提供，`/api/` 轉送至後端；瀏覽器使用同一個網址，無需額外設定 API 位址或 CORS。後端不對主機發布連接埠。管理 API 沒有完整登入保護，因此預設只綁定 `127.0.0.1`，適合本機使用；外部唯讀 API 的 API Key 不等於管理介面的存取保護。

## 常用操作

以下命令都在專案根目錄執行：

```sh
docker compose ps                     # 查看服務與健康狀態
docker compose logs -f                # 查看日誌（Ctrl+C 離開日誌）
docker compose down                   # 停止並移除容器，保留資料
docker compose up --build -d --wait    # 重新啟動，或在修改程式後重新建置
```

SQLite 與相關檔案存放在 Docker 命名卷 `tradebridge_tradebridge-data`，掛載至後端 `/app/data`。容器重建和 `docker compose down` 都會保留資料；`docker compose down -v` **會刪除資料卷及資料**。若使用 `-p` 自訂專案名稱，資料卷前綴也會改變。主機原有的 `data/tradebridge.db` 不會自動匯入。

後端固定一個 Uvicorn worker，預設啟用排程。請保持單一後端容器，不要增加 worker 或用 `--scale backend=...`，以免重複執行排程。

## 可選設定

需要調整時，在根目錄建立 `.env`，只填要覆寫的項目，例如：

```dotenv
WEB_PORT=8088
SCHEDULER_ENABLED=false
LOG_LEVEL=DEBUG
```

再次執行啟動命令即可套用；上述範例的介面網址是 <http://127.0.0.1:8088>。其他後端選項見 `env.example`，Compose 會依序讀取 `env.example` 和可選的 `.env`。容器內 `APP_ENV=docker`、`API_PREFIX=/api/v1`、`DATABASE_PATH=/app/data/tradebridge.db` 固定由 Compose 設定；Docker 前端也固定使用同源 API，無需改 `VITE_API_BASE_URL`。

若連接埠被佔用，可調整 `WEB_PORT`。若啟動或抓取失敗，先查看 `docker compose logs backend`；抓取行情另需能連線到設定的資料供應商，健康檢查成功不代表供應商一定可用。

## 不使用 Docker 的開發方式

後端使用 Python 3.11+ 與 uv，在根目錄執行：

```sh
uv sync --extra dev
uv run --env-file env.example uvicorn app.main:app --host 127.0.0.1 --port 8025 --reload --reload-dir backend/src
```

另開終端機，在 `frontend` 目錄執行 `npm ci`、`npm run dev`，並開啟 <http://127.0.0.1:5173>。前端預設連接 `http://127.0.0.1:8025`；要覆寫可在 `frontend/.env.local` 設定 `VITE_API_BASE_URL`。後端本身不會自動讀取 `.env`，此處透過 uv 的 `--env-file` 載入。

更多後端 API 說明見 [backend/README.md](backend/README.md)。
