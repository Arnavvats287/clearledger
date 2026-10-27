import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL:
      process.env.CLEARLEDGER_BROWSER_BUILD === "1"
        ? "http://127.0.0.1:4173"
        : "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        "../.venv/Scripts/python.exe -X utf8 ../scripts/serve_frontend_demo.py",
      url: "http://127.0.0.1:8010/health",
      reuseExistingServer: true,
      timeout: 120000,
    },
    {
      command:
        process.env.CLEARLEDGER_BROWSER_BUILD === "1"
          ? "npm run preview"
          : "npm run dev",
      url:
        process.env.CLEARLEDGER_BROWSER_BUILD === "1"
          ? "http://127.0.0.1:4173"
          : "http://127.0.0.1:5173",
      reuseExistingServer: true,
    },
  ],
});
