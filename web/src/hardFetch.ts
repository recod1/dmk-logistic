/** Safari/iOS often ignores AbortSignal; JS must still unblock after timeoutMs. */

export function createTimeoutError(): Error {
  const error = new Error("timeout");
  error.name = "TimeoutError";
  return error;
}

export function swallowAbandoned(promise: Promise<unknown>): void {
  void promise.catch(() => {
    // Late reject after Promise.race timeout — do not surface as unhandledrejection.
  });
}

function mergeAbortSignals(signals: Array<AbortSignal | null | undefined>): AbortSignal | undefined {
  const real = signals.filter((item): item is AbortSignal => Boolean(item));
  if (!real.length) {
    return undefined;
  }
  const anyFn = (AbortSignal as typeof AbortSignal & { any?: (items: AbortSignal[]) => AbortSignal }).any;
  if (typeof anyFn === "function") {
    return anyFn(real);
  }
  return real[0];
}

export async function fetchWithHardTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const timeoutCtrl = new AbortController();
  let timer: ReturnType<typeof globalThis.setTimeout> | null = null;
  const fetchPromise = fetch(url, {
    ...init,
    cache: init.cache ?? "no-store",
    credentials: init.credentials ?? "same-origin",
    keepalive: false,
    signal: mergeAbortSignals([init.signal, timeoutCtrl.signal])
  });
  const timeoutPromise = new Promise<never>((_, reject) => {
    timer = globalThis.setTimeout(() => {
      try {
        timeoutCtrl.abort();
      } catch {
        // Safari may keep the HTTP request alive.
      }
      reject(createTimeoutError());
    }, timeoutMs);
  });
  try {
    return await Promise.race([fetchPromise, timeoutPromise]);
  } catch (error) {
    swallowAbandoned(fetchPromise);
    throw error;
  } finally {
    if (timer != null) {
      globalThis.clearTimeout(timer);
    }
  }
}

export function withRetryBust(url: string, attempt: number): string {
  if (attempt <= 0) {
    return url;
  }
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}_r=${Date.now()}_${attempt}`;
}
