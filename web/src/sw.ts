/// <reference lib="webworker" />
/* eslint-disable no-restricted-globals */
import { clientsClaim } from "workbox-core";
import { precacheAndRoute } from "workbox-precaching";

import { DRIVER_PREFETCH_SYNC_TAG, prefetchAssignedRoutesFromSession } from "./offlinePrefetch";

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: string[] };

precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", () => {
  clientsClaim();
});

async function notifyClientsPrefetched(): Promise<void> {
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const client of windows) {
    client.postMessage({ type: "DMK_ROUTES_PREFETCHED" });
  }
}

async function prefetchDriverRoutesInBackground(): Promise<void> {
  const ok = await prefetchAssignedRoutesFromSession();
  if (ok) {
    await notifyClientsPrefetched();
  }
}

self.addEventListener("push", (event: PushEvent) => {
  let title = "ДМК";
  let body = "";
  let badgeCount: number | null = null;
  try {
    if (event.data) {
      const parsed = event.data.json() as {
        title?: string;
        body?: string;
        badge?: number;
        badgeCount?: number;
        sync?: string;
      };
      title = parsed.title || title;
      body = parsed.body || body;
      const rawBadge = typeof parsed.badgeCount === "number" ? parsed.badgeCount : parsed.badge;
      badgeCount = typeof rawBadge === "number" && Number.isFinite(rawBadge) ? rawBadge : null;
    }
  } catch {
    try {
      body = event.data?.text() || "";
    } catch {
      body = "";
    }
  }

  const tasks: Array<Promise<unknown>> = [];

  const nav = self.navigator as Navigator & {
    setAppBadge?: (count?: number) => Promise<void>;
    clearAppBadge?: () => Promise<void>;
  };
  if (typeof nav?.setAppBadge === "function") {
    try {
      tasks.push(badgeCount && badgeCount > 0 ? nav.setAppBadge(badgeCount) : nav.setAppBadge());
    } catch {
      // ignore
    }
  }

  tasks.push(
    self.registration.showNotification(title, {
      body,
      icon: "/pwa-192.png",
      badge: "/pwa-192.png"
    })
  );
  tasks.push(prefetchDriverRoutesInBackground());

  event.waitUntil(Promise.all(tasks));
});

self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  const nav = self.navigator as Navigator & {
    clearAppBadge?: () => Promise<void>;
    setAppBadge?: (count?: number) => Promise<void>;
  };
  const openApp = self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientsArr) => {
    const existing = clientsArr.find((client) => "focus" in client) as WindowClient | undefined;
    if (existing) {
      return existing.focus();
    }
    return self.clients.openWindow("/");
  });
  const clearBadge =
    typeof nav?.clearAppBadge === "function"
      ? nav.clearAppBadge()
      : typeof nav?.setAppBadge === "function"
        ? nav.setAppBadge(0)
        : Promise.resolve();
  event.waitUntil(Promise.all([clearBadge, openApp, prefetchDriverRoutesInBackground()]));
});

self.addEventListener("sync", (event) => {
  const syncEvent = event as ExtendableEvent & { tag?: string };
  if (syncEvent.tag !== DRIVER_PREFETCH_SYNC_TAG) {
    return;
  }
  syncEvent.waitUntil(prefetchDriverRoutesInBackground());
});

self.addEventListener("periodicsync", (event) => {
  const periodicEvent = event as ExtendableEvent & { tag?: string };
  if (periodicEvent.tag !== DRIVER_PREFETCH_SYNC_TAG) {
    return;
  }
  periodicEvent.waitUntil(prefetchDriverRoutesInBackground());
});

self.addEventListener("message", (event: ExtendableMessageEvent) => {
  const type = (event.data as { type?: string } | null)?.type;
  if (type === "DMK_PREFETCH") {
    event.waitUntil(prefetchDriverRoutesInBackground());
  }
});
