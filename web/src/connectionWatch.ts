import { computed, ref } from "vue";

import { connectionNetInfo, reportDebugError } from "./debugLog";

export type ConnectionTone = "ok" | "warn" | "bad";
export type WsState = "idle" | "open" | "closed";

const apiBaseRef = ref("/api");
const online = ref(typeof navigator === "undefined" ? true : navigator.onLine);
const serverOk = ref<boolean | null>(null);
const lastHealthAt = ref<string | null>(null);
const lastHealthMs = ref<number | null>(null);
const lastHealthError = ref<string | null>(null);
const wsNotifications = ref<WsState>("idle");
const wsChat = ref<WsState>("idle");
const syncing = ref(false);
const pendingOutbox = ref(0);
const pendingDocs = ref(0);
const pendingAccepts = ref(0);

let healthTimer: number | null = null;
let healthInFlight = false;
let healthFailStreak = 0;
let lastReportedHealthFail = false;
let unhandledBound = false;

function healthTimeoutMs(): number {
  if (typeof window === "undefined") {
    return 20_000;
  }
  const coarse = window.matchMedia?.("(pointer: coarse)")?.matches;
  return coarse ? 22_000 : 12_000;
}

export const connectionOnline = online;
export const connectionServerOk = serverOk;
export const connectionSyncing = syncing;
export const connectionPendingOutbox = pendingOutbox;
export const connectionPendingDocs = pendingDocs;

export const connectionLabel = computed(() => {
  if (!online.value) {
    return "Нет сети";
  }
  if (serverOk.value === false) {
    return "Нет сервера";
  }
  if (syncing.value || pendingDocs.value > 0 || pendingOutbox.value > 0 || pendingAccepts.value > 0) {
    return "Синхр.";
  }
  const net = connectionNetInfo();
  if (net.effectiveType === "slow-2g" || net.effectiveType === "2g") {
    return "Слабая сеть";
  }
  if (serverOk.value === null) {
    return "Проверка…";
  }
  return "Онлайн";
});

export const connectionTone = computed<ConnectionTone>(() => {
  if (!online.value || serverOk.value === false) {
    return "bad";
  }
  if (syncing.value || pendingDocs.value > 0 || pendingOutbox.value > 0 || pendingAccepts.value > 0) {
    return "warn";
  }
  const net = connectionNetInfo();
  if (net.effectiveType === "slow-2g" || net.effectiveType === "2g") {
    return "warn";
  }
  if (serverOk.value === null) {
    return "warn";
  }
  return "ok";
});

export const connectionHint = computed(() => {
  const net = connectionNetInfo();
  const parts = [
    online.value ? "Интернет: есть" : "Интернет: нет",
    serverOk.value === true ? "Сервер: отвечает" : serverOk.value === false ? "Сервер: нет ответа" : "Сервер: проверка",
    `Уведомления: ${wsLabel(wsNotifications.value)}`,
    `Чат: ${wsLabel(wsChat.value)}`
  ];
  if (lastHealthMs.value != null) {
    parts.push(`Пинг: ${Math.round(lastHealthMs.value)} мс`);
  }
  if (net.effectiveType) {
    parts.push(`Сеть: ${net.effectiveType}`);
  }
  if (pendingOutbox.value || pendingDocs.value || pendingAccepts.value) {
    parts.push(`Очередь: событий ${pendingOutbox.value}, фото ${pendingDocs.value}, принятий ${pendingAccepts.value}`);
  }
  return parts.join(" · ");
});

function wsLabel(state: WsState): string {
  if (state === "open") return "подключены";
  if (state === "closed") return "нет";
  return "—";
}

export function connectionSnapshot(): Record<string, unknown> {
  const net = connectionNetInfo();
  return {
    ...net,
    label: connectionLabel.value,
    tone: connectionTone.value,
    online: online.value,
    server_ok: serverOk.value,
    last_health_at: lastHealthAt.value,
    last_health_ms: lastHealthMs.value,
    last_health_error: lastHealthError.value,
    ws_notifications: wsNotifications.value,
    ws_chat: wsChat.value,
    syncing: syncing.value,
    pending_outbox: pendingOutbox.value,
    pending_docs: pendingDocs.value,
    pending_accepts: pendingAccepts.value,
    api_base: apiBaseRef.value,
    href: typeof location === "undefined" ? null : location.href
  };
}

export function setConnectionSyncing(value: boolean): void {
  syncing.value = value;
}

export function setConnectionQueue(counts: { outbox?: number; docs?: number; accepts?: number }): void {
  if (typeof counts.outbox === "number") pendingOutbox.value = counts.outbox;
  if (typeof counts.docs === "number") pendingDocs.value = counts.docs;
  if (typeof counts.accepts === "number") pendingAccepts.value = counts.accepts;
}

export function setNotificationsWsState(state: WsState): void {
  wsNotifications.value = state;
}

export function setChatWsState(state: WsState): void {
  wsChat.value = state;
}

