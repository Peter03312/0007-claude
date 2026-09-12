import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发环境下把 /api 代理到本机 FastAPI;
// 生产(Docker)由 nginx 同名路径代理到 api 服务。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/testSetup.ts"],
    css: false,
  },
});
