import { defineConfig, devices } from "@playwright/test";

// verify 容器内固定路径;本地可用 PLAYWRIGHT_BASE_URL 覆盖
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://web:80";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.e2e\.ts/,
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
