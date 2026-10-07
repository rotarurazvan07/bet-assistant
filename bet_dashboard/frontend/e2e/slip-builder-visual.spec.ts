// Visual baselines (issue #39 AC-12). Chromium-only, local-only.
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
});

const mask = (page: import('@playwright/test').Page) => ({
    mask: [page.locator('header .font-mono')],
});

test.describe('floating slip builder @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('expanded panel', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('.floating-slip-panel')).toBeVisible();
        await expect(page.locator('.floating-slip-panel')).toHaveScreenshot('slip-desktop-expanded.png', mask(page));
    });
});

test.describe('floating slip builder @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('sheet 50%', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('.floating-slip-panel')).toBeVisible();
        await expect(page.locator('.floating-slip-panel')).toHaveScreenshot('slip-mobile-50.png');
    });

    test('sheet 90%', async ({ page }) => {
        await page.goto('/');
        await page.getByRole('button', { name: 'Resize slip sheet' }).click();
        await expect(page.locator('.floating-slip-panel')).toHaveScreenshot('slip-mobile-90.png');
    });
});