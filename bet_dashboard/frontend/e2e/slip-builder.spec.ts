// Floating slip builder E2E + keyboard + axe (issue #39 AC-11).
// Local dev has no backend: the match table is empty, so we exercise the
// empty-slip chrome + keyboard no-op paths. Filters AxiosError noise like
// #36/#37.
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.beforeEach(async ({ page }) => {
    page.on('pageerror', (err) => {
        if (!String(err).includes('AxiosError')) throw err;
    });
});

test('desktop: expanded floating panel is visible and keyboard-guarded', async ({ page }) => {
    await page.goto('/');
    const panel = page.locator('.floating-slip-panel');
    await expect(panel).toBeVisible();
    // No legs in a local empty env — Ctrl+Enter must no-op cleanly (panel stays).
    await page.keyboard.press('Control+Enter');
    await expect(panel).toBeVisible();
    // Escape minimizes the panel to the pill.
    const dialog = page.getByRole('dialog', { name: 'Slip Builder' });
    await dialog.focus();
    await page.keyboard.press('Tab');
    const focused = page.locator(':focus');
    await expect(focused).toHaveCount(1);
    await expect(dialog.locator(':focus')).toHaveCount(1);
    await page.keyboard.press('Escape');
    await expect(panel).toHaveCount(0);
    await expect(page.locator('.floating-slip-minimized')).toBeVisible();
});

test('desktop: panel passes axe-core', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.floating-slip-panel')).toBeVisible();
    const results = await new AxeBuilder({ page }).include('[data-slip-panel]').analyze();
    expect(results.violations).toEqual([]);
});

test.describe('mobile bottom sheet 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('sheet + drag handle render; handle toggles snap', async ({ page }) => {
        await page.goto('/');
        const sheet = page.locator('.floating-slip-panel');
        await expect(sheet).toBeVisible();
        const handle = page.getByRole('button', { name: 'Resize slip sheet' });
        await expect(handle).toBeVisible();
        const before = await sheet.boundingBox();
        await handle.click();
        await expect.poll(async () => (await sheet.boundingBox())?.height ?? 0).toBeGreaterThan((before?.height ?? 0) + 80);
    });

    test('minimized pill is keyboard-reachable and expands', async ({ page }) => {
        await page.goto('/');
        await page.keyboard.press('Escape');
        const pill = page.locator('.floating-slip-minimized');
        await expect(pill).toBeVisible();
        await pill.focus();
        await page.keyboard.press('Enter');
        await expect(page.locator('.floating-slip-panel')).toBeVisible();
    });
});