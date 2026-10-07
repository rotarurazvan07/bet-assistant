// Visual baselines (issue #38 AC-10). Chromium-only, local-only.
// installDemoApi required. Do not screenshot mid-flight fly clone.
import { test, expect, type Page } from '@playwright/test';
import { installDemoApi } from './fixtures/mock-api';

test.beforeEach(async ({ browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
});

const mask = (page: Page) => ({
    mask: [page.locator('header .font-mono')],
});

async function addDemoHome(page: Page): Promise<void> {
    await installDemoApi(page);
    await page.goto('/');
    await expect(page.getByText('Arsenal')).toBeVisible();
    const cell = page.getByRole('button', { name: /Select 75% at @1\.90/ }).first();
    await cell.scrollIntoViewIfNeeded();
    await cell.click();
    await expect(page.getByRole('alert')).toHaveText('Added 1 @1.90 to slip');
}

test.describe('leg-add feedback @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('toast + in-slip cell + panel', async ({ page }) => {
        await addDemoHome(page);
        await expect(page).toHaveScreenshot('leg-add-desktop-toast.png', mask(page));
    });
});

test.describe('leg-add feedback @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('top toast above sheet', async ({ page }) => {
        await addDemoHome(page);
        await expect(page).toHaveScreenshot('leg-add-mobile-toast.png', mask(page));
    });
});
