/// <reference lib="webworker" />
/* eslint-disable no-restricted-globals */
import { clientsClaim } from "workbox-core";
import { precacheAndRoute } from "workbox-precaching";

import { deliverChatFromPush } from "./chatDeliveryBg";
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
  let deliveryHint: Record<string, unknown> | null = null;
  try {
    if (event.data) {
      const parsed = event.data.json() as {
        title?: string;
        body?: string;
        badge?: number;
        badgeCount?: number;
        sync?: string;
        event_type?: string;
        route_id?: string | null;
        room_id?: number | string | null;
        salary_id?: number | string | null;
        chat_message_id?: number | string | null;
        salary_chat_message_id?: number | string | null;
      };
      title = parsed.title || title;
      body = parsed.body || body;
      const rawBadge = typeof parsed.badgeCount === "number" ? parsed.badgeCount : parsed.badge;
      badgeCount = typeof rawBadge === "number" && Number.isFinite(rawBadge) ? rawBadge : null;
      deliveryHint = parsed;
    }
  } catch {
    try {
      body = event.data?.text() || "";
    } catch {
      body = "";
    }
  }

  const tasks: Array<Promise<unknown>> = [];
  if (deliveryHint) {
    tasks.push(
      deliverChatFromPush(deliveryHint).then(async (ok) => {
        if (!ok) {
          return;
        }
        const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
        for (const client of windows) {
          client.postMessage({ type: "DMK_CHAT_DELIVERED" });
        }
      })
    );
  }

  const nav = self.navigator as Navigator & {
    setAppBadge?: (count?: number) => Promise<void>;
    clearAppBadge?: () => Promise<void>;
  };
  if (typeof nav?.setAppBadge === "function") {
    try {
      tasks.push(
        badgeCount != null && badgeCount > 0
          ? nav.setAppBadge(badgeCount)
          : typeof nav.clearAppBadge === "function"
            ? nav.clearAppBadge()
            : nav.setAppBadge(0)
      );
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
  const openApp = self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientsArr) => {
    const existing = clientsArr.find((client) => "focus" in client) as WindowClient | undefined;
    if (existing) {
      return existing.focus();
    }
    return self.clients.openWindow("/");
  });
  event.waitUntil(Promise.all([openApp, prefetchDriverRoutesInBackground()]));
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
  if (type === "SKIP_WAITING") {
    void self.skipWaiting();
    return;
  }
  if (type === "DMK_PREFETCH") {
    event.waitUntil(prefetchDriverRoutesInBackground());
  }
  if (type === "DMK_SET_BADGE") {
    const count = Number((event.data as { count?: number } | null)?.count);
    const nav = self.navigator as Navigator & {
      setAppBadge?: (count?: number) => Promise<void>;
      clearAppBadge?: () => Promise<void>;
    };
    if (typeof nav?.setAppBadge !== "function") {
      return;
    }
    if (Number.isFinite(count) && count > 0) {
      event.waitUntil(nav.setAppBadge(count));
    } else if (typeof nav.clearAppBadge === "function") {
      event.waitUntil(nav.clearAppBadge());
    } else {
      event.waitUntil(nav.setAppBadge(0));
    }
  }
});
