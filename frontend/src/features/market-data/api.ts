import { apiRequest, buildQueryString } from "../../shared/api/client";

type MarketDataRequestOptions = {
  signal?: AbortSignal;
};

export type MarketDataProviderName = "binance";

export const DEFAULT_MARKET_DATA_PROVIDER: MarketDataProviderName = "binance";

export const MARKET_DATA_PROVIDER_LABELS: Record<MarketDataProviderName, string> = {
  binance: "Binance"
};

export interface MarketResponse {
  id: string;
  enabled: boolean;
  provider: string;
  market_type: string;
  market_pair: string;
  exchange_symbol: string;
  base_asset: string;
  quote_asset: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface MarketsResponse {
  count: number;
  markets: MarketResponse[];
}

export interface ProviderStatusResponse {
  provider: string;
  market_type: string;
  healthy: boolean;
}

export interface ProviderDataSourceResponse {
  provider: string;
  market_type: string;
  api_base_url: string;
  timeout_seconds: number;
  rate_limit_weight_per_minute: number;
  retry_attempts: number;
  cooldown_ms: number;
  healthy: boolean;
}

export interface StorageSettingsResponse {
  database_path: string;
  timezone: string;
  database_exists: boolean;
  database_size_bytes: number;
  updated_at: string | null;
}

export interface StorageSettingsUpdateRequest {
  timezone: string;
}

export type DatabaseResetScope = "market_data" | "job_history" | "all";

export interface DatabaseResetRequest {
  scope: DatabaseResetScope;
  confirm: "DELETE" | "RESET";
  create_backup: boolean;
}

export interface DatabaseResetResponse {
  scope: DatabaseResetScope;
  deleted_counts: Record<string, number>;
  backup_path: string | null;
  database_size_bytes: number;
  executed_at: string;
}

export type InterfaceLanguage = "zh-TW" | "en-US";
export type InterfaceTheme = "light";

export interface InterfacePreferencesResponse {
  language: InterfaceLanguage;
  theme: InterfaceTheme;
  updated_at: string | null;
}

export type InterfacePreferencesUpdateRequest = Omit<InterfacePreferencesResponse, "updated_at">;

export type NotificationChannel = "system" | "email";

export interface NotificationSettingsResponse {
  failed_job_enabled: boolean;
  failed_job_consecutive_threshold: number;
  failed_job_per_minute_limit: number;
  missing_range_enabled: boolean;
  missing_candles_threshold: number;
  missing_range_per_minute_limit: number;
  usage_enabled: boolean;
  usage_threshold_percent: number;
  usage_per_minute_limit: number;
  daily_report_enabled: boolean;
  channels: NotificationChannel[];
  updated_at: string | null;
}

export type NotificationSettingsUpdateRequest = Omit<NotificationSettingsResponse, "updated_at">;

export type ApiKeyScope = "market_data:read";

export interface RuntimeStatusResponse {
  runtime: string;
  backend_url: string;
  api_prefix: string;
  status: string;
  environment: string;
  version: string;
  api_key_configured: boolean;
  api_key_count: number;
  env_loaded: boolean;
  env_file_found: boolean;
  checked_at: string;
}

export interface ApiKeyResponse {
  id: string;
  name: string;
  key_prefix: string;
  scopes: ApiKeyScope[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyListResponse {
  count: number;
  api_keys: ApiKeyResponse[];
}

export interface ApiKeyCreateRequest {
  name: string;
  scopes?: ApiKeyScope[];
}

export interface ApiKeyCreateResponse {
  api_key: string;
  record: ApiKeyResponse;
}

export interface ApiKeyUpdateRequest {
  name?: string;
  enabled?: boolean;
}

export interface ProviderDataSourceUpdateRequest {
  provider?: MarketDataProviderName;
  market_type?: "spot";
  api_base_url: string;
  timeout_seconds: number;
  rate_limit_weight_per_minute: number;
  retry_attempts: number;
  cooldown_ms: number;
}

export interface ProviderMarketResponse {
  provider: string;
  market_type: string;
  market_pair: string;
  exchange_symbol: string;
  base_asset: string;
  quote_asset: string;
  status: string;
}

export interface ProviderMarketsResponse {
  provider: string;
  market_type: string;
  quote_asset: string | null;
  search: string | null;
  count: number;
  markets: ProviderMarketResponse[];
}

export interface CandleListItemResponse {
  provider: string;
  market_type: string;
  market_pair: string;
  exchange_symbol: string;
  interval: string;
  open_time_ms: number;
  close_time_ms: number;
  open_time: string;
  close_time: string;
  open_price: string;
  high_price: string;
  low_price: string;
  close_price: string;
  base_volume: string;
  quote_volume: string;
  trade_count: number;
  taker_buy_base_volume: string;
  taker_buy_quote_volume: string;
  unused_value: string;
}

export interface CandleResponse extends CandleListItemResponse {
  raw_payload_json: string;
}

export interface CandleListResponse {
  count: number;
  candles: CandleListItemResponse[];
}

export interface CandleChartResponse {
  count: number;
  candles: CandleListItemResponse[];
}

export interface CandleCoverageResponse {
  provider: string;
  market_pair: string;
  exchange_symbol: string;
  interval: string;
  candle_count: number;
  first_open_time_ms: number | null;
  last_open_time_ms: number | null;
  first_open_time: string | null;
  last_open_time: string | null;
  last_fetched_at: string | null;
}

export interface MissingCandleRangeResponse {
  start_open_time_ms: number;
  end_open_time_ms: number;
  start_open_time: string;
  end_open_time: string;
  missing_count: number;
}

export interface CandleGapResponse {
  provider: string;
  market_pair: string;
  exchange_symbol: string;
  interval: string;
  checked_start_open_time_ms: number | null;
  checked_end_open_time_ms: number | null;
  checked_start_open_time: string | null;
  checked_end_open_time: string | null;
  missing_count: number;
  missing_ranges: MissingCandleRangeResponse[];
}

export interface DataGapResponse {
  id: string;
  provider: string;
  market_type: string;
  market_pair: string;
  exchange_symbol: string;
  interval: string;
  start_open_time_ms: number;
  end_open_time_ms: number;
  start_open_time: string;
  end_open_time: string;
  missing_count: number;
  status: "detected" | "repairing" | "resolved" | "official_empty" | "failed" | string;
  source_job_id: string | null;
  repair_job_id: string | null;
  reason: string | null;
  first_detected_at: string;
  last_checked_at: string;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataGapListResponse {
  count: number;
  gaps: DataGapResponse[];
}

export interface DataGapSummaryResponse {
  total_count: number;
  detected_count: number;
  repairing_count: number;
  resolved_count: number;
  official_empty_count: number;
  failed_count: number;
  active_missing_count: number;
  first_active_gap_start_time_ms: number | null;
  first_active_gap_start_time: string | null;
  last_checked_at: string | null;
}

export interface DataGapRepairRequest {
  batch_limit?: number;
  overlap_candles?: number;
  verify_continuity?: boolean;
  retry_attempts?: number;
  retry_delay_seconds?: number;
}

export interface DataGapRepairResponse {
  gap: DataGapResponse;
  job: CandleFetchJobResponse;
}

export interface CandleFetchPlanResponse {
  mode: string;
  provider: string;
  closed_only: boolean;
  overlap_candles: number;
  batch_limit: number;
  max_batches: number;
  verify_continuity: boolean;
  retry_attempts: number;
  retry_delay_seconds: number;
  interval_ms: number;
  expected_candle_count: number;
  batch_count: number;
  excluded_open_candle: boolean;
  requested_start_time_ms: number | null;
  requested_end_time_ms: number | null;
  effective_start_open_time_ms: number;
  effective_end_open_time_ms: number;
  effective_end_time_ms: number;
  requested_start_time: string | null;
  requested_end_time: string | null;
  effective_start_open_time: string;
  effective_end_open_time: string;
  effective_end_time: string;
}

export interface CandleFetchResponse {
  fetch_id: string;
  fetched_count: number;
  saved_count: number;
  is_complete: boolean;
  missing_count: number;
  missing_ranges: MissingCandleRangeResponse[];
  plan: CandleFetchPlanResponse;
  candles: CandleResponse[];
}

export interface CandleFetchJobResponse {
  id: string;
  job_type: string;
  status: "pending" | "running" | "pausing" | "paused" | "success" | "failed" | "cancelled";
  schedule_id: string | null;
  trigger_type: "manual" | "scheduled" | string;
  provider: string;
  market_type: string;
  market_pair: string;
  exchange_symbol: string;
  interval: string;
  mode: string;
  requested_start_time_ms: number;
  requested_end_time_ms: number | null;
  effective_start_time_ms: number | null;
  effective_end_time_ms: number;
  current_cursor_time_ms: number | null;
  requested_start_time: string | null;
  requested_end_time: string | null;
  effective_start_time: string | null;
  effective_end_time: string | null;
  current_cursor_time: string | null;
  batch_limit: number;
  overlap_candles: number;
  total_estimated_count: number;
  fetched_count: number;
  saved_count: number;
  failed_count: number;
  missing_count: number;
  completed_batch_count: number;
  total_batch_count: number;
  progress_percent: number;
  closed_only: boolean;
  verify_continuity: boolean;
  retry_attempts: number;
  retry_delay_seconds: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandleFetchJobListResponse {
  count: number;
  jobs: CandleFetchJobResponse[];
}

export interface CandleFetchJobSummaryResponse {
  total_count: number;
  running_count: number;
  queued_count: number;
  completed_today_count: number;
  failed_count: number;
  timezone: string;
  today_start_time_ms: number;
  today_end_time_ms: number;
  today_start_time: string | null;
  today_end_time: string | null;
}

export interface CandleFetchJobOverviewResponse {
  recent_jobs: CandleFetchJobResponse[];
  latest_failed_job: CandleFetchJobResponse | null;
  failed_count: number;
}

export interface DashboardMetricsResponse {
  tracked_market_count: number;
  stored_candle_count: number;
  latest_sync_at: string | null;
  latest_candle_time_ms: number | null;
  latest_candle_time: string | null;
  data_gap_count: number | null;
  data_gap_failed_count: number;
  data_gap_repairing_count: number;
  first_data_gap_time_ms: number | null;
  first_data_gap_time: string | null;
  gap_check_status: string;
}

export interface DashboardCoverageItemResponse {
  provider: string;
  market_type: string;
  market_pair: string;
  exchange_symbol: string;
  interval: string;
  candle_count: number;
  coverage_percent: number;
  first_open_time_ms: number | null;
  last_open_time_ms: number | null;
  first_open_time: string | null;
  last_open_time: string | null;
  last_fetched_at: string | null;
  missing_count: number | null;
  gap_check_status: string;
  health: "healthy" | "warning" | "error" | string;
}

export interface DashboardProviderStatusResponse {
  provider: string;
  market_type: string;
  healthy: boolean;
  checked_at: string;
  latency_ms: number | null;
  request_quota_percent: number | null;
  error_rate_percent: number | null;
  last_successful_response: string | null;
  error_message: string | null;
}

export interface DashboardOverviewResponse {
  provider: string;
  interval: string;
  generated_at: string;
  metrics: DashboardMetricsResponse;
  coverage: DashboardCoverageItemResponse[];
  provider_status: DashboardProviderStatusResponse;
  job_summary: CandleFetchJobSummaryResponse;
  recent_jobs: CandleFetchJobResponse[];
  latest_failed_job: CandleFetchJobResponse | null;
}

export interface ScheduleResponse {
  id: string;
  name: string;
  enabled: boolean;
  provider: string;
  market_type: string;
  market_pair: string;
  exchange_symbol: string;
  interval: string;
  mode: Exclude<CandleFetchMode, "latest">;
  cron_expression: string;
  timezone: string;
  start_time_ms: number;
  start_time: string;
  batch_limit: number;
  overlap_candles: number;
  verify_continuity: boolean;
  retry_attempts: number;
  retry_delay_seconds: number;
  last_triggered_at_ms: number | null;
  last_triggered_at: string | null;
  next_run_at_ms: number | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleListResponse {
  count: number;
  schedules: ScheduleResponse[];
}

export interface CandleListQuery {
  provider?: MarketDataProviderName;
  market_pair: string;
  interval: string;
  limit: number;
  offset?: number;
  include_count?: boolean;
  start_time?: string;
  end_time?: string;
}

export interface CandleChartQuery {
  provider?: MarketDataProviderName;
  market_pair: string;
  interval: string;
  limit: number;
  start_time?: string;
  end_time?: string;
}

export interface CandleDetailQuery {
  provider?: MarketDataProviderName;
  market_pair: string;
  interval: string;
  open_time_ms: number;
}

export interface CandleCoverageQuery {
  provider?: MarketDataProviderName;
  market_pair: string;
  interval: string;
}

export interface CandleGapQuery {
  provider?: MarketDataProviderName;
  market_pair: string;
  interval: string;
  start_time?: string;
  end_time?: string;
}

export interface DataGapListQuery {
  provider?: MarketDataProviderName;
  market_pair?: string;
  interval?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface DataGapSummaryQuery {
  provider?: MarketDataProviderName;
  market_pair?: string;
  interval?: string;
}

export interface MarketListQuery {
  provider?: MarketDataProviderName;
  enabled?: boolean;
  limit?: number;
  offset?: number;
}

export interface ProviderMarketListQuery {
  provider?: MarketDataProviderName;
  market_type?: "spot";
  quote_asset?: string;
  search?: string;
  limit?: number;
}

export interface MarketCreateRequest {
  provider?: MarketDataProviderName;
  market_type?: "spot";
  market_pair: string;
  enabled?: boolean;
  is_default?: boolean;
}

export type MarketUpdateRequest = Partial<MarketCreateRequest>;

export type CandleFetchMode =
  | "auto"
  | "latest"
  | "backfill"
  | "fill_gaps"
  | "overwrite_range"
  | "delete_reload";

export interface CandleFetchRequest {
  provider?: MarketDataProviderName;
  market_type?: "spot";
  market_pair: string;
  interval: string;
  start_time?: string;
  end_time?: string;
  limit: number;
  mode: CandleFetchMode;
  closed_only?: boolean;
  overlap_candles?: number;
  batch_limit?: number;
  max_batches?: number;
  verify_continuity?: boolean;
  retry_attempts?: number;
  retry_delay_seconds?: number;
}

export interface CandleFetchJobCreateRequest {
  provider?: MarketDataProviderName;
  market_type?: "spot";
  market_pair: string;
  interval: string;
  start_time: string;
  end_time?: string;
  mode: Exclude<CandleFetchMode, "latest">;
  closed_only?: boolean;
  batch_limit?: number;
  overlap_candles?: number;
  verify_continuity?: boolean;
  retry_attempts?: number;
  retry_delay_seconds?: number;
}

export interface CandleFetchJobListQuery {
  provider?: MarketDataProviderName;
  status?: string;
  schedule_id?: string;
  market_pair?: string;
  interval?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface CandleFetchJobSummaryQuery {
  provider?: MarketDataProviderName;
  market_pair?: string;
  interval?: string;
  search?: string;
  timezone?: string;
}

export interface CandleFetchJobOverviewQuery {
  provider?: MarketDataProviderName;
  market_pair?: string;
  interval?: string;
  search?: string;
  recent_limit?: number;
}

export interface DashboardOverviewQuery {
  provider?: MarketDataProviderName;
  interval?: string;
  timezone?: string;
  market_limit?: number;
  activity_limit?: number;
}

export interface ScheduleListQuery {
  provider?: MarketDataProviderName;
  enabled?: boolean;
  limit?: number;
  offset?: number;
}

export interface ScheduleCreateRequest {
  name?: string;
  provider?: MarketDataProviderName;
  market_type?: "spot";
  market_pair: string;
  interval: string;
  mode: Exclude<CandleFetchMode, "latest">;
  cron_expression: string;
  timezone?: string;
  start_time: string;
  enabled?: boolean;
  batch_limit?: number;
  overlap_candles?: number;
  verify_continuity?: boolean;
  retry_attempts?: number;
  retry_delay_seconds?: number;
}

export type ScheduleUpdateRequest = Partial<ScheduleCreateRequest>;

export function listMarkets(query: MarketDataProviderName | MarketListQuery = DEFAULT_MARKET_DATA_PROVIDER) {
  const params = typeof query === "string" ? { provider: query } : { provider: DEFAULT_MARKET_DATA_PROVIDER, ...query };
  return apiRequest<MarketsResponse>(`/api/v1/markets/${buildQueryString(params)}`);
}

export function getProviderStatus(provider: MarketDataProviderName = DEFAULT_MARKET_DATA_PROVIDER) {
  return apiRequest<ProviderStatusResponse>(`/api/v1/provider/status${buildQueryString({ provider })}`);
}

export function getProviderDataSource(provider: MarketDataProviderName = DEFAULT_MARKET_DATA_PROVIDER) {
  return apiRequest<ProviderDataSourceResponse>(`/api/v1/provider/data-source${buildQueryString({ provider })}`);
}

export function updateProviderDataSource(request: ProviderDataSourceUpdateRequest) {
  return apiRequest<ProviderDataSourceResponse>("/api/v1/provider/data-source", {
    method: "PATCH",
    body: request
  });
}

export function testProviderDataSource(request: ProviderDataSourceUpdateRequest) {
  return apiRequest<ProviderDataSourceResponse>("/api/v1/provider/data-source/test", {
    method: "POST",
    body: request
  });
}

export function getStorageSettings() {
  return apiRequest<StorageSettingsResponse>("/api/v1/storage/settings");
}

export function updateStorageSettings(request: StorageSettingsUpdateRequest) {
  return apiRequest<StorageSettingsResponse>("/api/v1/storage/settings", {
    method: "PATCH",
    body: request
  });
}

export function resetDatabase(request: DatabaseResetRequest) {
  return apiRequest<DatabaseResetResponse>("/api/v1/storage/database/reset", {
    method: "POST",
    body: request
  });
}

export function getInterfacePreferences() {
  return apiRequest<InterfacePreferencesResponse>("/api/v1/interface-preferences/settings");
}

export function updateInterfacePreferences(request: InterfacePreferencesUpdateRequest) {
  return apiRequest<InterfacePreferencesResponse>("/api/v1/interface-preferences/settings", {
    method: "PATCH",
    body: request
  });
}

export function getNotificationSettings() {
  return apiRequest<NotificationSettingsResponse>("/api/v1/notifications/settings");
}

export function updateNotificationSettings(request: NotificationSettingsUpdateRequest) {
  return apiRequest<NotificationSettingsResponse>("/api/v1/notifications/settings", {
    method: "PATCH",
    body: request
  });
}

export function getRuntimeStatus() {
  return apiRequest<RuntimeStatusResponse>("/api/v1/runtime/status");
}

export function listApiKeys() {
  return apiRequest<ApiKeyListResponse>("/api/v1/security/api-keys");
}

export function createApiKey(request: ApiKeyCreateRequest) {
  return apiRequest<ApiKeyCreateResponse>("/api/v1/security/api-keys", {
    method: "POST",
    body: request
  });
}

export function updateApiKey(keyId: string, request: ApiKeyUpdateRequest) {
  return apiRequest<ApiKeyResponse>(`/api/v1/security/api-keys/${keyId}`, {
    method: "PATCH",
    body: request
  });
}

export function deleteApiKey(keyId: string) {
  return apiRequest<void>(`/api/v1/security/api-keys/${keyId}`, {
    method: "DELETE"
  });
}

export function listProviderMarkets(query: ProviderMarketListQuery = {}) {
  return apiRequest<ProviderMarketsResponse>(
    `/api/v1/provider/markets${buildQueryString({
      provider: query.provider ?? DEFAULT_MARKET_DATA_PROVIDER,
      market_type: query.market_type ?? "spot",
      quote_asset: query.quote_asset ?? "USDT",
      search: query.search,
      limit: query.limit ?? 100
    })}`
  );
}

export function createMarket(request: MarketCreateRequest) {
  return apiRequest<MarketResponse>("/api/v1/markets", {
    method: "POST",
    body: request
  });
}

export function updateMarket(marketId: string, request: MarketUpdateRequest) {
  return apiRequest<MarketResponse>(`/api/v1/markets/${marketId}`, {
    method: "PATCH",
    body: request
  });
}

export function deleteMarket(marketId: string) {
  return apiRequest<void>(`/api/v1/markets/${marketId}`, {
    method: "DELETE"
  });
}

export function setDefaultMarket(marketId: string) {
  return apiRequest<MarketResponse>(`/api/v1/markets/${marketId}/default`, {
    method: "POST"
  });
}

export function listCandles(query: CandleListQuery, options: MarketDataRequestOptions = {}) {
  return apiRequest<CandleListResponse>(`/api/v1/candles/${buildQueryString(query)}`, {
    signal: options.signal
  });
}

export function listChartCandles(query: CandleChartQuery, options: MarketDataRequestOptions = {}) {
  return apiRequest<CandleChartResponse>(`/api/v1/candles/chart${buildQueryString(query)}`, {
    signal: options.signal
  });
}

export function getCandleDetail(query: CandleDetailQuery, options: MarketDataRequestOptions = {}) {
  return apiRequest<CandleResponse>(`/api/v1/candles/detail${buildQueryString(query)}`, {
    signal: options.signal
  });
}

export function getCandleCoverage(query: CandleCoverageQuery) {
  return apiRequest<CandleCoverageResponse>(`/api/v1/candles/coverage${buildQueryString(query)}`);
}

export function getCandleGaps(query: CandleGapQuery) {
  return apiRequest<CandleGapResponse>(`/api/v1/candles/gaps${buildQueryString(query)}`);
}

export function listDataGaps(query: DataGapListQuery = {}) {
  return apiRequest<DataGapListResponse>(`/api/v1/data-gaps${buildQueryString(query)}`);
}

export function getDataGapSummary(query: DataGapSummaryQuery = {}) {
  return apiRequest<DataGapSummaryResponse>(`/api/v1/data-gaps/summary${buildQueryString(query)}`);
}

export function repairDataGap(gapId: string, request: DataGapRepairRequest = {}) {
  return apiRequest<DataGapRepairResponse>(`/api/v1/data-gaps/${gapId}/repair`, {
    method: "POST",
    body: request
  });
}

export function fetchCandles(request: CandleFetchRequest) {
  return apiRequest<CandleFetchResponse>("/api/v1/candles/fetch", {
    method: "POST",
    body: request
  });
}

export function createCandleFetchJob(request: CandleFetchJobCreateRequest) {
  return apiRequest<CandleFetchJobResponse>("/api/v1/candle-fetch-jobs", {
    method: "POST",
    body: request
  });
}

export function getCandleFetchJob(jobId: string) {
  return apiRequest<CandleFetchJobResponse>(`/api/v1/candle-fetch-jobs/${jobId}`);
}

export function cancelCandleFetchJob(jobId: string) {
  return apiRequest<CandleFetchJobResponse>(`/api/v1/candle-fetch-jobs/${jobId}/cancel`, {
    method: "POST"
  });
}

export function pauseCandleFetchJob(jobId: string) {
  return apiRequest<CandleFetchJobResponse>(`/api/v1/candle-fetch-jobs/${jobId}/pause`, {
    method: "POST"
  });
}

export function resumeCandleFetchJob(jobId: string) {
  return apiRequest<CandleFetchJobResponse>(`/api/v1/candle-fetch-jobs/${jobId}/resume`, {
    method: "POST"
  });
}

export function listCandleFetchJobs(query: CandleFetchJobListQuery = {}) {
  return apiRequest<CandleFetchJobListResponse>(`/api/v1/candle-fetch-jobs${buildQueryString(query)}`);
}

export function getCandleFetchJobSummary(query: CandleFetchJobSummaryQuery = {}) {
  return apiRequest<CandleFetchJobSummaryResponse>(`/api/v1/candle-fetch-jobs/summary${buildQueryString(query)}`);
}

export function getCandleFetchJobOverview(query: CandleFetchJobOverviewQuery = {}) {
  return apiRequest<CandleFetchJobOverviewResponse>(`/api/v1/candle-fetch-jobs/overview${buildQueryString(query)}`);
}

export function getDashboardOverview(query: DashboardOverviewQuery = {}) {
  return apiRequest<DashboardOverviewResponse>(
    `/api/v1/dashboard/overview${buildQueryString({
      provider: query.provider ?? DEFAULT_MARKET_DATA_PROVIDER,
      interval: query.interval ?? "1m",
      timezone: query.timezone,
      market_limit: query.market_limit ?? 20,
      activity_limit: query.activity_limit ?? 8
    })}`
  );
}

export function listSchedules(query: ScheduleListQuery = {}) {
  return apiRequest<ScheduleListResponse>(`/api/v1/schedules${buildQueryString(query)}`);
}

export function getSchedule(scheduleId: string) {
  return apiRequest<ScheduleResponse>(`/api/v1/schedules/${scheduleId}`);
}

export function createSchedule(request: ScheduleCreateRequest) {
  return apiRequest<ScheduleResponse>("/api/v1/schedules", {
    method: "POST",
    body: request
  });
}

export function updateSchedule(scheduleId: string, request: ScheduleUpdateRequest) {
  return apiRequest<ScheduleResponse>(`/api/v1/schedules/${scheduleId}`, {
    method: "PATCH",
    body: request
  });
}

export function pauseSchedule(scheduleId: string) {
  return apiRequest<ScheduleResponse>(`/api/v1/schedules/${scheduleId}/pause`, {
    method: "POST"
  });
}

export function resumeSchedule(scheduleId: string) {
  return apiRequest<ScheduleResponse>(`/api/v1/schedules/${scheduleId}/resume`, {
    method: "POST"
  });
}

export function deleteSchedule(scheduleId: string) {
  return apiRequest<void>(`/api/v1/schedules/${scheduleId}`, {
    method: "DELETE"
  });
}

export function runScheduleNow(scheduleId: string) {
  return apiRequest<CandleFetchJobResponse>(`/api/v1/schedules/${scheduleId}/run-now`, {
    method: "POST"
  });
}
