import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const E2E_DB = path.join(ROOT, 'data', 'processed', 'e2e_trade.db');
const E2E_DB_URL = `sqlite:///${E2E_DB.replace(/\\/g, '/')}`;

const apiEnv = {
  ...process.env,
  TRADE_DATABASE_URL: E2E_DB_URL,
  TRADE_AUTH_ENABLED: 'false',
  TRADE_ENVIRONMENT: 'development',
  TRADE_OLLAMA_ENABLED: 'false',
  TRADE_SOURCE_FETCH_SCHEDULER_ENABLED: 'false',
  TRADE_LIVE_FEED_ENABLED: 'false',
};

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Prefer bundled Chromium; fall back to installed Chrome if download failed.
        channel: process.env.PW_CHANNEL === 'chrome' ? 'chrome' : undefined,
      },
    },
  ],
  webServer: [
    {
      command: `python "${path.join(ROOT, 'scripts', 'e2e_api_server.py')}"`,
      cwd: ROOT,
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: apiEnv,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: __dirname,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
