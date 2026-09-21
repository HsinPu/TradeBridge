import { CatalogPanel } from "../features/collection/CatalogPanel";
import {
  ApiOutlined,
  BellOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  DesktopOutlined,
  EditOutlined,
  KeyOutlined,
  LockOutlined,
  PlusOutlined,
  QuestionCircleOutlined,
  SaveOutlined,
  SearchOutlined,
  SettingOutlined,
  ThunderboltOutlined
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Drawer,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Switch,
  Tag,
  Tooltip,
  Typography
} from "antd";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createApiKey,
  createMarket,
  DEFAULT_MARKET_DATA_PROVIDER,
  deleteApiKey,
  deleteMarket,
  getInterfacePreferences,
  getNotificationSettings,
  getProviderDataSource,
  getRuntimeStatus,
  getStorageSettings,
  listApiKeys,
  listMarkets,
  listProviderMarkets,
  MARKET_DATA_PROVIDER_LABELS,
  resetDatabase,
  testProviderDataSource,
  updateApiKey,
  updateInterfacePreferences,
  updateNotificationSettings,
  updateProviderDataSource,
  updateStorageSettings,
  updateMarket
} from "../features/market-data/api";
import type {
  ApiKeyResponse,
  ApiKeyScope,
  InterfacePreferencesResponse,
  InterfacePreferencesUpdateRequest,
  InterfaceTheme,
  NotificationChannel,
  NotificationSettingsResponse,
  NotificationSettingsUpdateRequest,
  ProviderDataSourceUpdateRequest,
  DatabaseResetScope,
  MarketDataProviderName,
  MarketResponse,
  ProviderDataSourceResponse,
  RuntimeStatusResponse,
  ProviderMarketResponse,
  StorageSettingsResponse
} from "../features/market-data/api";
import type { AppMessages, Language } from "../shared/i18n/messages";

type SettingsPageProps = {
  messages: AppMessages;
  language: Language;
  onLanguageChange: (language: Language) => void;
};

const copy = {
  "zh-TW": {
    subtitle: "資料來源、資產管理與系統偏好。",
    save: "儲存設定",
    reset: "重設",
    dataSource: "資料來源",
    provider: "Provider",
    apiBaseUrl: "API Base URL",
    connected: "已連線",
    testConnection: "測試連線",
    timeout: "Request Timeout（秒）",
    rateLimit: "Rate Limit（權重/分鐘）",
    retries: "Retries",
    cooldown: "休息間隔（毫秒）",
    supportedMarkets: "資產管理",
    marketManagementHint: "管理可抓取的市場與交易對。",
    addMarket: "新增幣種",
    addMarketTitle: "新增幣種",
    addModeProvider: "幣安搜尋",
    addModeManual: "手動輸入",
    basicMarketInfo: "基本資料",
    marketPair: "交易對",
    baseAsset: "基礎幣種",
    marketSearch: "幣安交易對",
    marketSearchPlaceholder: "選擇或搜尋 BTC、DOGE、USDT",
    statusOptions: "狀態設定",
    saveMarket: "建立幣種",
    cancel: "取消",
    preview: "預覽",
    searchAsset: "搜尋資產",
    providerFilter: "Provider",
    onlyEnabled: "只看啟用",
    asset: "資產",
    sourceMarket: "來源代號",
    marketType: "市場類型",
    quoteCurrency: "報價幣種",
    defaultMarket: "預設",
    actions: "操作",
    spot: "現貨",
    status: "狀態",
    enabled: "啟用",
    storage: "資料儲存",
    databasePath: "資料庫路徑",
    timezone: "時區",
    storageHint: "資料儲存目前只保留本機資料庫路徑與系統時區設定。",
    notifications: "通知與警示",
    failedJobNotice: "任務失敗通知",
    missingRangeNotice: "缺失區間警示",
    usageNotice: "配額使用量警示",
    dailyReport: "每日彙總報告",
    consecutiveFails: "連續失敗次數 ≥",
    missingCandles: "缺失超過（根 K 線）",
    usageThreshold: "使用率閾值 ≥",
    perMinuteLimit: "通知頻率限制（分鐘）",
    channels: "通知管道：",
    systemNotification: "系統內通知",
    email: "Email",
    preferences: "介面偏好",
    languageLabel: "語言（Language）",
    theme: "主題（Theme）",
    lightTheme: "淺色（Light）",
    security: "安全與環境",
    runtime: "運行環境",
    backendUrl: "後端 API URL",
    apiKey: "API Key",
    lastCheck: "上次檢查",
    envLoaded: "環境變數載入",
    envFile: ".env 檔案",
    loaded: "已載入",
    found: "已找到",
    normal: "正常",
    local: "Local",
    checkedAt: "2026-06-19 10:15:23"
  },
  "en-US": {
    subtitle: "Provider, market assets, and system preferences.",
    save: "Save Settings",
    reset: "Reset",
    dataSource: "Data Source",
    provider: "Provider",
    apiBaseUrl: "API Base URL",
    connected: "Connected",
    testConnection: "Test connection",
    timeout: "Request Timeout (sec)",
    rateLimit: "Rate Limit (weight/min)",
    retries: "Retries",
    cooldown: "Cooldown (ms)",
    supportedMarkets: "Asset Management",
    marketManagementHint: "Manage markets and trading pairs that can be fetched.",
    addMarket: "Add Market",
    addMarketTitle: "Add Market",
    addModeProvider: "Binance Search",
    addModeManual: "Manual Input",
    basicMarketInfo: "Basic Info",
    marketPair: "Trading Pair",
    baseAsset: "Base Asset",
    marketSearch: "Binance Market",
    marketSearchPlaceholder: "Select or search BTC, DOGE, USDT",
    statusOptions: "Status",
    saveMarket: "Create Market",
    cancel: "Cancel",
    preview: "Preview",
    searchAsset: "Search markets",
    providerFilter: "Provider",
    onlyEnabled: "Enabled only",
    asset: "Market",
    sourceMarket: "Exchange Symbol",
    marketType: "Market Type",
    quoteCurrency: "Quote",
    defaultMarket: "Default",
    actions: "Actions",
    spot: "Spot",
    status: "Status",
    enabled: "Enabled",
    storage: "Data Storage",
    databasePath: "Database Path",
    timezone: "Timezone",
    storageHint: "Data storage currently keeps only the local database path and system timezone settings.",
    notifications: "Notifications",
    failedJobNotice: "Failed job notice",
    missingRangeNotice: "Missing range alert",
    usageNotice: "Quota usage alert",
    dailyReport: "Daily digest",
    consecutiveFails: "Consecutive failures ≥",
    missingCandles: "Missing candles over",
    usageThreshold: "Usage threshold ≥",
    perMinuteLimit: "Frequency limit (min)",
    channels: "Channels:",
    systemNotification: "In-app",
    email: "Email",
    preferences: "Interface Preferences",
    languageLabel: "Language",
    theme: "Theme",
    lightTheme: "Light",
    security: "Security & Environment",
    runtime: "Runtime",
    backendUrl: "Backend API URL",
    apiKey: "API Key",
    lastCheck: "Last Check",
    envLoaded: "Environment Variables",
    envFile: ".env File",
    loaded: "Loaded",
    found: "Found",
    normal: "Normal",
    local: "Local",
    checkedAt: "2026-06-19 10:15:23"
  }
} as const;

type MarketEntryMode = "provider" | "manual";

type DatabaseResetOption = {
  scope: DatabaseResetScope;
  title: string;
  description: string;
  buttonLabel: string;
};

type MarketFormValues = {
  provider?: string;
  marketType?: "spot";
  baseAsset?: string;
  quoteCurrency?: string;
  marketPair?: string;
  sourceMarket?: string;
  enabled?: boolean;
  isDefault?: boolean;
};

type DataSourceFormValues = {
  provider?: MarketDataProviderName;
  apiBaseUrl?: string;
  timeout?: number;
  rateLimit?: number;
  retries?: number;
  cooldown?: number;
};

type StorageFormValues = {
  databasePath?: string;
  timezone?: string;
};

type PreferenceFormValues = {
  language?: Language;
  theme?: InterfaceTheme;
};

type NotificationFormValues = {
  failedJobEnabled?: boolean;
  failedJobConsecutiveThreshold?: number;
  failedJobPerMinuteLimit?: number;
  missingRangeEnabled?: boolean;
  missingCandlesThreshold?: number;
  missingRangePerMinuteLimit?: number;
  usageEnabled?: boolean;
  usageThresholdPercent?: number;
  usagePerMinuteLimit?: number;
  dailyReportEnabled?: boolean;
  channels?: NotificationChannel[];
};

type ApiKeyFormValues = {
  name?: string;
  scopes?: ApiKeyScope[];
};

