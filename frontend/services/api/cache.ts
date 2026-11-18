export interface ApiCacheOptions {
  force?: boolean;
  ttl?: number;
}

interface ApiCacheContext {
  baseURL: string;
  credentialScope: string;
}

interface CacheEntry {
  expiresAt: number;
  value: unknown;
}

const DATA_TTL_MS = 30_000;
const CATALOG_TTL_MS = 5 * 60_000;
const MAX_ENTRIES = 150;

const entries = new Map<string, CacheEntry>();
const pending = new Map<string, Promise<unknown>>();
let activeCredentialScope = "";
let generation = 0;

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, item]) => item !== undefined)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, stableValue(item)]),
    );
  }
  return value;
}

function cacheTtl(path: string): number {
  // Sessão e notificações representam estado pessoal ou em tempo real.
  if (/^\/(?:auth(?:\/|$)|notificacoes(?:[-/]|$)|alertas(?:\/|$))/.test(path)) return 0;
  if (/^\/(setores|equipes-notificacao)(?:\/|$)/.test(path)) return CATALOG_TTL_MS;
  return DATA_TTL_MS;
}

function cacheKey(context: ApiCacheContext, path: string, query?: Record<string, unknown>): string {
  return `${context.baseURL}|${context.credentialScope}|${path}|${JSON.stringify(stableValue(query ?? {}))}`;
}

function pruneExpired(now: number): void {
  for (const [key, entry] of entries) {
    if (entry.expiresAt <= now) entries.delete(key);
  }
  while (entries.size > MAX_ENTRIES) entries.delete(entries.keys().next().value as string);
}

export function clearApiCache(): void {
  generation++;
  entries.clear();
  pending.clear();
}

export async function cachedApiGet<T>(
  context: ApiCacheContext,
  path: string,
  query: Record<string, unknown> | undefined,
  options: ApiCacheOptions,
  load: () => Promise<T>,
): Promise<T> {
  if (import.meta.server) return load();

  if (activeCredentialScope !== context.credentialScope) {
    activeCredentialScope = context.credentialScope;
    clearApiCache();
  }

  const ttl = options.ttl ?? cacheTtl(path);
  if (ttl <= 0) return load();

  const now = Date.now();
  pruneExpired(now);
  const key = cacheKey(context, path, query);
  if (options.force) {
    entries.delete(key);
    pending.delete(key);
  }
  const hit = entries.get(key);
  if (hit && hit.expiresAt > now) return hit.value as T;

  const inFlight = pending.get(key);
  if (inFlight) return inFlight as Promise<T>;

  const requestGeneration = generation;
  const request = load().then((value) => {
    if (generation === requestGeneration) {
      entries.set(key, { value, expiresAt: Date.now() + ttl });
      pruneExpired(Date.now());
    }
    return value;
  }).finally(() => {
    if (pending.get(key) === request) pending.delete(key);
  });

  pending.set(key, request);
  return request;
}
