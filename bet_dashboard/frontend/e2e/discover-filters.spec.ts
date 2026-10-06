// Discover filters drawer (issue #37 AC-09 / AC-11).
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('Discover shows Filters button and hides inline search', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: /^filters$/i })).toBeVisible();
    await expect(page.getByPlaceholder('Filter by team...')).toHaveCount(0);
});

test('Filters drawer opens Basic, Advanced toggle, Escape closes', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /^filters$/i }).click();
    await expect(page.getByPlaceholder('Filter by team...')).toBeVisible();
    await expect(page.getByRole('slider', { name: 'Min Consensus' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Sources' })).toHaveCount(0);
    await page.getByRole('button', { name: /advanced/i }).click();
    await expect(page.getByRole('heading', { name: 'Sources' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByPlaceholder('Filter by team...')).toHaveCount(0);
});

test('open drawer passes axe-core', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /^filters$/i }).click();
    await expect(page.getByPlaceholder('Filter by team...')).toBeVisible();
    const results = await new AxeBuilder({ page }).include('#discover-filters-drawer').analyze();
    expect(results.violations).toEqual([]);
});

test.describe('mobile bottom sheet', () => {
    test.use({ viewport: { width: 375, height: 667 } });
    test('Filters opens a bottom sheet', async ({ page }) => {
        await page.goto('/');
        await page.getByRole('button', { name: /^filters$/i }).click();
        await expect(page.getByPlaceholder('Filter by team...')).toBeVisible();
    });
});
