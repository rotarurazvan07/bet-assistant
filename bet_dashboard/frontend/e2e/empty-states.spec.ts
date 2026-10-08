// Actionable empty states (issue #46 AC-10).
// THIS STORY IS THE EXPLICIT DEMO-DATA EXCEPTION.
// Do NOT call installDemoApi. Do NOT import DEMO_MATCHES.
// Discover/Build are forced empty via the narrow beforeEach mocks below —
// needed locally (Vite 502s) AND in CI, where the stack serves seeded demo
// matches (setup/seed_e2e.py). Track stays genuinely empty in CI (fresh
// slips.db). Analytics empty needs stats:null. Services empty needs
// generator.enabled:false.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page }) => {
    await suppressTour(page);
    // Pathname-only matchers: globs like **/api/matches* steal Vite /src/api/*.ts.
    await page.route((url) => url.pathname === '/api/matches', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ total: 0, page: 1, page_size: 20, total_pages: 1, matches: [] }),
        });
    });
    await page.route((url) => url.pathname === '/api/builder/preview', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ total_odds: 1, pending_urls: [], legs: [] }),
        });
    });
    page.on('pageerror', (err) => {
        if (!String(err).includes('AxiosError')) throw err;
    });
});

async function mockAnalyticsEmpty(page: import('@playwright/test').Page) {
    await page.route('**/api/analytics**', async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: 'null' });
    });
}

async function mockServicesGeneratorOff(page: import('@playwright/test').Page) {
    await page.route('**/api/services**', async (route) => {
        if (route.request().method() !== 'GET') {
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ name: 'generator', enabled: true }) });
            return;
        }
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                services: {
                    puller: { name: 'puller', description: 'pull', enabled: true, alive: true },
                    generator: { name: 'generator', description: 'gen', enabled: false, alive: false },
                    verifier: { name: 'verifier', description: 'verify', enabled: true, alive: true },
                },
                generate_hour: 9,
                generate_minute: 0,
                server_time: '2026-09-24T12:00:00',
            }),
        });
    });
}

test('Discover empty CTAs: Pull posts /api/pull and Adjust Filters opens drawer', async ({ page }) => {
    let pulled = 0;
    await page.route('**/api/pull', async (route) => {
        pulled += 1;
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', timestamp: '2026-09-24T12:00:00' }) });
    });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Discover' })).toBeVisible();
    await expect(page.locator('[data-empty-state]')).toBeVisible();
    await page.getByRole('button', { name: 'Pull Update Now' }).click();
    await expect.poll(() => pulled).toBe(1);
    await page.getByRole('button', { name: 'Adjust Filters' }).click();
    await expect(page.getByRole('heading', { name: 'Filters' })).toBeVisible();
});

test('Build empty CTAs stay on /builder', async ({ page }) => {
    await page.goto('/builder');
    await expect(page.getByRole('heading', { name: 'Build' })).toBeVisible();
    await expect(page.getByText('No preview yet')).toBeVisible();
    await page.getByRole('button', { name: 'Select a Preset' }).click();
    await expect(page).toHaveURL(/\/builder/);
    await page.getByRole('region', { name: 'No preview yet' }).getByRole('button', { name: 'Add to Slips', exact: true }).click();
    await expect(page.getByText('No legs in preview.')).toBeVisible();
});

test('Track empty CTAs: Generate posts and Go to Build navigates', async ({ page }) => {
    let generated = 0;
    await page.route('**/api/slips/generate', async (route) => {
        generated += 1;
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ generated: 0, by_profile: {} }) });
    });
    await page.goto('/slips');
    await expect(page.getByRole('heading', { name: 'Track' })).toBeVisible();
    await expect(page.getByText('No slips yet')).toBeVisible();
    await page.getByRole('region', { name: 'No slips yet' }).getByRole('button', { name: 'Generate Slips', exact: true }).click();
    await expect.poll(() => generated).toBe(1);
    await page.getByRole('button', { name: 'Go to Build' }).click();
    await expect(page).toHaveURL(/\/builder/);
});

test('Analytics empty CTAs navigate to Track and Build', async ({ page }) => {
    await mockAnalyticsEmpty(page);
    await page.goto('/analytics');
    await expect(page.getByText('No analytics yet')).toBeVisible();
    await page.getByRole('button', { name: 'Go to Track' }).click();
    await expect(page).toHaveURL(/\/slips/);
    await mockAnalyticsEmpty(page);
    await page.goto('/analytics');
    await page.getByRole('button', { name: 'Go to Build' }).click();
    await expect(page).toHaveURL(/\/builder/);
});

test('Services empty CTAs enable generator and save', async ({ page }) => {
    let toggled = 0;
    let saved = 0;
    await mockServicesGeneratorOff(page);
    await page.route('**/api/services/generator/toggle', async (route) => {
        toggled += 1;
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ name: 'generator', enabled: true }) });
    });
    await page.route('**/api/services/settings', async (route) => {
        saved += 1;
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
    });
    await page.goto('/services');
    await expect(page.getByText('Generate Slips is off')).toBeVisible();
    await page.getByRole('button', { name: 'Enable Generate Slips' }).click();
    await expect.poll(() => toggled).toBe(1);
    await page.getByRole('region', { name: 'Generate Slips is off' }).getByRole('button', { name: 'Save Settings' }).click();
    await expect.poll(() => saved).toBe(1);
});

test('EmptyState regions pass axe-core', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('[data-empty-state]')).toBeVisible();
    const discover = await new AxeBuilder({ page }).include('[data-empty-state]').analyze();
    expect(discover.violations).toEqual([]);
});
