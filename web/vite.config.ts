import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [],
      manifest: {
        name: "DMK Mobile",
        short_name: "DMK",
        description: "Offline-first mobile route tracker",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        scope: "/",
        start_url: "/",
        icons: []
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,json}"]
      }
    })
  ],
  server: {
    host: "0.0.0.0",
    port: 5173
  }
});

