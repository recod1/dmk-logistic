/// <reference lib="webworker" />
/* eslint-disable no-restricted-globals */
import { clientsClaim } from "workbox-core";
import { precacheAndRoute } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: string[] };

precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(clientsClaim());
});

self.addEventListener("push", (event: PushEvent) => {
  let title = "ДМК";
  let body = "";
  let badgeCount: number | null = null;
  try {
    if (event.data) {
      const parsed = event.data.json() as { title?: string; body?: string; badge?: number; badgeCount?: number };
      title = parsed.title || title;
      body = parsed.body || body;
      // support both "badge" and "badgeCount" keys (if backend starts sending it later)
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

  // iOS PWA: setAppBadge is available only for installed web apps with notifications permission.
  // Use an "empty" badge (dot) when count is unknown; use numeric badge when count is provided.
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

  event.waitUntil(Promise.all(tasks));
});

self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  const nav = self.navigator as Navigator & {
    clearAppBadge?: () => Promise<void>;
    setAppBadge?: (count?: number) => Promise<void>;
  };
  if (typeof nav?.clearAppBadge === "function") {
    event.waitUntil(nav.clearAppBadge());
  } else if (typeof nav?.setAppBadge === "function") {
    event.waitUntil(nav.setAppBadge(0));
  }
});