function isInstantFetchFail(error: unknown): boolean {
  const message = ((error as Error | null)?.message || "").toLowerCase();
  return message.includes("load failed") || message.includes("failed to fetch");
}

async function fetchHealth(signal: AbortSignal): Promise<Response> {
  const base = apiBaseRef.value.replace(/\/$/, "");
  return fetch(`${base}/health?t=${Date.now()}`, {
    method: "GET",
    cache: "no-store",
    credentials: "same-origin",
    signal,
    headers: { Accept: "application/json" }
  });
}

let lastApiOkAt = 0;

export function noteApiReachable(): void {
  lastApiOkAt = Date.now();
  healthFailStreak = 0;
  lastHealthError.value = null;
  serverOk.value = true;
}

export async function pingServer(): Promise<boolean> {
  if (healthInFlight) {
    return serverOk.value !== false;
  }
  if (lastApiOkAt > 0 && Date.now() - lastApiOkAt < 20_000) {
    serverOk.value = true;
    lastHealthError.value = null;
    return true;
  }
  healthInFlight = true;
  const ctrl = new AbortController();
  const timeoutMs = healthTimeoutMs();
  const timer = globalThis.setTimeout(() => ctrl.abort(), timeoutMs);
  const started = typeof performance !== "undefined" ? performance.now() : Date.now();
  try {
    let response: Response;
    try {
      response = await fetchHealth(ctrl.signal);
    } catch (error) {
      if (!isInstantFetchFail(error) || ctrl.signal.aborted) {
        throw error;
      }
      await new Promise((resolve) => globalThis.setTimeout(resolve, 400));
      response = await fetchHealth(ctrl.signal);
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    lastHealthMs.value = (typeof performance !== "undefined" ? performance.now() : Date.now()) - started;
    lastHealthAt.value = new Date().toISOString();
    lastHealthError.value = null;
    healthFailStreak = 0;
    serverOk.value = true;
    void response;
    if (lastReportedHealthFail) {
      lastReportedHealthFail = false;
    }
    return true;
  } catch (error) {
    lastHealthMs.value = (typeof performance !== "undefined" ? performance.now() : Date.now()) - started;
    lastHealthAt.value = new Date().toISOString();
    lastHealthError.value = (error as Error)?.message || String(error);
    if (lastApiOkAt > 0 && Date.now() - lastApiOkAt < 20_000) {
      serverOk.value = true;
      return false;
    }
    healthFailStreak += 1;
    const wasOk = serverOk.value;
    if (healthFailStreak >= 2) {
      serverOk.value = false;
    }
    if (wasOk !== false && healthFailStreak >= 2 && !lastReportedHealthFail) {
      lastReportedHealthFail = true;
      reportDebugError({
        source: "health",
        error,
        message: "Нет ответа сервера (health)",
        url: `${apiBaseRef.value}/health`,
        method: "GET",
        extra: { ...connectionSnapshot(), timeout_ms: timeoutMs, fail_streak: healthFailStreak }
      });
    }
    return false;
  } finally {
    globalThis.clearTimeout(timer);
    healthInFlight = false;
    online.value = typeof navigator === "undefined" ? true : navigator.onLine;
  }
}

function onOnline(): void {
  online.value = true;
  void pingServer();
}

function onOffline(): void {
  online.value = false;
  serverOk.value = false;
}

function onUnhandledRejection(event: PromiseRejectionEvent): void {
  const reason = event.reason as { name?: string; message?: string } | null;
  if (reason?.name === "ApiError") {
    return;
  }
  reportDebugError({
    source: "unhandledrejection",
    error: event.reason,
    extra: connectionSnapshot()
  });
}

function onWindowError(event: ErrorEvent): void {
  reportDebugError({
    source: "window.onerror",
    error: event.error || event.message,
    message: event.message,
    extra: {
      ...connectionSnapshot(),
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno
    }
  });
}

export function startConnectionWatch(apiBase: string): void {
  apiBaseRef.value = apiBase || "/api";
  online.value = typeof navigator === "undefined" ? true : navigator.onLine;
  if (typeof window === "undefined") {
    return;
  }
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
  if (!unhandledBound) {
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    window.addEventListener("error", onWindowError);
    unhandledBound = true;
  }
  if (healthTimer !== null) {
    window.clearInterval(healthTimer);
  }
  void pingServer();
  healthTimer = window.setInterval(() => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden") {
      return;
    }
    void pingServer();
  }, 45000);
}

export function stopConnectionWatch(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.removeEventListener("online", onOnline);
  window.removeEventListener("offline", onOffline);
  if (healthTimer !== null) {
    window.clearInterval(healthTimer);
    healthTimer = null;
  }
}

export function restartConnectionWatch(apiBase: string): void {
  stopConnectionWatch();
  healthFailStreak = 0;
  healthInFlight = false;
  lastReportedHealthFail = false;
  lastHealthError.value = null;
  serverOk.value = null;
  startConnectionWatch(apiBase);
}
