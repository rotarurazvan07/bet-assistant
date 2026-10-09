// Two-track demo data: local Playwright MUST call installDemoApi; CI uses
// setup/seed_e2e.py. Expand BOTH when a new surface needs data (same rows).
// Exception: explicit empty-state specs. Skip this helper when E2E_BASE_URL.
// Pathname matchers only — globs like **/api/matches* also steal Vite /src/api/*.ts.
import type { Page } from '@playwright/test';
import type { SlipsPage, ProfilesMap } from '../../src/types';
import { DEMO_MATCHES, DEMO_MATCHES_PAGE } from './demo-data';

function apiPath(pathname: string, exact: string): boolean {
    return pathname === exact || pathname.startsWith(`${exact}/`);
}

export type DemoApiOpts = {
    slips?: SlipsPage;
    profiles?: ProfilesMap;
};

export async function installDemoApi(page: Page, opts: DemoApiOpts = {}): Promise<void> {
    const slipsGet = opts.slips ?? { slips: [], stats: null, profiles: [] };
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
        const body = method === 'GET' ? slipsGet : { slip_id: 1 };
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
    if (opts.profiles) {
        await page.route((url) => url.pathname === '/api/profiles', async (route) => {
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ profiles: opts.profiles }),
            });
        });
    }
}

/** AC-09: existing specs must not see first-visit tour. */
export async function suppressTour(page: Page): Promise<void> {
    await page.addInitScript(() => {
        try {
            localStorage.setItem('bet-assistant-tour-done', '1');
        } catch {
            // ignore
        }
    });
}
