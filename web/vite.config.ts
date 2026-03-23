import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["logo.jpg", "icons/icon-192.png", "icons/icon-512.png"],
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
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any maskable"
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable"
          },
          {
            src: "/logo.jpg",
            sizes: "1024x1024",
            type: "image/jpeg",
            purpose: "any"
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

