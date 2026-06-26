export type Language = "zh-TW" | "en-US";

export const messages = {
  "zh-TW": {
    app: {
      caption: "市場資料中控",
      local: "本機環境",
      apiReady: "已連線",
      providerStatus: "來源狀態",
      language: "語言",
      languageZh: "中文",
      languageEn: "EN",
      collapse: "收合"
    },
    nav: {
      dashboard: "儀表板",
      data: "資料",
      jobs: "任務",
      settings: "設定"
    },
    common: {
      healthy: "正常",
      success: "成功",
      warning: "注意",
      failed: "失敗",
      complete: "完整",
      gaps: "個缺口",
      latest: "最新",
      cancel: "取消",
      binance: "Binance",
      mockData: "模擬資料",
      available: "可用資料",
      missing: "缺漏資料",
      noData: "無資料",
      viewAll: "查看全部"
    },
    dashboard: {
      title: "儀表板",
      subtitle: "市場資料健康度與同步狀態總覽",
      openData: "開啟市場資料",
      startFetch: "前往資料頁",
      dataCoverage: "資料覆蓋率",
      providerStatus: "來源狀態",
      recentSyncActivity: "最近同步活動",
      quickActions: "快速操作",
      alerts: "警示",
      viewAllActivities: "查看全部活動",
      viewAllAlerts: "查看全部警示",
      marketData: "開啟市場資料",
      marketDataDescription: "檢視與分析資料",
      fetch: "同步紀錄",
      fetchDescription: "查看最近同步結果",
      jobs: "查看任務",
      jobsDescription: "監控背景任務",
      settings: "設定",
      settingsDescription: "系統設定",
      missingRangesAlert: "BTC/USDT 1m 目前有 2 個缺口",
      noScheduledJobs: "尚未設定排程任務",
      coverageRange: "2025-06-12 ~ 2025-06-19",
      kpis: {
        trackedSymbols: {
          label: "追蹤資產",
          detail: "BTC/USDT / ETH/USDT",
          trend: "+2"
        },
        storedCandles: {
          label: "已儲存 K 線",
          detail: "較昨日",
          trend: "+6.3%"
        },
        latestSync: {
          label: "最近同步",
          detail: "成功",
          trend: "2 分鐘前"
        },
        dataGaps: {
          label: "資料缺口",
          detail: "較昨日",
          trend: "+2"
        }
      },
      table: {
        time: "時間",
        source: "來源",
        symbol: "資產",
        interval: "週期",
        rows: "筆數",
        status: "狀態",
        duration: "耗時"
      }
    },
    data: {
      title: "市場資料",
      subtitle: "抓取與檢視 BTC/USDT / ETH/USDT K 線資料",
      exchange: "交易所",
      symbol: "資產",
      interval: "週期",
      dateRange: "日期範圍",
      startDate: "起始日",
      limit: "筆數上限",
      fetch: "抓取",
      fetchData: "抓取資料",
      refetch: "重新抓取",
      storedRows: "已儲存筆數",
      storedRowsDetail: "資料庫總計",
      latestCandle: "最新 K 線",
      missingRanges: "缺漏範圍",
      noGapsDetected: "未偵測到缺口",
      lastSync: "最近同步",
      fewSecondsAgo: "幾秒前",
      candlePreview: "BTC/USDT - 15m - Binance",
      chartOhlc: "O 66,780.12  H 66,920.35  L 66,720.01  C 66,892.41  +112.29 (+0.17%)",
      apiStatus: "API 狀態",
      provider: "提供者",
      sourceMarket: "來源市場",
      status: "狀態",
      providerStatus: "來源狀態",
      latency: "延遲",
      lastRequest: "最近請求",
      rowsReturned: "回傳筆數",
      backendNotConnected: "後端尚未串接，目前此頁使用模擬資料。",
      candleRows: "BTC/USDT K 線資料列",
      showingRows: "顯示 1 到 5 筆，共 500 筆",
      drawerTitle: "重新抓取資料",
      mode: "模式",
      fillGaps: "補齊缺口",
      overwriteRange: "覆蓋範圍",
      deleteReload: "刪除後重抓",
      overwriteWarning: "覆蓋與刪除模式會修改選取範圍內的既有資料。此動作無法復原。",
      validateRows: "驗證既有資料列",
      runAsBackgroundJob: "作為背景任務執行",
      startRefetch: "開始重新抓取",
      maxRowsHint: "每次請求最多抓取筆數",
      kpis: {
        lastPrice: {
          label: "最新價格",
          detail: "24h +1.8%",
          trend: "66,892.41"
        },
        change24h: {
          label: "24h 漲跌",
          detail: "高於 7 日均值",
          trend: "+1,327.62"
        },
        volume: {
          label: "成交量",
          detail: "近 24 小時",
          trend: "28,451.34 BTC/USDT"
        },
        latestCandle: {
          label: "最新 K 線時間",
          detail: "15m 週期，已收線",
          trend: "2024-05-17 15:30:00"
        }
      },
      table: {
        time: "時間",
        open: "開盤",
        high: "最高",
        low: "最低",
        close: "收盤",
        volume: "成交量",
        trades: "成交筆數",
        source: "來源"
      }
    },
    provider: {
      binanceApi: "Binance API",
      marketEndpoint: "公開市場資料端點正常",
      latency: "平均延遲",
      quotaUsed: "額度使用",
      requestQuota: "請求額度",
      lastSuccessfulResponse: "最近成功回應",
      errorRate: "24h 錯誤率",
      status: "狀態",
      allSystemsOperational: "所有系統運作正常"
    },
    jobs: {
      title: "任務",
      subtitle: "背景抓取與重新抓取任務會顯示在這裡。",
      empty: "目前沒有背景任務"
    },
    settings: {
      title: "設定",
      subtitle: "來源預設值與應用偏好之後會在這裡設定。",
      empty: "尚未設定任何項目"
    }
  },
  "en-US": {
    app: {
      caption: "Market Ops",
      local: "Local",
      apiReady: "Connected",
      providerStatus: "Provider status",
      language: "Language",
      languageZh: "中文",
      languageEn: "EN",
      collapse: "Collapse"
    },
    nav: {
      dashboard: "Dashboard",
      data: "Data",
      jobs: "Jobs",
      settings: "Settings"
    },
    common: {
      healthy: "Healthy",
      success: "Success",
      warning: "Warning",
      failed: "Failed",
      complete: "Complete",
      gaps: "gaps",
      latest: "Latest",
      cancel: "Cancel",
      binance: "Binance",
      mockData: "Mock data",
      available: "Data Available",
      missing: "Missing Data",
      noData: "No Data",
      viewAll: "View all"
    },
    dashboard: {
      title: "Dashboard",
      subtitle: "Market data health and sync overview",
      openData: "Open Market Data",
      startFetch: "Open Data Page",
      dataCoverage: "Data Coverage",
      providerStatus: "Provider Status",
      recentSyncActivity: "Recent Sync Activity",
      quickActions: "Quick Actions",
      alerts: "Alerts",
      viewAllActivities: "View all activities",
      viewAllAlerts: "View all alerts",
      marketData: "Open Market Data",
      marketDataDescription: "View and analyze data",
      fetch: "Sync Log",
      fetchDescription: "Review recent sync results",
      jobs: "View Jobs",
      jobsDescription: "Monitor jobs",
      settings: "Settings",
      settingsDescription: "System settings",
      missingRangesAlert: "BTC/USDT 1m has 2 missing ranges",
      noScheduledJobs: "No scheduled jobs configured",
      coverageRange: "2025-06-12 ~ 2025-06-19",
      kpis: {
        trackedSymbols: {
          label: "Tracked Markets",
          detail: "BTC/USDT / ETH/USDT",
          trend: "+2"
        },
        storedCandles: {
          label: "Stored Candles",
          detail: "vs yesterday",
          trend: "+6.3%"
        },
        latestSync: {
          label: "Latest Sync",
          detail: "Success",
          trend: "2m ago"
        },
        dataGaps: {
          label: "Data Gaps",
          detail: "vs yesterday",
          trend: "+2"
        }
      },
      table: {
        time: "Time",
        source: "Source",
        symbol: "Market",
        interval: "Interval",
        rows: "Rows",
        status: "Status",
        duration: "Duration"
      }
    },
    data: {
      title: "Market Data",
      subtitle: "Fetch and inspect BTC/USDT / ETH/USDT candles",
      exchange: "Exchange",
      symbol: "Market",
      interval: "Interval",
      dateRange: "Date Range",
      startDate: "Start Date",
      limit: "Limit",
      fetch: "Fetch",
      fetchData: "Fetch Data",
      refetch: "Re-fetch",
      storedRows: "Stored Rows",
      storedRowsDetail: "Total in database",
      latestCandle: "Latest Candle",
      missingRanges: "Missing Ranges",
      noGapsDetected: "No gaps detected",
      lastSync: "Last Sync",
      fewSecondsAgo: "a few seconds ago",
      candlePreview: "BTC/USDT - 15m - Binance",
      chartOhlc: "O 66,780.12  H 66,920.35  L 66,720.01  C 66,892.41  +112.29 (+0.17%)",
      apiStatus: "API Status",
      provider: "Provider",
      sourceMarket: "Source Market",
      status: "Status",
      providerStatus: "Provider Status",
      latency: "Latency",
      lastRequest: "Last Request",
      rowsReturned: "Rows Returned",
      backendNotConnected: "Backend is not connected yet. This page uses mock data.",
      candleRows: "BTC/USDT Candle Rows",
      showingRows: "Showing 1 to 5 of 500 rows",
      drawerTitle: "Re-fetch Data",
      mode: "Mode",
      fillGaps: "Fill gaps",
      overwriteRange: "Overwrite range",
      deleteReload: "Delete and reload",
      overwriteWarning: "Overwrite and delete modes will modify existing data in the selected range. This action cannot be undone.",
      validateRows: "Validate existing rows",
      runAsBackgroundJob: "Run as background job",
      startRefetch: "Start Re-fetch",
      maxRowsHint: "Max rows to fetch per request",
      kpis: {
        lastPrice: {
          label: "Last Price",
          detail: "+1.8% 24h",
          trend: "66,892.41"
        },
        change24h: {
          label: "24h Change",
          detail: "Above 7d mean",
          trend: "+1,327.62"
        },
        volume: {
          label: "Volume",
          detail: "Rolling 24h",
          trend: "28,451.34 BTC/USDT"
        },
        latestCandle: {
          label: "Latest Candle Time",
          detail: "15m interval, closed",
          trend: "2024-05-17 15:30:00"
        }
      },
      table: {
        time: "Time",
        open: "Open",
        high: "High",
        low: "Low",
        close: "Close",
        volume: "Volume",
        trades: "Trades",
        source: "Source"
      }
    },
    provider: {
      binanceApi: "Binance API",
      marketEndpoint: "Healthy public market endpoint",
      latency: "Latency (avg)",
      quotaUsed: "Quota Used",
      requestQuota: "Request Quota",
      lastSuccessfulResponse: "Last Successful Response",
      errorRate: "Error Rate (24h)",
      status: "Status",
      allSystemsOperational: "All systems operational"
    },
    jobs: {
      title: "Jobs",
      subtitle: "Background fetch and re-fetch tasks will appear here.",
      empty: "No background jobs yet"
    },
    settings: {
      title: "Settings",
      subtitle: "Provider defaults and app preferences will be configured here.",
      empty: "Settings are not configured yet"
    }
  }
} as const;

export type AppMessages = (typeof messages)[Language];
