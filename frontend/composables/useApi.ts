import { ApiError, apiErrorMessage } from "~/services/api/error";
import { cachedApiGet, clearApiCache, type ApiCacheOptions } from "~/services/api/cache";

function normalizedBaseUrl(value: string): string {
  const base = value.replace(/\/$/, "");
  return /\/api\/v\d+$/.test(base) ? base : `${base}/api/v1`;
}

export function useApi() {
  const config = useRuntimeConfig();
  const auth = useAuthStore();
  const baseURL = normalizedBaseUrl(config.public.apiBaseUrl);

  async function request<T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}): Promise<T> {
    try {
      const response = (await $fetch<T>(path, {
        ...options,
        baseURL,
        // Envia o cookie de sessão HttpOnly do login de homologação (o JS nunca o lê).
        credentials: "include",
        headers: {
          ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}),
          ...((options.headers as Record<string, string> | undefined) ?? {}),
        },
      })) as T;
      const method = String(options.method ?? "GET").toUpperCase();
      if (method !== "GET" && method !== "HEAD") clearApiCache();
      return response;
    } catch (error: unknown) {
      const response = (error as { response?: { status?: number; _data?: unknown } }).response;
      throw new ApiError(apiErrorMessage(response?._data), response?.status ?? 0, response?._data);
    }
  }

  function get<T>(
    path: string,
    query?: Record<string, unknown>,
    cacheOptions: ApiCacheOptions = {},
    requestOptions: Parameters<typeof $fetch<T>>[1] = {},
  ): Promise<T> {
    const credentialScope = `${auth.token ?? "cookie"}:${auth.user?.id ?? "anonymous"}`;
    return cachedApiGet(
      { baseURL, credentialScope },
      path,
      query,
      cacheOptions,
      () => request<T>(path, { ...requestOptions, method: "GET", query }),
    );
  }

  return {
    get,
    post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body as never }),
    put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body as never }),
    patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: body as never }),
    delete: <T>(path: string, body?: unknown, query?: Record<string, unknown>) =>
      request<T>(path, { method: "DELETE", body: body as never, query }),
    clearCache: clearApiCache,
    request,
  };
}
