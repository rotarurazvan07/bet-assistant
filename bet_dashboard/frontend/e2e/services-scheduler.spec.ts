// Workstream B Part D: per-profile auto-generation scheduler on Services —
// rows per saved profile, hour/minute selects, units/payout inputs, live next
// run, single Save POSTs the profiles map; axe-core on the scheduler table.
import { test, expect } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';
import { installDemoApi, suppressTour } from './fixtures/mock-api';


test.beforeEach(async ({ page }) => {
    await suppressTour(page);
    // Two-track rule: CI (E2E_BASE_URL set) uses the seeded docker stack; only
    // the local Vite run gets the mock API.
    if (!process.env.E2E_BASE_URL) await installDemoApi(page);
    await page.goto('/services');
    await expect(page.getByText('Per-profile Auto-Generation')).toBeVisible();
    // AppReady: the scheduler table renders only after BOTH GET /api/profiles
    // and GET /api/services resolve. On the CI stack the heading paints before
    // those responses land, and the FIRST browser's cold round-trip (uvicorn
    // lazily importing its heavy deps on first router hit) can exceed the
    // default 5s action timeout - chromium runs first with workers:1, which is
    // why this gate failed there while later warm browsers passed. Gate on the
    // rendered row with a budget that covers the cold first response.
    await expect(page.getByRole('switch', { name: 'Auto-generate low' })).toBeVisible({ timeout: 30000 });
});


test.describe('services per-profile scheduler @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('one row per saved profile with controls and next-run', async ({ page }) => {
        for (const name of ['low', 'medium', 'high_risk']) {
            await expect(page.getByRole('switch', { name: `Auto-generate ${name}` })).toBeVisible();
            await expect(page.getByRole('combobox', { name: `${name} hour` })).toBeVisible();
            await expect(page.getByRole('spinbutton', { name: `${name} units` })).toBeVisible();
        }
        // Clock-tolerant: the backend computes "Today/Tomorrow HH:MM (in Xh YYm)"
        // from the server's own clock, so a fixed delta string is flaky by design.
        await expect(page.getByText(/^(Today|Tomorrow) 09:30 \(in \d+h \d{2}m\)$/)).toBeVisible();
        await expect(page.getByText('Disabled')).toHaveCount(2);
        // MUI StaticTimePicker is gone (#51 silently satisfied)
        await expect(page.locator('.MuiClock-root')).toHaveCount(0);
    });

    test('Save persists all rows in one POST carrying the profiles map', async ({ page }) => {
        let posted: Record<string, unknown> | null = null;
        await page.route((url) => url.pathname === '/api/services/settings', async (route) => {
            posted = route.request().postDataJSON() as Record<string, unknown>;
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
        });
        // Row state can be rebuilt by load() (post-save refetch); wait for the
        // row's switch before interacting so a rebuild cannot eat the click.
        await expect(page.getByRole('switch', { name: 'Auto-generate medium' })).toBeVisible({ timeout: 15000 });
        await page.getByRole('switch', { name: 'Auto-generate medium' }).click();
        await page.getByRole('combobox', { name: 'medium hour' }).selectOption('7');
        // The scheduler owns the profiles map: scope the save to it so the
        // generator-off empty state (seeded stack parks the toggle off) can
        // never make this an ambiguous 'Save Settings' match.
        await page.getByTestId('profile-scheduler').getByRole('button', { name: 'Save Settings' }).click();
        await expect(page.getByText(/Schedules saved/)).toBeVisible();
        const profiles = (posted?.profiles ?? {}) as Record<string, { enabled: boolean; hour: number; units: number; target_payout: number | null }>;
        expect(Object.keys(profiles).sort()).toEqual(['high_risk', 'low', 'medium']);
        expect(profiles.low.enabled).toBe(true);
        expect(profiles.medium.enabled).toBe(true);
        expect(profiles.medium.hour).toBe(7);
        expect(profiles.low.units).toBe(2.5);
        expect(profiles.low.target_payout).toBe(100);
    });

    test('scheduler table passes axe-core (Workstream B a11y gate)', async ({ page }) => {
        const results = await new AxeBuilder({ page })
            .include('[data-testid="profile-scheduler"]')
            .analyze();
        expect(results.violations).toEqual([]);
    });
});
