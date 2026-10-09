// Visual baselines (issue #39 AC-12). Chromium-only, local-only.
// Local Vite has no backend — installDemoApi serves 2–3 factory matches so
// the table + populated slip are in the shot. Skipped when E2E_BASE_URL (CI).
import { test, expect, type Page } from '@playwright/test';
import { installDemoApi, suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
    await suppressTour(page);
});

const mask = (page: Page) => ({
    mask: [page.locator('header .font-mono')],
});

async function openPopulatedDiscover(page: Page): Promise<void> {
    await installDemoApi(page);
    await page.goto('/');
    await expect(page.getByText('Arsenal')).toBeVisible();
    const cell = page.getByRole('button', { name: /Select 75% at @1\.90/ }).first();
    await cell.scrollIntoViewIfNeeded();
    await cell.click();
    await expect(page.getByText('1 leg selected')).toBeVisible();
    await expect(page.getByText('No legs selected.')).toHaveCount(0);
    // #38 toast / pulse must not leak into #39 baselines.
    const toast = page.getByRole('alert');
    if (await toast.count()) {
        await toast.getByRole('button', { name: /close/i }).click();
        await expect(toast).toHaveCount(0);
    }
    // Wait for React-owned pulse (300ms) + fly clone; do not classList.remove (React re-adds).
    await expect(page.locator('.leg-fly-clone')).toHaveCount(0);
    await expect(page.locator('.slip-chrome-pulse-a, .slip-chrome-pulse-b, .market-cell-pulse')).toHaveCount(0);
}

test.describe('floating slip builder @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('expanded panel', async ({ page }) => {
        await openPopulatedDiscover(page);
        await expect(page.locator('.floating-slip-panel')).toBeVisible();
        await expect(page.locator('.floating-slip-panel')).toHaveScreenshot('slip-desktop-expanded.png', mask(page));
    });

    test('full viewport with matches + populated slip', async ({ page }) => {
        await openPopulatedDiscover(page);
        await expect(page).toHaveScreenshot('slip-desktop-full.png', { ...mask(page), maxDiffPixels: 500 });
    });
});

test.describe('floating slip builder @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('sheet 50%', async ({ page }) => {
        await openPopulatedDiscover(page);
        await expect(page.locator('.floating-slip-panel')).toBeVisible();
        await expect(page.locator('.floating-slip-panel')).toHaveScreenshot('slip-mobile-50.png');
    });

    test('sheet 90%', async ({ page }) => {
        await openPopulatedDiscover(page);
        await page.getByRole('button', { name: 'Resize slip sheet' }).click();
        // AC-12: Restart Tour wraps the 375px header (Workstream E). Do not recapture #39.
        await expect(page.locator('.floating-slip-panel')).toHaveScreenshot('slip-mobile-90.png', { maxDiffPixels: 300 });
    });

    test('full viewport sheet 50% with table peek', async ({ page }) => {
        await openPopulatedDiscover(page);
        await expect(page).toHaveScreenshot('slip-mobile-50-full.png', { ...mask(page), maxDiffPixels: 300 });
    });

    test('full viewport sheet 90% populated', async ({ page }) => {
        await openPopulatedDiscover(page);
        await page.getByRole('button', { name: 'Resize slip sheet' }).click();
        await expect(page).toHaveScreenshot('slip-mobile-90-full.png', mask(page));
    });
});
