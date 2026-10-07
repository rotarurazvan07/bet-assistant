// page.route demo API for local Playwright (Vite, no backend). Not used when E2E_BASE_URL is set.
// Pathname matchers only — globs like **/api/matches* also steal Vite /src/api/*.ts.
import type { Page } from '@playwright/test';
import { DEMO_MATCHES, DEMO_MATCHES_PAGE } from './demo-data';

function apiPath(pathname: string, exact: string): boolean {
    return pathname === exact || pathname.startsWith(`${exact}/`);
}

export async function installDemoApi(page: Page): Promise<void> {
    await page.route((url) => apiPath(url.pathname, '/api/matches'), async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(DEMO_MATCHES_PAGE),
        });
    });
    await page.route((url) => apiPath(url.pathname, '/api/odds-history/movements/all'), async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: '{}',
        });
    });
    await page.route((url) => url.pathname === '/api/slips', async (route) => {
        const method = route.request().method();
        const body =
            method === 'GET'
                ? { slips: [], stats: null, profiles: [] }
                : { slip_id: 1 };
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(body),
        });
    });
    await page.route((url) => apiPath(url.pathname, '/api/config/sources'), async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ sources: ['forebet', 'predictz', 'scorepredictor'] }),
        });
    });
    await page.route((url) => apiPath(url.pathname, '/api/status'), async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                last_pull: '2026-10-07T10:00:00',
                matches_loaded: DEMO_MATCHES.length,
            }),
        });
    });
}
