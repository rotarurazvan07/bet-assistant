// Visual baselines (issue #37 AC-10). Chromium-only, local-only.
import { test, expect } from '@playwright/test';
import { suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
    await suppressTour(page);
});

const mask = (page: import('@playwright/test').Page) => ({
    mask: [page.locator('header .font-mono')],
});

test.describe('discover filters @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('drawer closed', async ({ page }) => {
        await page.goto('/');
        await expect(page).toHaveScreenshot('discover-desktop-closed.png', mask(page));
    });

    test('drawer open Basic', async ({ page }) => {
        await page.goto('/');
        await page.getByRole('button', { name: /^filters$/i }).click();
        await expect(page.getByPlaceholder('Filter by team...')).toBeVisible();
        await expect(page).toHaveScreenshot('discover-desktop-basic.png', mask(page));
    });

    test('drawer open Advanced', async ({ page }) => {
        await page.goto('/');
        await page.getByRole('button', { name: /^filters$/i }).click();
        await page.getByRole('button', { name: /advanced/i }).click();
        await expect(page.getByRole('heading', { name: 'Sources' })).toBeVisible();
        await expect(page).toHaveScreenshot('discover-desktop-advanced.png', mask(page));
    });
});

test.describe('discover filters @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('sheet closed', async ({ page }) => {
        await page.goto('/');
        await expect(page).toHaveScreenshot('discover-mobile-closed.png');
    });

    test('sheet open', async ({ page }) => {
        await page.goto('/');
        await page.getByRole('button', { name: /^filters$/i }).click();
        await expect(page.getByPlaceholder('Filter by team...')).toBeVisible();
        await expect(page).toHaveScreenshot('discover-mobile-open.png');
    });
});
