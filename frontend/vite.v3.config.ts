import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  root: resolve(import.meta.dirname, "v3"),
  base: "/static/workbench-v3/",
  plugins: [react()],
  build: { outDir: resolve(import.meta.dirname, "workbench-v3"), emptyOutDir: true,
    rollupOptions: { output: { manualChunks: id => /node_modules\/(echarts|zrender)\//.test(id.replaceAll("\\", "/")) ? "charts" : undefined } } },
  server: { host: "127.0.0.1", port: 5174, strictPort: true, proxy: { "/api": "http://127.0.0.1:8000" } },
});
