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
  try {
    if (event.data) {
      const parsed = event.data.json() as { title?: string; body?: string };
      title = parsed.title || title;
      body = parsed.body || body;
    }
  } catch {
    try {
      body = event.data?.text() || "";
    } catch {
      body = "";
    }
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/pwa-192.png",
      badge: "/pwa-192.png"
    })
  );
});