const marketFormInitialValues = {
  provider: DEFAULT_MARKET_DATA_PROVIDER,
  marketType: "spot",
  baseAsset: "BTC",
  quoteCurrency: "USDT",
  marketPair: "BTC/USDT",
  sourceMarket: "BTCUSDT",
  isDefault: false,
  enabled: true
};

const dataSourceInitialValues = {
  provider: DEFAULT_MARKET_DATA_PROVIDER,
  apiBaseUrl: "https://api.binance.com",
  timeout: 10,
  rateLimit: 1200,
  retries: 3,
  cooldown: 200
};

const storageInitialValues = {
  databasePath: "./data/tradebridge.db",
  timezone: "Asia/Taipei"
};

const preferenceInitialValues: Required<PreferenceFormValues> = {
  language: "zh-TW",
  theme: "light"
};

const notificationInitialValues: Required<NotificationFormValues> = {
  failedJobEnabled: true,
  failedJobConsecutiveThreshold: 3,
  failedJobPerMinuteLimit: 60,
  missingRangeEnabled: true,
  missingCandlesThreshold: 200,
  missingRangePerMinuteLimit: 60,
  usageEnabled: true,
  usageThresholdPercent: 80,
  usagePerMinuteLimit: 30,
  dailyReportEnabled: false,
  channels: ["system"]
};

function normalizeAssetSymbol(value: unknown, fallback: string) {
  const symbol = String(value ?? "").trim().toUpperCase();
  return symbol || fallback;
}

function getBaseAsset(asset: string) {
  return asset.split("/")[0].toLowerCase();
}

