// Onboarding tour + first-slip milestone (issue #50 AC-11).
// Do NOT use default suppressTour. Clear tour key before goto.
// installDemoApi + slips/profiles override. Pathname-only routes.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { installDemoApi } from './fixtures/mock-api';
import { DEMO_PROFILES, DEMO_SLIPS_PAGE } from './fixtures/demo-data';

test.beforeEach(async ({ page }) => {
    page.on('pageerror', (err) => {
        if (!String(err).includes('AxiosError')) throw err;
    });
    await page.addInitScript(() => {
        try {
            // Once per tab: empty storage for first visit. Reload must keep Skip persist.
            if (!sessionStorage.getItem('tour-init-cleared')) {
                localStorage.removeItem('bet-assistant-tour-done');
                localStorage.removeItem('bet-assistant-first-slip-done');
                sessionStorage.setItem('tour-init-cleared', '1');
            }
        } catch {
            // ignore
        }
    });
    if (!process.env.E2E_BASE_URL) {
        await installDemoApi(page, { slips: DEMO_SLIPS_PAGE, profiles: DEMO_PROFILES });
    }
});

test('first visit shows step 0 on /', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toBeVisible();
});

test('Next walks / → /builder → /slips then Done persists', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page).toHaveURL(/\/builder/);
    await expect(page.getByRole('dialog', { name: 'Create your strategy' })).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(page).toHaveURL(/\/slips/);
    await expect(page.getByRole('dialog', { name: 'Monitor performance' })).toBeVisible();
    await page.getByRole('button', { name: 'Done' }).click();
    await expect(page.getByRole('dialog', { name: 'Monitor performance' })).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => localStorage.getItem('bet-assistant-tour-done'))).toBe('1');
});

test('Skip persists and reload stays dismissed', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Skip' }).click();
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toHaveCount(0);
});

test('Restart Tour returns to step 0 on /', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Skip' }).click();
    await page.getByRole('button', { name: 'Restart Tour' }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toBeVisible();
});

test('Esc skips the tour', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => localStorage.getItem('bet-assistant-tour-done'))).toBe('1');
});

test('Tab + Enter advances Next', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('dialog', { name: 'Find value bets' })).toBeVisible();
    await page.getByRole('button', { name: 'Next' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog', { name: 'Create your strategy' })).toBeVisible();
});

test('first Add Slip shows milestone once', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Skip' }).click();
    await expect(page.getByText('Arsenal')).toBeVisible();
    await page.getByRole('button', { name: /Select 75% at @1\.90/ }).first().click();
    await page.getByRole('button', { name: /Add Slip/i }).click();
    const alert = page.getByRole('alert').filter({ hasText: 'First slip submitted' });
    await expect(alert).toBeVisible();
    await expect(alert).toHaveCSS('opacity', '1');
    await page.getByRole('button', { name: /Select 42% at @2\.40/ }).first().click();
    await page.getByRole('button', { name: /Add Slip/i }).click();
    await expect(page.getByRole('alert').filter({ hasText: 'First slip submitted' })).toHaveCount(0);
});

test('tour dialog passes axe-core', async ({ page }) => {
    await page.goto('/');
    const dialog = page.getByRole('dialog', { name: 'Find value bets' });
    await expect(dialog).toBeVisible();
    const results = await new AxeBuilder({ page }).include('[role="dialog"][aria-labelledby="tour-title"]').analyze();
    expect(results.violations).toEqual([]);
});
