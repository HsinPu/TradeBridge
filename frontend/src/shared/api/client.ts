const DEFAULT_API_BASE_URL = "http://127.0.0.1:8025";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, "");

type ApiRequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<TResponse>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<TResponse> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal
  });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }

    throw new ApiError(`API request failed with ${response.status}`, response.status, detail);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return (await response.json()) as TResponse;
}

export function buildQueryString<TParams extends object>(params: TParams) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (
      (typeof value === "string" || typeof value === "number" || typeof value === "boolean") &&
      value !== ""
    ) {
      searchParams.set(key, String(value));
    }
  }

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}
