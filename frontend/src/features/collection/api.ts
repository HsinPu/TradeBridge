import { ApiError, apiJobRequest, apiRequest, buildQueryString } from "../../shared/api/client";

export type CollectionPolicy = {
  revision: number; enabled: boolean; history_paused: boolean; refresh_minutes: number;
  catalog_hours: number; queue_limit: number; min_free_bytes: number; blocked_reason: string | null;
  last_cycle_ms: number | null;
};
export type CollectionStatus = {
  policy: CollectionPolicy;
  markets: { total_markets: number; discovering: number; excluded: number; history_scanned: number; oldest_tail_next_ms: number | null; oldest_tail_complete_until_ms: number | null };
  catalog: { total: number; tradable: number }; segments: Record<string, number>; missing_minutes: number; checked_at_ms: number;
};
export type CatalogRun = { id: string; status: string; symbol_count: number | null; error_message: string | null; finished_at_ms: number | null };
export type CatalogMarket = { exchange_symbol: string; market_pair: string; exchange_status: string; spot_allowed: boolean; observation: string; enabled: boolean | null; last_seen_at_ms: number };
export type CollectionMarket = { exchange_symbol: string; market_pair: string; excluded: boolean; first_open_time_ms: number | null; history_next_ms: number | null; history_end_ms: number | null; tail_next_ms: number | null; tail_complete_until_ms: number | null; exchange_status: string | null; enabled: boolean | null; observation: string | null; problem_segments: number; last_error: string | null };
export type Page<T> = { items: T[]; next_cursor: string | null; total?: number };
export type CollectionPreview = { policy: CollectionPolicy; eligible_markets: number; catalog_sync: { id: string; finished_at_ms: number } | null; free_bytes: number; scheduler_enabled: boolean; conflicting_schedules: { id: string; name: string; market_pair: string; interval: string }[] };

export const collectionApi = {
  status: (signal?: AbortSignal) => apiRequest<CollectionStatus>("/api/v1/collection", { signal }),
  catalogRun: (signal?: AbortSignal) => apiRequest<CatalogRun | null>("/api/v1/market-catalog/syncs/latest", { signal }),
  sync: (allow_large_change = false) => apiJobRequest<CatalogRun>("/api/v1/market-catalog/sync", { allow_large_change }),
  preview: () => apiRequest<CollectionPreview>("/api/v1/collection/preview"),
  start: (revision: number, pause_schedule_ids: string[]) => apiRequest<CollectionPolicy>("/api/v1/collection/start", { method: "POST", body: { revision, pause_schedule_ids } }),
  control: (scope: "all" | "history", paused: boolean) => apiRequest<CollectionPolicy>("/api/v1/collection/control", { method: "POST", body: { scope, paused } }),
  configure: (revision: number, values: Partial<CollectionPolicy>) => apiRequest<CollectionPolicy>("/api/v1/collection/policy", { method: "PATCH", body: { revision, ...values } }),
  markets: (search: string, cursor: string | null, signal?: AbortSignal) => apiRequest<Page<CollectionMarket>>(`/api/v1/collection/markets${buildQueryString({ search, cursor, limit: 50 })}`, { signal }),
  catalog: (search: string, cursor: string | null, signal?: AbortSignal) => apiRequest<Page<CatalogMarket>>(`/api/v1/market-catalog${buildQueryString({ search, cursor, limit: 100 })}`, { signal }),
  exclude: (symbol: string, excluded: boolean) => apiRequest(`/api/v1/collection/markets/${encodeURIComponent(symbol)}`, { method: "PATCH", body: { excluded } }),
  retry: (symbol?: string) => apiRequest<{ job_ids: string[] }>(`/api/v1/collection/retry${buildQueryString({ symbol })}`, { method: "POST" })
};

export function errorText(error: unknown): string {
  if (error instanceof ApiError && error.detail && typeof error.detail === "object" && "detail" in error.detail && typeof error.detail.detail === "string") return error.detail.detail;
  return error instanceof Error ? error.message : String(error);
}

export const dateText = (ms: number | null) => ms === null ? "—" : new Date(ms).toISOString().replace("T", " ").slice(0, 16) + " UTC";
