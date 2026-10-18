// Two-track demo data: local Playwright MUST call installDemoApi; CI uses
// setup/seed_e2e.py. Expand BOTH when a new surface needs data (same rows).
// Exception: explicit empty-state specs. Skip this helper when E2E_BASE_URL.
// Pathname matchers only — globs like **/api/matches* also steal Vite /src/api/*.ts.
import type { Page } from '@playwright/test';
import type { SlipsPage, ProfilesMap } from '../../src/types';
import { DEMO_MATCHES, DEMO_MATCHES_PAGE, DEMO_PREVIEW, DEMO_PROFILES, DEMO_PROFILE_SCHEDULES } from './demo-data';

function apiPath(pathname: string, exact: string): boolean {
    return pathname === exact || pathname.startsWith(`${exact}/`);
}

export type DemoApiOpts = {
    slips?: SlipsPage;
    profiles?: ProfilesMap;
};

export async function installDemoApi(page: Page, opts: DemoApiOpts = {}): Promise<void> {
    const slipsGet = opts.slips ?? { slips: [], stats: null, profiles: [] };
    const preview = opts.preview ?? DEMO_PREVIEW;
    // Smart Builder live preview (two-track: DEMO_PREVIEW mirrors a real /api/preview response).
    await page.route((url) => apiPath(url.pathname, '/api/preview'), async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(preview),
        });
    });
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
    await page.route((url) => url.pathname === '/api/services', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                services: {
                    puller: { name: 'puller', description: 'Checks every 5 minutes', enabled: false, alive: false, hour: null, minute: null, interval_seconds: 300, next_run: 'Every 5 min', last_time_generated: null },
                    generator: { name: 'generator', description: 'Checks every 5 minutes', enabled: true, alive: true, hour: 9, minute: 0, interval_seconds: 300, next_run: 'Today 09:00 (in 1h 0m)', last_time_generated: null },
                    verifier: { name: 'verifier', description: 'Polls every 60 seconds', enabled: true, alive: true, hour: null, minute: null, interval_seconds: 60, next_run: 'Every 1 min', last_time_generated: null },
                },
                generate_hour: 9,
                generate_minute: 0,
                server_time: '2026-10-07T10:00:00',
                profile_schedules: DEMO_PROFILE_SCHEDULES,
            }),
        });
    });
    await page.route((url) => url.pathname === '/api/profiles', async (route) => {
        if (route.request().method() === 'POST') {
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ name: 'ok' }) });
            return;
        }
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ profiles: opts.profiles ?? DEMO_PROFILES }),
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
