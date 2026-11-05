// Two-track demo data: local Playwright MUST call installDemoApi; CI uses
// setup/seed_e2e.py. Expand BOTH when a new surface needs data (same rows).
// Exception: explicit empty-state specs. Skip this helper when E2E_BASE_URL.
// Pathname matchers only — globs like **/api/matches* also steal Vite /src/api/*.ts.
import type { Page } from '@playwright/test';
import type { SlipCalendarData, SlipsPage, ProfilesMap } from '../../src/types';
import { DEMO_MATCHES, DEMO_MATCHES_PAGE, DEMO_PREVIEW, DEMO_PROFILES, DEMO_PROFILE_SCHEDULES } from './demo-data';

function apiPath(pathname: string, exact: string): boolean {
    return pathname === exact || pathname.startsWith(`${exact}/`);
}

export type DemoApiOpts = {
    slips?: SlipsPage;
    calendar?: SlipCalendarData;
    profiles?: ProfilesMap;
};

export async function installDemoApi(page: Page, opts: DemoApiOpts = {}): Promise<void> {
    const slipsGet = opts.slips ?? { slips: [], profiles: [], page: 1, page_size: 20, total: 0, total_pages: 1 };
    const preview = opts.preview ?? DEMO_PREVIEW;
    // Smart Builder live preview (two-track: DEMO_PREVIEW mirrors a real /api/builder/preview response — the client posts to /builder/preview).
    await page.route((url) => apiPath(url.pathname, '/api/builder/preview'), async (route) => {
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
    await page.route((url) => url.pathname === '/api/slips/calendar', async (route) => {
        const query = new URL(route.request().url()).searchParams;
        const from = query.get('date_from') ?? '';
        const to = query.get('date_to') ?? '';
        const selectedProfiles = query.getAll('profiles[]');
        const days = (opts.calendar?.days ?? []).filter(day =>
            day.date >= from
            && day.date <= to
            && (selectedProfiles.length === 0 || selectedProfiles.includes('low')),
        );
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ days }),
        });
    });
    await page.route((url) => url.pathname === '/api/slips', async (route) => {
        const method = route.request().method();
        let body: unknown = { slip_id: 1 };
        if (method === 'GET') {
            const query = new URL(route.request().url()).searchParams;
            const from = query.get('date_from');
            const to = query.get('date_to');
            const start = Number(query.get('page') ?? 1);
            const pageSize = Number(query.get('page_size') ?? 20);
            const filtered = slipsGet.slips.filter(slip =>
                (!from || slip.date_generated.slice(0, 10) >= from)
                && (!to || slip.date_generated.slice(0, 10) <= to),
            );
            body = {
                ...slipsGet,
                slips: filtered.slice((start - 1) * pageSize, start * pageSize),
                page: start,
                page_size: pageSize,
                total: filtered.length,
                total_pages: Math.max(1, Math.ceil(filtered.length / pageSize)),
            };
        }
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
    await page.route((url) => apiPath(url.pathname, '/api/config/timezone'), async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ timezone: 'UTC' }),
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
                    generator: { name: 'generator', description: 'Checks every 5 minutes', enabled: true, alive: true, hour: 8, minute: 30, interval_seconds: 300, next_run: 'Tomorrow 08:30 (in 22h 30m)', last_time_generated: null },
                    verifier: { name: 'verifier', description: 'Polls every 60 seconds', enabled: true, alive: true, hour: null, minute: null, interval_seconds: 60, next_run: 'Every 1 min', last_time_generated: null },
                },
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

/** existing specs must not see first-visit tour. */
export async function suppressTour(page: Page): Promise<void> {
    await page.addInitScript(() => {
        try {
            localStorage.setItem('bet-assistant-tour-done', '1');
        } catch {
            // ignore
        }
    });
}
