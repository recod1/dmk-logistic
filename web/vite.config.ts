import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["logo.jpg", "pwa-192.png", "pwa-512.png", "apple-touch-icon.png", "screenshots/pwa-home-1280x720.png"],
      manifest: {
        name: "DMK Mobile",
        short_name: "DMK",
        description: "Offline-first mobile route tracker",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        scope: "/",
        start_url: "/",
        icons: [
          {
            src: "/pwa-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any"
          },
          {
            src: "/pwa-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "maskable"
          },
          {
            src: "/pwa-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any"
          },
          {
            src: "/pwa-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable"
          }
        ],
        screenshots: [
          {
            src: "/screenshots/pwa-home-1280x720.png",
            sizes: "1280x720",
            type: "image/png",
            form_factor: "wide",
            label: "Главный экран приложения DMK Mobile"
          }
        ]
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,jpg,jpeg,svg,json,webmanifest}"]
      }
    })
  ],
  server: {
    host: "0.0.0.0",
    port: 5173
  }
});
