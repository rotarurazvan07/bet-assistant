import { defineConfig, devices } from '@playwright/test';

// Cycle 9 (issue #63): infrastructure config. Cycle 15 wired CI.
// PR #75 batch (D-B): external-stack mode — when E2E_BASE_URL is set (the CI
// e2e-tests job runs the composed docker stack on :3002), use it as baseURL
// and do NOT start a local webServer (the stack's nginx serves the built
// frontend + proxies /api + /ws). Local default unchanged: vite dev on 5173.
const externalBaseUrl = process.env.E2E_BASE_URL;

export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    // 'list' for humans; junit feeds the E2E step-summary (CI gate tab).
    reporter: [['list'], ['junit', { outputFile: 'test-results/e2e-junit.xml' }]],
    timeout: 120_000,
    use: {
        baseURL: externalBaseUrl ?? 'http://localhost:5173',
        trace: 'on-first-retry',
        actionTimeout: 15_000,
    },
    projects: [
        { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
        { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
        { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    ],
    ...(externalBaseUrl
        ? {}
        : {
              webServer: {
                  command: 'npm run dev -- --port 5173 --strictPort',
                  url: 'http://localhost:5173',
                  reuseExistingServer: !process.env.CI,
                  timeout: 120_000,
              },
          }),
});
