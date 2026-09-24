import { defineConfig, devices } from '@playwright/test';

// Cycle 9 (issue #63): infrastructure config. CI wiring lands in cycle 15.
// webServer launches the Vite dev server so `npm run test:e2e` works locally
// without a manual `npm run dev`. The backend is NOT launched — smoke tests
// only assert the SPA shell renders (API/WS failures are handled gracefully
// by design: fetchStatus().catch + useSocket reconnect).
export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: [['list']],
    timeout: 120_000,
    use: {
        baseURL: 'http://localhost:5173',
        // Cold dev-server loads transform the full module graph on demand
        // (MUI + recharts under container CPU) — the default 30s per-test
        // timeout loses that race on first run; warm runs are fast.
        trace: 'on-first-retry',
        actionTimeout: 15_000,
    },
    projects: [
        { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
        { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
        { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    ],
    webServer: {
        command: 'npm run dev -- --port 5173 --strictPort',
        url: 'http://localhost:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
    },
});
