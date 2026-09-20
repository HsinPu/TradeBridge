# 變更紀錄

## 0.2.0 — 2026-09-19

- 新增整站部署前綴，預設管理介面 `/tradebridge/`、API `/tradebridge/api/v1`、文件 `/tradebridge/docs`。
- 前端資源、API client、Nginx 與 FastAPI 共用 `APP_BASE_PATH`，支援經驗證的自訂路徑與尾端斜線正規化。
- 保留舊 `/api/v1` 的方法與請求內容；首頁與舊文件入口導向新的專案路徑。
- 保留可信任外層代理提供的公開網域與協定，讓文件、重新導向及環境 API 位址正確。
- 更新 Docker 健康檢查、部署文件與專案指引。

相容性：向後相容的新部署能力，因此由 0.1.0 升至 0.2.0。沒有資料庫結構變更。變更 `APP_BASE_PATH` 後須重新建置前端；`VITE_API_BASE_URL` 僅填來源網址，`API_PREFIX` 維持 `/api/v1`。既有 `.env` 若覆寫版本需同步調整。

驗證：完整後端測試 179 項通過（含新增部署前綴 16 項）；Docker 中 TypeScript 檢查及 Vite 建置通過；前後端容器健康檢查通過。實際部署唯讀檢查 16 項與隔離暫存資料庫的雙層代理檢查 24 項通過，含新舊 POST/PATCH、Key 驗證、公開 Host／HTTPS 協定資訊與尾端斜線正規化。瀏覽器已檢查四個主要頁面，設定頁 API 位址正確，Swagger 實際呼叫新路徑取得 200。HTTPS 驗證模擬代理協定標頭，未配置正式憑證或網域。

既有工具提示：後端測試有 Starlette/httpx 棄用提示；前端建置有大型 bundle 提示，npm 安裝回報 4 個依賴弱點（1 moderate、3 high），本次未變更第三方依賴。Windows 受限環境的本機 Vite 啟動受阻，已以 Docker 建置驗證。
