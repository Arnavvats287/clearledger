import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";
const portfolio = process.env.PORTFOLIO_BROWSER_URL;
const python = resolve(
  process.platform === "win32"
    ? "../.venv/Scripts/python.exe"
    : "../.venv/bin/python",
);
const demo = resolve("../scripts/serve_frontend_demo.py");
export default defineConfig({
  testDir: "./e2e",
  testMatch: portfolio ? "**/portfolio.spec.ts" : "**/workstation.spec.ts",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL:
      portfolio ||
      (process.env.CLEARLEDGER_BROWSER_BUILD === "1"
        ? "http://127.0.0.1:4173"
        : "http://127.0.0.1:5173"),
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    screenshot: "only-on-failure",
  },
  webServer: portfolio
    ? []
    : [
        {
          command: `"${python}" -X utf8 "${demo}"`,
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
