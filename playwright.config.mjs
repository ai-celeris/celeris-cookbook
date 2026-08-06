import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4178",
    browserName: "chromium",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "node tests/browser/demo-host.mjs",
    port: 4178,
    reuseExistingServer: !process.env.CI,
  },
});
