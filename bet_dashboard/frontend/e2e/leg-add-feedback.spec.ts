// Add-leg pulse / fly-to / toast (issue #38 AC-10).
// Local Vite: installDemoApi paints Arsenal 75% @1.90. Skip mocks on CI stack.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { installDemoApi } from './fixtures/mock-api';

test.beforeEach(async ({ page }) => {
    page.on('pageerror', (err) => {
        if (!String(err).includes('AxiosError')) throw err;
    });
    if (!process.env.E2E_BASE_URL) await installDemoApi(page);
});

test('add shows toast Added 1 @1.90 to slip', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Arsenal')).toBeVisible();
    await page.getByRole('button', { name: /Select 75% at @1\.90/ }).first().click();
    await expect(page.getByRole('alert')).toHaveText('Added 1 @1.90 to slip');
});

test('toggle-off does not show a Removed toast', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Arsenal')).toBeVisible();
    const cell = page.getByRole('button', { name: /Select 75% at @1\.90/ }).first();
    await cell.click();
    await expect(page.getByRole('alert')).toBeVisible();
    await page.getByRole('button', { name: /close/i }).click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    await cell.click();
    await expect(page.getByText('0 legs selected')).toBeVisible();
    await expect(page.getByRole('alert')).toHaveCount(0);
});

test('reduced-motion still toasts without a fly clone', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await expect(page.getByText('Arsenal')).toBeVisible();
    await page.getByRole('button', { name: /Select 75% at @1\.90/ }).first().click();
    await expect(page.getByRole('alert')).toHaveText('Added 1 @1.90 to slip');
    await expect(page.locator('.leg-fly-clone')).toHaveCount(0);
});

test('toast and slip panel pass axe-core', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('[data-slip-panel]')).toBeVisible();
    const emptyPanel = await new AxeBuilder({ page }).include('[data-slip-panel]').analyze();
    expect(emptyPanel.violations).toEqual([]);
    await expect(page.getByText('Arsenal')).toBeVisible();
    await page.getByRole('button', { name: /Select 75% at @1\.90/ }).first().click();
    await expect(page.getByRole('alert')).toBeVisible();
    const toast = await new AxeBuilder({ page }).include('[role="alert"]').analyze();
    expect(toast.violations).toEqual([]);
});
