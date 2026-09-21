import { computed, ref } from "vue";

export interface DebugErrorEntry {
  id: number;
  at: string;
  source: string;
  message: string;
  name: string;
  stack: string | null;
  status: number | null;
  url: string | null;
  method: string | null;
  detail: string | null;
  bodyPreview: string | null;
  online: boolean;
  visibility: string;
  effectiveType: string | null;
  downlink: number | null;
  rtt: number | null;
  userAgent: string;
  extra: Record<string, unknown> | null;
}

const MAX_ERRORS = 40;
let nextId = 1;

export const debugErrors = ref<DebugErrorEntry[]>([]);
export const unreadDebugCount = ref(0);
export const latestDebugError = computed(() => debugErrors.value[0] ?? null);

type NavConnection = {
  effectiveType?: string;
  downlink?: number;
  rtt?: number;
};

function navConnection(): NavConnection | null {
  if (typeof navigator === "undefined") {
    return null;
  }
  return ((navigator as Navigator & { connection?: NavConnection }).connection ?? null) as NavConnection | null;
}

export function connectionNetInfo(): {
  online: boolean;
  effectiveType: string | null;
  downlink: number | null;
  rtt: number | null;
  visibility: string;
  userAgent: string;
} {
  const conn = navConnection();
  return {
    online: typeof navigator === "undefined" ? true : navigator.onLine,
    effectiveType: conn?.effectiveType ?? null,
    downlink: typeof conn?.downlink === "number" ? conn.downlink : null,
    rtt: typeof conn?.rtt === "number" ? conn.rtt : null,
    visibility: typeof document === "undefined" ? "unknown" : document.visibilityState,
    userAgent: typeof navigator === "undefined" ? "" : navigator.userAgent
  };
}

export function reportDebugError(input: {
  source: string;
  error?: unknown;
  message?: string;
  url?: string | null;
  method?: string | null;
  extra?: Record<string, unknown> | null;
}): DebugErrorEntry {
  const err = input.error as
    | {
        name?: string;
        message?: string;
        stack?: string;
        status?: number;
        detail?: string | null;
        bodyText?: string;
      }
    | null
    | undefined;
  const net = connectionNetInfo();
  const message =
    (input.message || "").trim() ||
    (err?.message || "").trim() ||
    (typeof input.error === "string" ? input.error : "") ||
    "Неизвестная ошибка";
  const entry: DebugErrorEntry = {
    id: nextId++,
    at: new Date().toISOString(),
    source: input.source,
    message,
    name: err?.name || (input.error instanceof Error ? input.error.name : typeof input.error),
    stack: err?.stack || (input.error instanceof Error ? input.error.stack || null : null),
    status: typeof err?.status === "number" ? err.status : null,
    url: input.url ?? (typeof (err as { url?: unknown } | null)?.url === "string" ? (err as { url?: string }).url ?? null : null),
    method:
      input.method ??
      (typeof (err as { method?: unknown } | null)?.method === "string" ? (err as { method?: string }).method ?? null : null),
    detail: err?.detail ?? null,
    bodyPreview: err?.bodyText ? String(err.bodyText).slice(0, 1200) : null,
    online: net.online,
    visibility: net.visibility,
    effectiveType: net.effectiveType,
    downlink: net.downlink,
    rtt: net.rtt,
    userAgent: net.userAgent,
    extra: input.extra ?? null
  };
  debugErrors.value = [entry, ...debugErrors.value].slice(0, MAX_ERRORS);
  unreadDebugCount.value += 1;
  return entry;
}

export function markDebugErrorsRead(): void {
  unreadDebugCount.value = 0;
}

export function clearDebugErrors(): void {
  debugErrors.value = [];
  unreadDebugCount.value = 0;
}

export function formatDebugDump(snapshot: Record<string, unknown>): string {
  return JSON.stringify(
    {
      captured_at: new Date().toISOString(),
      snapshot,
      errors: debugErrors.value
    },
    null,
    2
  );
}
