import { defineConfig, devices } from "@playwright/test";

// E2E runs against the real backend in fake-LLM mode: no API cost, no network to OpenAI.
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 120_000,
  fullyParallel: false,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
  projects: [
    { name: "light", use: { ...devices["Desktop Chrome"], colorScheme: "light" } },
    { name: "dark", use: { ...devices["Desktop Chrome"], colorScheme: "dark" } },
  ],
  webServer: [
    {
      command: "uv run slidex serve",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/health",
      env: { SLIDEX_FAKE_LLM: "1", SLIDEX_DATA_DIR: "../data-e2e" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