function formatProvider(provider: string) {
  return MARKET_DATA_PROVIDER_LABELS[provider as MarketDataProviderName] ?? provider;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function SectionTitle({ icon, title, hint }: { icon: ReactNode; title: string; hint?: string }) {
  return (
    <span className="settings-section-title">
      {icon}
      {title}
      {hint ? (
        <Tooltip title={hint} trigger={["hover", "focus", "click"]}>
          <Button
            aria-label={hint}
            className="settings-title-help"
            icon={<QuestionCircleOutlined />}
            size="small"
            type="text"
          />
        </Tooltip>
      ) : null}
    </span>
  );
}

export function SettingsPage({ messages, language, onLanguageChange }: SettingsPageProps) {
  const t = copy[language];
  const [messageApi, contextHolder] = message.useMessage();
  const [isMarketDrawerOpen, setIsMarketDrawerOpen] = useState(false);
  const [marketEntryMode, setMarketEntryMode] = useState<MarketEntryMode>("provider");
  const [selectedProvider, setSelectedProvider] = useState<MarketDataProviderName>(DEFAULT_MARKET_DATA_PROVIDER);
  const [enabledOnly, setEnabledOnly] = useState(true);
  const [assetSearch, setAssetSearch] = useState("");
  const [markets, setMarkets] = useState<MarketResponse[]>([]);
  const [providerMarketOptions, setProviderMarketOptions] = useState<ProviderMarketResponse[]>([]);
  const [providerMarketSearch, setProviderMarketSearch] = useState("");
  const [selectedProviderMarket, setSelectedProviderMarket] = useState<ProviderMarketResponse | null>(null);
  const [isProviderMarketLoading, setIsProviderMarketLoading] = useState(false);
  const [editingMarket, setEditingMarket] = useState<MarketResponse | null>(null);
  const [dataSourceStatus, setDataSourceStatus] = useState<ProviderDataSourceResponse | null>(null);
  const [storageSettings, setStorageSettings] = useState<StorageSettingsResponse | null>(null);
  const [isDataSourceLoading, setIsDataSourceLoading] = useState(false);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [isSavingDataSource, setIsSavingDataSource] = useState(false);
  const [isStorageLoading, setIsStorageLoading] = useState(false);
  const [isSavingStorage, setIsSavingStorage] = useState(false);
  const [databaseResetScope, setDatabaseResetScope] = useState<DatabaseResetScope | null>(null);
  const [databaseResetConfirmText, setDatabaseResetConfirmText] = useState("");
  const [databaseResetCreateBackup, setDatabaseResetCreateBackup] = useState(true);
  const [isResettingDatabase, setIsResettingDatabase] = useState(false);
  const [isPreferenceLoading, setIsPreferenceLoading] = useState(false);
  const [isSavingPreference, setIsSavingPreference] = useState(false);
  const [isNotificationLoading, setIsNotificationLoading] = useState(false);
  const [isSavingNotification, setIsSavingNotification] = useState(false);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusResponse | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKeyResponse[]>([]);
  const [isSecurityLoading, setIsSecurityLoading] = useState(false);
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState(false);
  const [isCreatingApiKey, setIsCreatingApiKey] = useState(false);
  const [createdApiKey, setCreatedApiKey] = useState<string | null>(null);
  const [mutatingApiKeyIds, setMutatingApiKeyIds] = useState<Set<string>>(() => new Set());
  const [savingMarket, setSavingMarket] = useState(false);
  const [mutatingMarketIds, setMutatingMarketIds] = useState<Set<string>>(() => new Set());
  const [dataSourceForm] = Form.useForm();
  const [storageForm] = Form.useForm();
  const [preferenceForm] = Form.useForm<PreferenceFormValues>();
  const [notificationForm] = Form.useForm();
  const [apiKeyForm] = Form.useForm<ApiKeyFormValues>();
  const [marketForm] = Form.useForm();
  const providerOptions = useMemo(
    () => [{ value: DEFAULT_MARKET_DATA_PROVIDER, label: MARKET_DATA_PROVIDER_LABELS[DEFAULT_MARKET_DATA_PROVIDER] }],
    []
  );
  const timezoneOptions = useMemo(
    () => [
      { value: "Asia/Taipei", label: "Asia/Taipei" },
      { value: "UTC", label: "UTC" }
    ],
    []
  );
  const databaseResetOptions = useMemo<DatabaseResetOption[]>(
    () =>
      language === "zh-TW"
        ? [
            {
              scope: "market_data",
              title: "清除市場資料",
              description: "刪除所有已儲存 K 線資料，保留設定、資產、排程與 API Key。",
              buttonLabel: "清除市場資料"
            },
            {
              scope: "job_history",
              title: "清除任務紀錄",
              description: "刪除抓取任務執行紀錄，保留市場資料、排程與設定。",
              buttonLabel: "清除任務紀錄"
            },
            {
              scope: "all",
              title: "重置全部資料庫",
              description: "刪除市場資料、任務、排程、資產設定、API Key 與偏好設定，並回到系統預設值。",
              buttonLabel: "重置全部"
            }
          ]
        : [
            {
              scope: "market_data",
              title: "Clear Market Data",
              description: "Delete stored candles while keeping settings, assets, schedules, and API keys.",
              buttonLabel: "Clear Market Data"
            },
            {
              scope: "job_history",
              title: "Clear Job History",
              description: "Delete fetch job execution history while keeping market data, schedules, and settings.",
              buttonLabel: "Clear Job History"
            },
            {
              scope: "all",
              title: "Reset Entire Database",
              description: "Delete market data, jobs, schedules, assets, API keys, and preferences, then restore defaults.",
              buttonLabel: "Reset All"
            }
          ],
    [language]
  );
  const notificationChannelOptions = useMemo(
    () => [
      { value: "system", label: t.systemNotification },
      { value: "email", label: t.email }
    ],
    [t.email, t.systemNotification]
  );
  const apiKeyScopeOptions = useMemo(
    () => [
      {
        value: "market_data:read" as const,
        label: language === "zh-TW" ? "市場資料讀取" : "Market data read"
      }
    ],
    [language]
  );
  const filteredMarkets = useMemo(() => {
    const keyword = assetSearch.trim().toUpperCase();
    if (!keyword) {
      return markets;
    }
    return markets.filter((market) =>
      [
        market.market_pair,
        market.exchange_symbol,
        market.base_asset,
        market.quote_asset,
        formatProvider(market.provider)
      ].some((value) => value.toUpperCase().includes(keyword))
    );
  }, [assetSearch, markets]);
  const providerMarketSelectOptions = useMemo(() => {
    const options = selectedProviderMarket
      ? [
          selectedProviderMarket,
          ...providerMarketOptions.filter(
            (market) => market.exchange_symbol !== selectedProviderMarket.exchange_symbol
          )
        ]
      : providerMarketOptions;
    return options.map((market) => ({
      value: market.exchange_symbol,
      label: `${market.market_pair} · ${market.exchange_symbol}`,
      searchText: `${market.market_pair} ${market.exchange_symbol} ${market.base_asset} ${market.quote_asset}`
    }));
  }, [providerMarketOptions, selectedProviderMarket]);
  const watchedBaseAsset = Form.useWatch("baseAsset", marketForm);
  const watchedQuoteCurrency = Form.useWatch("quoteCurrency", marketForm);
  const watchedSourceMarket = Form.useWatch("sourceMarket", marketForm);
  const previewBaseAsset =
    marketEntryMode === "provider"
      ? selectedProviderMarket?.base_asset ?? marketFormInitialValues.baseAsset
      : normalizeAssetSymbol(watchedBaseAsset, marketFormInitialValues.baseAsset);
  const previewQuoteCurrency =
    marketEntryMode === "provider"
      ? selectedProviderMarket?.quote_asset ?? marketFormInitialValues.quoteCurrency
      : normalizeAssetSymbol(watchedQuoteCurrency, marketFormInitialValues.quoteCurrency);
  const previewProvider = Form.useWatch("provider", marketForm) ?? marketFormInitialValues.provider;
  const previewMarketType = Form.useWatch("marketType", marketForm) ?? marketFormInitialValues.marketType;
  const previewSourceMarket =
    marketEntryMode === "provider"
      ? selectedProviderMarket?.exchange_symbol ?? marketFormInitialValues.sourceMarket
      : normalizeAssetSymbol(watchedSourceMarket, marketFormInitialValues.sourceMarket);
  const previewMarketPair =
    marketEntryMode === "provider"
      ? selectedProviderMarket?.market_pair ?? marketFormInitialValues.marketPair
      : `${previewBaseAsset || "BTC"}/${previewQuoteCurrency || "USDT"}`;
  const dataSourceTagColor = dataSourceStatus ? (dataSourceStatus.healthy ? "green" : "red") : "default";
  const dataSourceTagText = dataSourceStatus
    ? dataSourceStatus.healthy
      ? t.connected
      : language === "zh-TW"
        ? "未連線"
        : "Disconnected"
    : "--";
  const runtimeTagColor = runtimeStatus ? (runtimeStatus.status === "ok" ? "green" : "red") : "default";
  const runtimeApiUrl = runtimeStatus ? `${runtimeStatus.backend_url}${runtimeStatus.api_prefix}` : "--";
  const apiKeySummaryText = runtimeStatus
    ? runtimeStatus.api_key_count > 0
      ? language === "zh-TW"
        ? `${runtimeStatus.api_key_count} 組`
        : `${runtimeStatus.api_key_count} keys`
      : language === "zh-TW"
        ? "未建立"
        : "Not created"
    : "--";
  const apiKeySummaryColor = runtimeStatus?.api_key_configured ? "green" : "default";
  const envLoadedColor = runtimeStatus?.env_loaded ? "green" : "default";
  const envFileColor = runtimeStatus?.env_file_found ? "green" : "default";
  const selectedDatabaseResetOption =
    databaseResetOptions.find((option) => option.scope === databaseResetScope) ?? null;
  const isDatabaseResetConfirmDisabled =
    isResettingDatabase || (databaseResetScope === "all" && databaseResetConfirmText.trim() !== "RESET");

  const applyDataSourceValues = useCallback(
    (response: ProviderDataSourceResponse) => {
      setDataSourceStatus(response);
      setSelectedProvider(response.provider as MarketDataProviderName);
      dataSourceForm.setFieldsValue({
        provider: response.provider,
        apiBaseUrl: response.api_base_url,
        timeout: response.timeout_seconds,
        rateLimit: response.rate_limit_weight_per_minute,
        retries: response.retry_attempts,
        cooldown: response.cooldown_ms
      });
    },
    [dataSourceForm]
  );

  const buildDataSourceRequest = useCallback(
    (values: DataSourceFormValues): ProviderDataSourceUpdateRequest => ({
      provider: (values.provider ?? selectedProvider) as MarketDataProviderName,
      market_type: "spot",
      api_base_url: values.apiBaseUrl?.trim() || dataSourceInitialValues.apiBaseUrl,
      timeout_seconds: Number(values.timeout ?? dataSourceInitialValues.timeout),
      rate_limit_weight_per_minute: Number(values.rateLimit ?? dataSourceInitialValues.rateLimit),
      retry_attempts: Number(values.retries ?? dataSourceInitialValues.retries),
      cooldown_ms: Number(values.cooldown ?? dataSourceInitialValues.cooldown)
    }),
    [selectedProvider]
  );

  const loadDataSource = useCallback(async () => {
    setIsDataSourceLoading(true);
    try {
      applyDataSourceValues(await getProviderDataSource(selectedProvider));
    } catch (error) {
      console.error(error);
      setDataSourceStatus(null);
      void messageApi.error(language === "zh-TW" ? "資料來源設定讀取失敗" : "Failed to load data source settings");
    } finally {
      setIsDataSourceLoading(false);
    }
  }, [applyDataSourceValues, language, messageApi, selectedProvider]);

  const handleDataSourceFormFinish = async (values: DataSourceFormValues) => {
    setIsSavingDataSource(true);
    try {
      const response = await updateProviderDataSource(buildDataSourceRequest(values));
      applyDataSourceValues(response);
      void messageApi.success(language === "zh-TW" ? "資料來源已儲存" : "Data source settings saved");
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "資料來源儲存失敗" : "Failed to save data source settings");
    } finally {
      setIsSavingDataSource(false);
    }
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    try {
      const values = await dataSourceForm.validateFields();
      const response = await testProviderDataSource(buildDataSourceRequest(values));
      applyDataSourceValues(response);
      if (response.healthy) {
        void messageApi.success(language === "zh-TW" ? "資料來源連線正常" : "Data source connection is healthy");
      } else {
        void messageApi.warning(language === "zh-TW" ? "資料來源目前無法連線" : "Data source is not reachable");
      }
    } catch (error) {
      console.error(error);
      setDataSourceStatus((current) => (current ? { ...current, healthy: false } : current));
      void messageApi.error(language === "zh-TW" ? "測試連線失敗" : "Connection test failed");
    } finally {
      setIsTestingConnection(false);
    }
  };

  useEffect(() => {
    void loadDataSource();
  }, [loadDataSource]);

  const applyStorageValues = useCallback(
    (response: StorageSettingsResponse) => {
      setStorageSettings(response);
      storageForm.setFieldsValue({
        databasePath: response.database_path,
        timezone: response.timezone
      });
    },
    [storageForm]
  );

  const loadStorageSettings = useCallback(async () => {
    setIsStorageLoading(true);
    try {
      applyStorageValues(await getStorageSettings());
    } catch (error) {
      console.error(error);
      setStorageSettings(null);
      void messageApi.error(language === "zh-TW" ? "資料儲存設定讀取失敗" : "Failed to load storage settings");
    } finally {
      setIsStorageLoading(false);
    }
  }, [applyStorageValues, language, messageApi]);

  const handleStorageFormFinish = async (values: StorageFormValues) => {
    setIsSavingStorage(true);
    try {
      const response = await updateStorageSettings({
        timezone: values.timezone ?? storageInitialValues.timezone
      });
      applyStorageValues(response);
      void messageApi.success(language === "zh-TW" ? "資料儲存設定已儲存" : "Storage settings saved");
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "資料儲存設定儲存失敗" : "Failed to save storage settings");
    } finally {
      setIsSavingStorage(false);
    }
  };

  useEffect(() => {
    void loadStorageSettings();
  }, [loadStorageSettings]);

  const applyInterfacePreferenceValues = useCallback(
    (response: InterfacePreferencesResponse) => {
      preferenceForm.setFieldsValue({
        language: response.language as Language,
        theme: response.theme
      });
      if (response.language !== language) {
        onLanguageChange(response.language as Language);
      }
    },
    [language, onLanguageChange, preferenceForm]
  );

  const buildInterfacePreferenceRequest = useCallback(
    (values: PreferenceFormValues): InterfacePreferencesUpdateRequest => ({
      language: values.language ?? language,
      theme: values.theme ?? preferenceInitialValues.theme
    }),
    [language]
  );

  const loadInterfacePreferences = useCallback(async () => {
    setIsPreferenceLoading(true);
    try {
      applyInterfacePreferenceValues(await getInterfacePreferences());
    } catch (error) {
      console.error(error);
      preferenceForm.setFieldsValue({
        language,
        theme: preferenceInitialValues.theme
      });
      void messageApi.error(language === "zh-TW" ? "介面偏好設定讀取失敗" : "Failed to load interface preferences");
    } finally {
      setIsPreferenceLoading(false);
    }
  }, [applyInterfacePreferenceValues, language, messageApi, preferenceForm]);

  const handleInterfacePreferenceFormFinish = async (values: PreferenceFormValues) => {
    setIsSavingPreference(true);
    try {
      const response = await updateInterfacePreferences(buildInterfacePreferenceRequest(values));
      applyInterfacePreferenceValues(response);
      void messageApi.success(language === "zh-TW" ? "介面偏好已儲存" : "Interface preferences saved");
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "介面偏好儲存失敗" : "Failed to save interface preferences");
    } finally {
      setIsSavingPreference(false);
    }
  };

  useEffect(() => {
    void loadInterfacePreferences();
  }, [loadInterfacePreferences]);

  useEffect(() => {
    preferenceForm.setFieldsValue({ language });
  }, [language, preferenceForm]);

  const applyNotificationValues = useCallback(
    (response: NotificationSettingsResponse) => {
      notificationForm.setFieldsValue({
        failedJobEnabled: response.failed_job_enabled,
        failedJobConsecutiveThreshold: response.failed_job_consecutive_threshold,
        failedJobPerMinuteLimit: response.failed_job_per_minute_limit,
        missingRangeEnabled: response.missing_range_enabled,
        missingCandlesThreshold: response.missing_candles_threshold,
        missingRangePerMinuteLimit: response.missing_range_per_minute_limit,
        usageEnabled: response.usage_enabled,
        usageThresholdPercent: response.usage_threshold_percent,
        usagePerMinuteLimit: response.usage_per_minute_limit,
        dailyReportEnabled: response.daily_report_enabled,
        channels: response.channels.length > 0 ? response.channels : notificationInitialValues.channels
      });
    },
    [notificationForm]
  );

  const buildNotificationRequest = useCallback(
    (values: NotificationFormValues): NotificationSettingsUpdateRequest => {
      const channels = values.channels?.length ? values.channels : notificationInitialValues.channels;
      return {
        failed_job_enabled: values.failedJobEnabled ?? notificationInitialValues.failedJobEnabled,
        failed_job_consecutive_threshold: Number(
          values.failedJobConsecutiveThreshold ?? notificationInitialValues.failedJobConsecutiveThreshold
        ),
        failed_job_per_minute_limit: Number(
          values.failedJobPerMinuteLimit ?? notificationInitialValues.failedJobPerMinuteLimit
        ),
        missing_range_enabled: values.missingRangeEnabled ?? notificationInitialValues.missingRangeEnabled,
        missing_candles_threshold: Number(
          values.missingCandlesThreshold ?? notificationInitialValues.missingCandlesThreshold
        ),
        missing_range_per_minute_limit: Number(
          values.missingRangePerMinuteLimit ?? notificationInitialValues.missingRangePerMinuteLimit
        ),
        usage_enabled: values.usageEnabled ?? notificationInitialValues.usageEnabled,
        usage_threshold_percent: Number(values.usageThresholdPercent ?? notificationInitialValues.usageThresholdPercent),
        usage_per_minute_limit: Number(values.usagePerMinuteLimit ?? notificationInitialValues.usagePerMinuteLimit),
        daily_report_enabled: values.dailyReportEnabled ?? notificationInitialValues.dailyReportEnabled,
        channels
      };
    },
    []
  );

  const loadNotificationSettings = useCallback(async () => {
    setIsNotificationLoading(true);
    try {
      applyNotificationValues(await getNotificationSettings());
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "通知與警示設定讀取失敗" : "Failed to load notification settings");
    } finally {
      setIsNotificationLoading(false);
    }
  }, [applyNotificationValues, language, messageApi]);

  const handleNotificationFormFinish = async (values: NotificationFormValues) => {
    setIsSavingNotification(true);
    try {
      const response = await updateNotificationSettings(buildNotificationRequest(values));
      applyNotificationValues(response);
      void messageApi.success(language === "zh-TW" ? "通知與警示設定已儲存" : "Notification settings saved");
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "通知與警示設定儲存失敗" : "Failed to save notification settings");
    } finally {
      setIsSavingNotification(false);
    }
  };

  useEffect(() => {
    void loadNotificationSettings();
  }, [loadNotificationSettings]);

  const loadSecurityStatus = useCallback(async () => {
    setIsSecurityLoading(true);
    try {
      const [runtimeResponse, apiKeyResponse] = await Promise.all([getRuntimeStatus(), listApiKeys()]);
      setRuntimeStatus(runtimeResponse);
      setApiKeys(apiKeyResponse.api_keys);
    } catch (error) {
      console.error(error);
      setRuntimeStatus(null);
      setApiKeys([]);
      void messageApi.error(language === "zh-TW" ? "安全與環境狀態讀取失敗" : "Failed to load security status");
    } finally {
      setIsSecurityLoading(false);
    }
  }, [language, messageApi]);

  useEffect(() => {
    void loadSecurityStatus();
  }, [loadSecurityStatus]);

  const openApiKeyModal = () => {
    setCreatedApiKey(null);
    apiKeyForm.resetFields();
    apiKeyForm.setFieldsValue({
      name: "External consumer",
      scopes: ["market_data:read"]
    });
    setIsApiKeyModalOpen(true);
  };

  const closeApiKeyModal = () => {
    setIsApiKeyModalOpen(false);
    setCreatedApiKey(null);
  };

  const handleCreateApiKey = async () => {
    let values: ApiKeyFormValues;
    try {
      values = await apiKeyForm.validateFields();
    } catch {
      return;
    }

    setIsCreatingApiKey(true);
    try {
      const response = await createApiKey({
        name: values.name?.trim() || "External consumer",
        scopes: values.scopes?.length ? values.scopes : ["market_data:read"]
      });
      setCreatedApiKey(response.api_key);
      await loadSecurityStatus();
      void messageApi.success(language === "zh-TW" ? "API Key 已建立" : "API key created");
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "API Key 建立失敗" : "Failed to create API key");
    } finally {
      setIsCreatingApiKey(false);
    }
  };

  const handleCopyApiKey = async () => {
    if (!createdApiKey) {
      return;
    }
    try {
      await navigator.clipboard.writeText(createdApiKey);
      void messageApi.success(language === "zh-TW" ? "API Key 已複製" : "API key copied");
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "複製失敗" : "Failed to copy API key");
    }
  };

  const setMutatingApiKey = (keyId: string, isMutating: boolean) => {
    setMutatingApiKeyIds((current) => {
      const next = new Set(current);
      if (isMutating) {
        next.add(keyId);
      } else {
        next.delete(keyId);
      }
      return next;
    });
  };

  const handleToggleApiKeyEnabled = async (apiKey: ApiKeyResponse, enabled: boolean) => {
    setMutatingApiKey(apiKey.id, true);
    try {
      await updateApiKey(apiKey.id, { enabled });
      await loadSecurityStatus();
      void messageApi.success(
        enabled
          ? language === "zh-TW"
            ? "API Key 已啟用"
            : "API key enabled"
          : language === "zh-TW"
            ? "API Key 已停用"
            : "API key disabled"
      );
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "API Key 狀態更新失敗" : "Failed to update API key");
    } finally {
      setMutatingApiKey(apiKey.id, false);
    }
  };

  const handleRevokeApiKey = async (apiKey: ApiKeyResponse) => {
    setMutatingApiKey(apiKey.id, true);
    try {
      await deleteApiKey(apiKey.id);
      await loadSecurityStatus();
      void messageApi.success(language === "zh-TW" ? "API Key 已撤銷" : "API key revoked");
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "API Key 撤銷失敗" : "Failed to revoke API key");
    } finally {
      setMutatingApiKey(apiKey.id, false);
    }
  };

  const loadMarkets = useCallback(async () => {
    try {
      const response = await listMarkets({
        provider: selectedProvider,
        enabled: enabledOnly ? true : undefined,
        limit: 200
      });
      setMarkets(response.markets);
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "資產管理資料讀取失敗" : "Failed to load asset management data");
    }
  }, [enabledOnly, language, messageApi, selectedProvider]);

  useEffect(() => {
    void loadMarkets();
  }, [loadMarkets]);

  const handleOpenDatabaseReset = (scope: DatabaseResetScope) => {
    setDatabaseResetScope(scope);
    setDatabaseResetConfirmText("");
    setDatabaseResetCreateBackup(true);
  };

  const handleCloseDatabaseReset = () => {
    if (isResettingDatabase) {
      return;
    }
    setDatabaseResetScope(null);
    setDatabaseResetConfirmText("");
  };

  const handleDatabaseResetConfirm = async () => {
    if (!databaseResetScope || !selectedDatabaseResetOption) {
      return;
    }
    setIsResettingDatabase(true);
    try {
      const response = await resetDatabase({
        scope: databaseResetScope,
        confirm: databaseResetScope === "all" ? "RESET" : "DELETE",
        create_backup: databaseResetCreateBackup
      });
      const deletedTotal = Object.values(response.deleted_counts).reduce((sum, value) => sum + value, 0);
      await Promise.allSettled([
        loadStorageSettings(),
        loadDataSource(),
        loadMarkets(),
        loadSecurityStatus(),
        loadNotificationSettings(),
        loadInterfacePreferences()
      ]);
      setDatabaseResetScope(null);
      setDatabaseResetConfirmText("");
      void messageApi.success(
        language === "zh-TW"
          ? `${selectedDatabaseResetOption.title}完成，已刪除 ${deletedTotal} 筆。`
          : `${selectedDatabaseResetOption.title} completed. Deleted ${deletedTotal} rows.`
      );
    } catch (error) {
      console.error(error);
      void messageApi.error(
        language === "zh-TW"
          ? "資料庫維護操作失敗，請確認沒有任務正在執行。"
          : "Database maintenance failed. Make sure no jobs are running."
      );
    } finally {
      setIsResettingDatabase(false);
    }
  };

  useEffect(() => {
    let ignore = false;
    const timeoutId = window.setTimeout(() => {
      async function loadProviderMarketOptions() {
        setIsProviderMarketLoading(true);
        try {
          const response = await listProviderMarkets({
            provider: selectedProvider,
            market_type: "spot",
            quote_asset: "USDT",
            search: providerMarketSearch.trim() || undefined,
            limit: 200
          });
          if (!ignore) {
            setProviderMarketOptions(response.markets);
            setSelectedProviderMarket((current) => current ?? response.markets[0] ?? null);
          }
        } catch (error) {
          console.error(error);
          if (!ignore) {
            void messageApi.error(language === "zh-TW" ? "幣安交易對讀取失敗" : "Failed to load Binance markets");
          }
        } finally {
          if (!ignore) {
            setIsProviderMarketLoading(false);
          }
        }
      }

      void loadProviderMarketOptions();
    }, 250);

    return () => {
      ignore = true;
      window.clearTimeout(timeoutId);
    };
  }, [language, messageApi, providerMarketSearch, selectedProvider]);

  const closeMarketDrawer = () => {
    setIsMarketDrawerOpen(false);
    setEditingMarket(null);
  };
  const applyProviderMarket = (market: ProviderMarketResponse) => {
    setSelectedProviderMarket(market);
    marketForm.setFieldsValue({
      provider: market.provider,
      marketType: market.market_type,
      baseAsset: market.base_asset,
      quoteCurrency: market.quote_asset,
      marketPair: market.market_pair,
      sourceMarket: market.exchange_symbol
    });
  };
  const openMarketDrawer = () => {
    setEditingMarket(null);
    setMarketEntryMode("provider");
    marketForm.resetFields();
    marketForm.setFieldsValue(marketFormInitialValues);
    const nextMarket = selectedProviderMarket ?? providerMarketOptions[0];
    if (nextMarket) {
      applyProviderMarket(nextMarket);
    }
    setIsMarketDrawerOpen(true);
  };
  const openEditMarketDrawer = (market: MarketResponse) => {
    setEditingMarket(market);
    setMarketEntryMode("manual");
    marketForm.setFieldsValue({
      provider: market.provider,
      marketType: market.market_type,
      baseAsset: market.base_asset,
      quoteCurrency: market.quote_asset,
      marketPair: market.market_pair,
      sourceMarket: market.exchange_symbol,
      enabled: market.enabled,
      isDefault: market.is_default
    });
    setIsMarketDrawerOpen(true);
  };
  const setMutatingMarket = (marketId: string, isMutating: boolean) => {
    setMutatingMarketIds((current) => {
      const next = new Set(current);
      if (isMutating) {
        next.add(marketId);
      } else {
        next.delete(marketId);
      }
      return next;
    });
  };
  const handleMarketFormFinish = async (values: MarketFormValues) => {
    const marketPair = values.marketPair?.trim();
    if (!marketPair) {
      void messageApi.error(language === "zh-TW" ? "請選擇或輸入交易對" : "Select or enter a market pair");
      return;
    }
    setSavingMarket(true);
    try {
      const request = {
        provider: (values.provider ?? selectedProvider) as MarketDataProviderName,
        market_type: values.marketType ?? "spot",
        market_pair: marketPair,
        enabled: values.enabled ?? true,
        is_default: values.isDefault ?? false
      };
      if (editingMarket) {
        await updateMarket(editingMarket.id, request);
      } else {
        await createMarket(request);
      }
      await loadMarkets();
      closeMarketDrawer();
      void messageApi.success(
        editingMarket
          ? language === "zh-TW"
            ? "幣種已更新"
            : "Market updated"
          : language === "zh-TW"
            ? "幣種已新增"
            : "Market created"
      );
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "幣種儲存失敗" : "Failed to save market");
    } finally {
      setSavingMarket(false);
    }
  };
  const handleToggleMarketEnabled = async (market: MarketResponse, enabled: boolean) => {
    setMutatingMarket(market.id, true);
    try {
      await updateMarket(market.id, { enabled });
      await loadMarkets();
      void messageApi.success(
        enabled
          ? language === "zh-TW"
            ? `${market.market_pair} 已啟用`
            : `${market.market_pair} enabled`
          : language === "zh-TW"
            ? `${market.market_pair} 已停用`
            : `${market.market_pair} disabled`
      );
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "啟用狀態更新失敗" : "Failed to update enabled status");
    } finally {
      setMutatingMarket(market.id, false);
    }
  };
  const handleDeleteMarket = async (market: MarketResponse) => {
    setMutatingMarket(market.id, true);
    try {
      await deleteMarket(market.id);
      await loadMarkets();
      void messageApi.success(
        language === "zh-TW" ? `${market.market_pair} 已刪除` : `${market.market_pair} deleted`
      );
    } catch (error) {
      console.error(error);
      void messageApi.error(language === "zh-TW" ? "幣種刪除失敗" : "Failed to delete market");
    } finally {
      setMutatingMarket(market.id, false);
    }
  };
  return (
    <main className="page-stack settings-page">
      {contextHolder}
      <div className="page-header settings-page-header">
        <div className="settings-page-title-block">
          <Typography.Title level={2}>{messages.settings.title}</Typography.Title>
        </div>
        <Typography.Text className="page-subtitle settings-page-subtitle">{t.subtitle}</Typography.Text>
      </div>

      <section className="settings-grid">
        <div style={{ gridColumn: "1 / -1" }}><CatalogPanel language={language} /></div>
        <div className="settings-main-stack">
          <Card
            title={<SectionTitle icon={<DatabaseOutlined />} title={t.dataSource} />}
            className="panel-card settings-card settings-data-source-card"
            variant="borderless"
          >
            <Form
              form={dataSourceForm}
              layout="vertical"
              className="settings-form-grid settings-source-form"
              initialValues={dataSourceInitialValues}
              onFinish={handleDataSourceFormFinish}
            >
              <Form.Item label={t.provider} name="provider" rules={[{ required: true }]}>
                <Select
                  loading={isDataSourceLoading || isSavingDataSource}
                  options={providerOptions}
                  onChange={(provider) => setSelectedProvider(provider)}
                />
              </Form.Item>
              <Form.Item
                label={t.apiBaseUrl}
                name="apiBaseUrl"
                className="settings-wide-field"
                rules={[{ required: true }, { type: "url" }]}
              >
                <Input disabled={isDataSourceLoading || isSavingDataSource} />
              </Form.Item>
              <Form.Item label={t.connected}>
                <Tag color={dataSourceTagColor} className="settings-status-tag">
                  <CheckCircleOutlined /> {dataSourceTagText}
                </Tag>
              </Form.Item>
              <Form.Item label={t.timeout} name="timeout" rules={[{ required: true }]}>
                <InputNumber min={1} max={60} disabled={isDataSourceLoading || isSavingDataSource} />
              </Form.Item>
              <Form.Item label={t.rateLimit} name="rateLimit" rules={[{ required: true }]}>
                <InputNumber min={1} disabled={isDataSourceLoading || isSavingDataSource} />
              </Form.Item>
              <Form.Item label={t.retries} name="retries" rules={[{ required: true }]}>
                <InputNumber min={0} max={10} disabled={isDataSourceLoading || isSavingDataSource} />
              </Form.Item>
              <Form.Item label={t.cooldown} name="cooldown" rules={[{ required: true }]}>
                <InputNumber min={0} disabled={isDataSourceLoading || isSavingDataSource} />
              </Form.Item>
              <div className="settings-source-actions">
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit" loading={isSavingDataSource}>
                  {language === "zh-TW" ? "儲存資料來源" : "Save Data Source"}
                </Button>
                <Button icon={<ThunderboltOutlined />} loading={isTestingConnection} onClick={handleTestConnection}>
                  {t.testConnection}
                </Button>
              </div>
            </Form>
          </Card>

          <Card
            className="panel-card settings-card settings-asset-card"
            variant="borderless"
            title={
              <div className="settings-card-heading">
                <SectionTitle icon={<SettingOutlined />} title={t.supportedMarkets} />
                <Typography.Text>{t.marketManagementHint}</Typography.Text>
              </div>
            }
          >
            <div className="settings-asset-toolbar">
              <Button type="primary" icon={<PlusOutlined />} onClick={openMarketDrawer}>
                {t.addMarket}
              </Button>
              <Input
                prefix={<SearchOutlined />}
                placeholder={t.searchAsset}
                allowClear
                value={assetSearch}
                onChange={(event) => setAssetSearch(event.target.value)}
              />
              <Select
                value={selectedProvider}
                options={providerOptions}
                aria-label={t.providerFilter}
                onChange={(provider) => setSelectedProvider(provider)}
              />
              <div className="settings-enabled-filter">
                <span>{t.onlyEnabled}</span>
                <Switch checked={enabledOnly} size="small" onChange={setEnabledOnly} />
              </div>
            </div>
            <div className="settings-market-table">
              <div className="settings-market-head">
                <span>{t.asset}</span>
                <span>{t.provider}</span>
                <span>{t.marketType}</span>
                <span>{t.sourceMarket}</span>
                <span>{t.quoteCurrency}</span>
                <span>{t.defaultMarket}</span>
                <span>{t.enabled}</span>
                <span>{t.actions}</span>
              </div>
              {filteredMarkets.length === 0 ? (
                <div className="settings-market-empty">
                  <Typography.Text type="secondary">
                    {language === "zh-TW" ? "目前沒有符合條件的幣種" : "No markets match the current filters"}
                  </Typography.Text>
                </div>
              ) : filteredMarkets.map((row) => (
                <div className="settings-market-row" key={row.id}>
                  <span className="asset-cell">
                    <span className={`asset-mark asset-mark-${getBaseAsset(row.market_pair)}`}>
                      {row.market_pair[0]}
                    </span>
                    <strong>{row.market_pair}</strong>
                  </span>
                  <span>{formatProvider(row.provider)}</span>
                  <Tag>{row.market_type === "spot" ? t.spot : row.market_type}</Tag>
                  <Tag>{row.exchange_symbol}</Tag>
                  <Tag color="blue">{row.quote_asset}</Tag>
                  {row.is_default ? <Tag color="gold" className="settings-market-default">{t.defaultMarket}</Tag> : <span className="muted-text">-</span>}
                  <Switch
                    checked={row.enabled}
                    disabled={mutatingMarketIds.has(row.id)}
                    loading={mutatingMarketIds.has(row.id)}
                    size="small"
                    onChange={(checked) => {
                      void handleToggleMarketEnabled(row, checked);
                    }}
                  />
                  <Space size={4} className="settings-row-actions">
                    <Button
                      aria-label={`${t.actions} ${row.market_pair}`}
                      disabled={mutatingMarketIds.has(row.id)}
                      icon={<EditOutlined />}
                      onClick={() => openEditMarketDrawer(row)}
                    />
                    <Popconfirm
                      title={language === "zh-TW" ? `刪除 ${row.market_pair}？` : `Delete ${row.market_pair}?`}
                      description={
                        language === "zh-TW"
                          ? "刪除後資料頁與任務頁就不會再把它列為可選幣種。"
                          : "After deletion, this market will no longer be selectable in Data or Jobs."
                      }
                      okText={language === "zh-TW" ? "刪除" : "Delete"}
                      cancelText={t.cancel}
                      okButtonProps={{ danger: true, loading: mutatingMarketIds.has(row.id) }}
                      onConfirm={() => {
                        void handleDeleteMarket(row);
                      }}
                    >
                      <Button
                        aria-label={`Delete ${row.market_pair}`}
                        disabled={mutatingMarketIds.has(row.id)}
                        icon={<DeleteOutlined />}
                        danger
                      />
                    </Popconfirm>
                  </Space>
                </div>
              ))}
            </div>
          </Card>

          <div className="settings-support-stack">
          <Card
            title={<SectionTitle icon={<ApiOutlined />} title={t.storage} hint={t.storageHint} />}
            className="panel-card settings-card settings-storage-card"
            variant="borderless"
          >
            <Form
              form={storageForm}
              layout="vertical"
              className="settings-form-grid settings-storage-form"
              initialValues={storageInitialValues}
              onFinish={handleStorageFormFinish}
            >
              <Form.Item label={t.databasePath} name="databasePath" className="settings-wide-field">
                <Input readOnly disabled={isStorageLoading || isSavingStorage} />
              </Form.Item>
              <Form.Item
                label={t.timezone}
                name="timezone"
                className="settings-storage-timezone-field"
                rules={[{ required: true }]}
              >
                <Select
                  disabled={isStorageLoading || isSavingStorage}
                  options={timezoneOptions}
                  showSearch
                />
              </Form.Item>
              <Form.Item label={t.status} className="settings-storage-status-field">
                <Tag
                  color={storageSettings?.database_exists ? "green" : "orange"}
                  className="settings-status-tag"
                >
                  <DatabaseOutlined />{" "}
                  {storageSettings?.database_exists
                    ? language === "zh-TW"
                      ? "已找到"
                      : "Found"
                    : language === "zh-TW"
                      ? "未建立"
                      : "Not found"}
                </Tag>
              </Form.Item>
              <div className="settings-card-actions settings-storage-actions">
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit" loading={isSavingStorage}>
                  {language === "zh-TW" ? "儲存資料儲存" : "Save Storage"}
                </Button>
              </div>
            </Form>
            <div className="settings-database-maintenance">
              <div className="settings-maintenance-heading">
                <Typography.Text strong>{language === "zh-TW" ? "資料維護" : "Data Maintenance"}</Typography.Text>
                <Typography.Paragraph type="secondary">
                  {language === "zh-TW"
                    ? "清除測試資料或回到初始狀態。操作前會再次確認。"
                    : "Clear test data or return the database to its initial state. Confirmation is required."}
                </Typography.Paragraph>
              </div>
              <div className="settings-maintenance-actions">
                {databaseResetOptions.map((option) => (
                  <div className="settings-maintenance-row" key={option.scope}>
                    <div className="settings-maintenance-copy">
                      <Typography.Text strong>{option.title}</Typography.Text>
                      <Typography.Text type="secondary">{option.description}</Typography.Text>
                    </div>
                    <Button
                      danger={option.scope === "all"}
                      icon={<DeleteOutlined />}
                      loading={isResettingDatabase && databaseResetScope === option.scope}
                      onClick={() => handleOpenDatabaseReset(option.scope)}
                    >
                      {option.buttonLabel}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card
            title={<SectionTitle icon={<DesktopOutlined />} title={t.preferences} />}
            className="panel-card settings-card settings-support-preferences-card"
            loading={isPreferenceLoading}
            variant="borderless"
          >
            <Form
              form={preferenceForm}
              layout="vertical"
              className="settings-form-grid settings-preference-grid"
              initialValues={preferenceInitialValues}
              onFinish={handleInterfacePreferenceFormFinish}
            >
              <Form.Item label={t.languageLabel} name="language" rules={[{ required: true }]}>
                <Select
                  disabled={isPreferenceLoading || isSavingPreference}
                  options={[
                    { label: "繁體中文", value: "zh-TW" },
                    { label: "English", value: "en-US" }
                  ]}
                />
              </Form.Item>
              <Form.Item label={t.theme} name="theme" rules={[{ required: true }]}>
                <Select
                  disabled={isPreferenceLoading || isSavingPreference}
                  options={[{ value: "light", label: t.lightTheme }]}
                />
              </Form.Item>
              <div className="settings-card-actions settings-preference-actions">
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit" loading={isSavingPreference}>
                  {language === "zh-TW" ? "儲存介面偏好" : "Save Preferences"}
                </Button>
              </div>
            </Form>
          </Card>
          </div>
        </div>

        <aside className="settings-side-stack">
          <Card
            title={<SectionTitle icon={<BellOutlined />} title={t.notifications} />}
            className="panel-card settings-card settings-notifications-card"
            variant="borderless"
            extra={<SettingOutlined />}
          >
            <Form
              form={notificationForm}
              layout="vertical"
              initialValues={notificationInitialValues}
              onFinish={handleNotificationFormFinish}
            >
              <div className="settings-notice-grid">
                <section className="settings-notice-item">
                  <div className="settings-toggle-line">
                    <span>{t.failedJobNotice}</span>
                    <Form.Item name="failedJobEnabled" valuePropName="checked" noStyle>
                      <Switch disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                  </div>
                  <div className="settings-notice-fields">
                    <Form.Item
                      label={t.consecutiveFails}
                      name="failedJobConsecutiveThreshold"
                      rules={[{ required: true }]}
                    >
                      <InputNumber min={1} max={100} disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                    <Form.Item label={t.perMinuteLimit} name="failedJobPerMinuteLimit" rules={[{ required: true }]}>
                      <InputNumber min={1} disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                  </div>
                </section>

                <section className="settings-notice-item">
                  <div className="settings-toggle-line">
                    <span>{t.missingRangeNotice}</span>
                    <Form.Item name="missingRangeEnabled" valuePropName="checked" noStyle>
                      <Switch disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                  </div>
                  <div className="settings-notice-fields">
                    <Form.Item label={t.missingCandles} name="missingCandlesThreshold" rules={[{ required: true }]}>
                      <InputNumber min={1} disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                    <Form.Item label={t.perMinuteLimit} name="missingRangePerMinuteLimit" rules={[{ required: true }]}>
                      <InputNumber min={1} disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                  </div>
                </section>

                <section className="settings-notice-item">
                  <div className="settings-toggle-line">
                    <span>{t.usageNotice}</span>
                    <Form.Item name="usageEnabled" valuePropName="checked" noStyle>
                      <Switch disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                  </div>
                  <div className="settings-notice-fields">
                    <Form.Item label={t.usageThreshold} name="usageThresholdPercent" rules={[{ required: true }]}>
                      <Space.Compact block>
                        <InputNumber min={1} max={100} disabled={isNotificationLoading || isSavingNotification} />
                        <Button disabled className="settings-unit-button">%</Button>
                      </Space.Compact>
                    </Form.Item>
                    <Form.Item label={t.perMinuteLimit} name="usagePerMinuteLimit" rules={[{ required: true }]}>
                      <InputNumber min={1} disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                  </div>
                </section>

                <section className="settings-notice-item settings-notice-item-compact">
                  <div className="settings-toggle-line">
                    <span>{t.dailyReport}</span>
                    <Form.Item name="dailyReportEnabled" valuePropName="checked" noStyle>
                      <Switch disabled={isNotificationLoading || isSavingNotification} />
                    </Form.Item>
                  </div>
                </section>
              </div>
              <div className="settings-channel-row settings-notice-footer">
                <div className="settings-channel-options">
                  <span>{t.channels}</span>
                  <Form.Item name="channels" noStyle>
                    <Checkbox.Group
                      disabled={isNotificationLoading || isSavingNotification}
                      options={notificationChannelOptions}
                    />
                  </Form.Item>
                </div>
                <div className="settings-card-actions settings-notice-actions">
                <Button type="primary" icon={<SaveOutlined />} htmlType="submit" loading={isSavingNotification}>
                  {language === "zh-TW" ? "儲存通知與警示" : "Save Notifications"}
                </Button>
                </div>
              </div>
            </Form>
          </Card>

          <Card
            title={<SectionTitle icon={<LockOutlined />} title={t.security} />}
            className="panel-card settings-card settings-security-card"
            loading={isSecurityLoading}
            variant="borderless"
          >
            <div className="settings-security-summary">
              <div>
                <span>{language === "zh-TW" ? "前端版本" : "Frontend version"}</span>
                <strong>v{__APP_VERSION__}</strong>
              </div>
              <div>
                <span>{language === "zh-TW" ? "後端版本" : "Backend version"}</span>
                <strong>{runtimeStatus?.version ? `v${runtimeStatus.version}` : language === "zh-TW" ? "無法取得" : "Unavailable"}</strong>
              </div>
              <div>
                <span>{t.runtime}</span>
                <Tag color={runtimeTagColor} className="settings-runtime-tag">
                  {runtimeStatus?.runtime ?? t.local}
                </Tag>
              </div>
              <div>
                <span>{t.backendUrl}</span>
                <strong>{runtimeApiUrl}</strong>
              </div>
              <div>
                <span>{t.apiKey}</span>
                <Tag color={apiKeySummaryColor}>{apiKeySummaryText}</Tag>
              </div>
              <div>
                <span>{t.status}</span>
                <Tag color={runtimeTagColor}>{runtimeStatus?.status ?? "--"}</Tag>
              </div>
              <div className="settings-security-wide">
                <span>{t.lastCheck}</span>
                <strong>{formatDateTime(runtimeStatus?.checked_at)}</strong>
              </div>
            </div>
            <div className="settings-env-row">
              <span>{t.envLoaded}</span>
              <Tag color={envLoadedColor}>
                {runtimeStatus?.env_loaded ? t.loaded : language === "zh-TW" ? "未載入" : "Not loaded"}
              </Tag>
              <span>{t.envFile}</span>
              <Tag color={envFileColor}>
                {runtimeStatus?.env_file_found ? t.found : language === "zh-TW" ? "未找到" : "Not found"}
              </Tag>
            </div>
            <div className="settings-api-key-header">
              <div>
                <strong>{language === "zh-TW" ? "外部 API Key" : "External API keys"}</strong>
                <span>
                  {language === "zh-TW"
                    ? "給其他應用讀取市場資料使用。"
                    : "For external apps that read market data."}
                </span>
              </div>
              <Button
                className="settings-api-key-primary-button"
                icon={<KeyOutlined />}
                type="primary"
                onClick={openApiKeyModal}
              >
                {language === "zh-TW" ? "產生 Key" : "Generate Key"}
              </Button>
            </div>
            <div className="settings-api-key-list">
              {apiKeys.length === 0 ? (
                <div className="settings-api-key-empty">
                  {language === "zh-TW" ? "尚未建立 API Key" : "No API keys yet"}
                </div>
              ) : (
                apiKeys.map((apiKey) => (
                  <div className="settings-api-key-row" key={apiKey.id}>
                    <div className="settings-api-key-main">
                      <strong>{apiKey.name}</strong>
                      <span>{apiKey.key_prefix}...</span>
                      <small>
                        {language === "zh-TW" ? "最後使用：" : "Last used: "}
                        {formatDateTime(apiKey.last_used_at)}
                      </small>
                    </div>
                    <div className="settings-api-key-meta">
                      <Tag color="blue">{apiKey.scopes.join(", ")}</Tag>
                      <Switch
                        checked={apiKey.enabled}
                        loading={mutatingApiKeyIds.has(apiKey.id)}
                        onChange={(checked) => void handleToggleApiKeyEnabled(apiKey, checked)}
                      />
                      <Popconfirm
                        title={language === "zh-TW" ? "撤銷這組 API Key？" : "Revoke this API key?"}
                        description={
                          language === "zh-TW"
                            ? "撤銷後，使用這組 Key 的外部應用會失去存取權。"
                            : "External apps using this key will lose access after it is revoked."
                        }
                        okText={language === "zh-TW" ? "撤銷" : "Revoke"}
                        cancelText={t.cancel}
                        okButtonProps={{ danger: true, loading: mutatingApiKeyIds.has(apiKey.id) }}
                        onConfirm={() => void handleRevokeApiKey(apiKey)}
                      >
                        <Button
                          danger
                          icon={<DeleteOutlined />}
                          loading={mutatingApiKeyIds.has(apiKey.id)}
                        />
                      </Popconfirm>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </aside>
      </section>
      <Modal
        destroyOnHidden
        footer={
          createdApiKey ? (
            <Button type="primary" onClick={closeApiKeyModal}>
              {language === "zh-TW" ? "完成" : "Done"}
            </Button>
          ) : (
            <>
              <Button onClick={closeApiKeyModal}>{t.cancel}</Button>
              <Button
                className="settings-api-key-primary-button"
                type="primary"
                icon={<KeyOutlined />}
                loading={isCreatingApiKey}
                onClick={handleCreateApiKey}
              >
                {language === "zh-TW" ? "產生 Key" : "Generate Key"}
              </Button>
            </>
          )
        }
        onCancel={closeApiKeyModal}
        open={isApiKeyModalOpen}
        title={<SectionTitle icon={<KeyOutlined />} title={language === "zh-TW" ? "產生 API Key" : "Generate API Key"} />}
      >
        {createdApiKey ? (
          <div className="settings-api-key-created">
            <Alert
              message={language === "zh-TW" ? "請立即複製並保存" : "Copy and store it now"}
              description={
                language === "zh-TW"
                  ? "完整 API Key 只會顯示一次，關閉視窗後後端只保留雜湊值。"
                  : "The full API key is shown once. After closing, only its hash remains on the backend."
              }
              showIcon
              type="warning"
            />
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 5 }} readOnly value={createdApiKey} />
            <Button block icon={<CopyOutlined />} onClick={handleCopyApiKey}>
              {language === "zh-TW" ? "複製 API Key" : "Copy API Key"}
            </Button>
          </div>
        ) : (
          <Form form={apiKeyForm} layout="vertical">
            <Form.Item
              label={language === "zh-TW" ? "名稱" : "Name"}
              name="name"
              rules={[{ required: true, message: language === "zh-TW" ? "請輸入名稱" : "Enter a name" }]}
            >
              <Input maxLength={80} placeholder={language === "zh-TW" ? "例如：報表服務" : "Example: reporting service"} />
            </Form.Item>
            <Form.Item
              label={language === "zh-TW" ? "權限" : "Scopes"}
              name="scopes"
              rules={[{ required: true, message: language === "zh-TW" ? "請選擇權限" : "Select a scope" }]}
            >
              <Checkbox.Group options={apiKeyScopeOptions} />
            </Form.Item>
          </Form>
        )}
      </Modal>
      <Modal
        title={selectedDatabaseResetOption?.title}
        open={databaseResetScope !== null}
        okButtonProps={{
          danger: true,
          disabled: isDatabaseResetConfirmDisabled
        }}
        okText={language === "zh-TW" ? "確認執行" : "Confirm"}
        cancelText={t.cancel}
        confirmLoading={isResettingDatabase}
        onCancel={handleCloseDatabaseReset}
        onOk={() => {
          void handleDatabaseResetConfirm();
        }}
      >
        <Space className="settings-reset-modal" direction="vertical" size={16}>
          <Alert
            showIcon
            type="warning"
            message={selectedDatabaseResetOption?.title}
            description={selectedDatabaseResetOption?.description}
          />
          <Checkbox
            checked={databaseResetCreateBackup}
            disabled={isResettingDatabase}
            onChange={(event) => setDatabaseResetCreateBackup(event.target.checked)}
          >
            {language === "zh-TW" ? "執行前建立資料庫備份" : "Create a database backup before running"}
          </Checkbox>
          {databaseResetScope === "all" ? (
            <div className="settings-reset-confirm-input">
              <Typography.Text strong>{language === "zh-TW" ? "輸入 RESET 才能繼續" : "Type RESET to continue"}</Typography.Text>
              <Input
                autoComplete="off"
                disabled={isResettingDatabase}
                placeholder="RESET"
                value={databaseResetConfirmText}
                onChange={(event) => setDatabaseResetConfirmText(event.target.value)}
              />
            </div>
          ) : (
            <Typography.Text type="secondary">
              {language === "zh-TW"
                ? "按下確認後會立即刪除所選資料。"
                : "Selected data will be deleted immediately after confirmation."}
            </Typography.Text>
          )}
        </Space>
      </Modal>

      <Drawer
        className="settings-market-drawer"
        destroyOnHidden
        footer={
          <div className="settings-market-drawer-footer">
            <Button onClick={closeMarketDrawer}>{t.cancel}</Button>
            <Button
              type="primary"
              icon={editingMarket ? <SaveOutlined /> : <PlusOutlined />}
              loading={savingMarket}
              onClick={() => marketForm.submit()}
            >
              {editingMarket
                ? language === "zh-TW"
                  ? "儲存幣種"
                  : "Save Market"
                : t.saveMarket}
            </Button>
          </div>
        }
        onClose={closeMarketDrawer}
        open={isMarketDrawerOpen}
        title={
          <SectionTitle
            icon={editingMarket ? <EditOutlined /> : <PlusOutlined />}
            title={editingMarket ? (language === "zh-TW" ? "編輯幣種" : "Edit Market") : t.addMarketTitle}
          />
        }
        width={520}
      >
        <div className="settings-market-drawer-content">
          <Segmented
            block
            className="settings-market-mode-switch"
            onChange={(value) => {
              const nextMode = value as MarketEntryMode;
              setMarketEntryMode(nextMode);
              if (nextMode === "provider" && selectedProviderMarket) {
                applyProviderMarket(selectedProviderMarket);
              }
            }}
            options={[
              { label: t.addModeProvider, value: "provider" },
              { label: t.addModeManual, value: "manual" }
            ]}
            value={marketEntryMode}
          />

          <div className="settings-market-preview" aria-label={t.preview}>
            <span className={`asset-mark asset-mark-${String(previewBaseAsset).toLowerCase()}`}>
              {String(previewBaseAsset || "B")[0]}
            </span>
            <div className="settings-market-preview-main">
              <span>{t.preview}</span>
              <strong>{previewMarketPair}</strong>
              <div className="settings-market-preview-tags">
                <Tag>{formatProvider(String(previewProvider))}</Tag>
                <Tag color="blue">{previewMarketType === "spot" ? t.spot : previewMarketType}</Tag>
                <Tag>{previewSourceMarket}</Tag>
              </div>
            </div>
          </div>

          <Form
            className="settings-market-drawer-form"
            form={marketForm}
            initialValues={marketFormInitialValues}
            layout="vertical"
            onValuesChange={(changedValues: Partial<MarketFormValues>, values: MarketFormValues) => {
              if ("baseAsset" in changedValues || "quoteCurrency" in changedValues) {
                const baseAsset = normalizeAssetSymbol(values.baseAsset, "");
                const quoteCurrency = normalizeAssetSymbol(values.quoteCurrency, "");
                const nextMarketPair = baseAsset && quoteCurrency ? `${baseAsset}/${quoteCurrency}` : "";
                const nextSourceMarket = baseAsset && quoteCurrency ? `${baseAsset}${quoteCurrency}` : "";
                marketForm.setFieldsValue({
                  baseAsset,
                  quoteCurrency,
                  marketPair: nextMarketPair,
                  sourceMarket: nextSourceMarket
                });
              }
            }}
            onFinish={handleMarketFormFinish}
          >
            {marketEntryMode === "provider" ? (
              <section className="settings-market-form-card">
                <Form.Item hidden name="baseAsset">
                  <Input />
                </Form.Item>
                <Form.Item hidden name="quoteCurrency">
                  <Input />
                </Form.Item>
                <Form.Item hidden name="marketPair">
                  <Input />
                </Form.Item>
                <Form.Item hidden name="sourceMarket">
                  <Input />
                </Form.Item>
                <h3>{t.addModeProvider}</h3>
                <div className="settings-provider-search-grid">
                  <Form.Item label={t.provider} name="provider">
                    <Select options={providerOptions} />
                  </Form.Item>
                  <Form.Item label={t.marketType} name="marketType">
                    <Select options={[{ value: "spot", label: t.spot }]} />
                  </Form.Item>
                  <Form.Item className="settings-provider-market-select-field" label={t.marketSearch}>
                    <Select
                      showSearch
                      loading={isProviderMarketLoading}
                      optionFilterProp="searchText"
                      placeholder={t.marketSearchPlaceholder}
                      value={selectedProviderMarket?.exchange_symbol}
                      onSearch={setProviderMarketSearch}
                      onChange={(exchangeSymbol) => {
                        const nextMarket = [selectedProviderMarket, ...providerMarketOptions].find(
                          (market) => market?.exchange_symbol === exchangeSymbol
                        );
                        if (nextMarket) {
                          applyProviderMarket(nextMarket);
                        }
                      }}
                      options={providerMarketSelectOptions}
                    />
                  </Form.Item>
                </div>
              </section>
            ) : (
              <section className="settings-market-form-card">
                <h3>{t.basicMarketInfo}</h3>
                <div className="settings-market-form-grid">
                  <Form.Item label={t.provider} name="provider">
                    <Select options={providerOptions} />
                  </Form.Item>
                  <Form.Item label={t.marketType} name="marketType">
                    <Select options={[{ value: "spot", label: t.spot }]} />
                  </Form.Item>
                  <Form.Item label={t.baseAsset} name="baseAsset">
                    <Input autoComplete="off" placeholder="BTC" />
                  </Form.Item>
                  <Form.Item label={t.quoteCurrency} name="quoteCurrency">
                    <Input autoComplete="off" placeholder="USDT" />
                  </Form.Item>
                  <Form.Item className="settings-market-form-wide" label={t.marketPair} name="marketPair">
                    <Input />
                  </Form.Item>
                  <Form.Item className="settings-market-form-wide" label={t.sourceMarket} name="sourceMarket">
                    <Input />
                  </Form.Item>
                </div>
              </section>
            )}

            <section className="settings-market-form-card">
              <h3>{t.statusOptions}</h3>
              <div className="settings-market-state-row">
                <div className="settings-market-state-toggle">
                  <span>{t.enabled}</span>
                  <Form.Item name="enabled" valuePropName="checked" noStyle>
                    <Switch />
                  </Form.Item>
                </div>
                <div className="settings-market-state-toggle">
                  <span>{t.defaultMarket}</span>
                  <Form.Item name="isDefault" valuePropName="checked" noStyle>
                    <Switch />
                  </Form.Item>
                </div>
              </div>
            </section>
          </Form>
        </div>
      </Drawer>
    </main>
  );
}
