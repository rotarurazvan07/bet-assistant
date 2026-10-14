// Workstream B visual baselines: reworked builder sidebar — desktop 1280x800
// and mobile 375x667. Chromium-only, local-only (CI stack fonts differ).
import { test, expect, type Page } from '@playwright/test';
import { installDemoApi, suppressTour } from './fixtures/mock-api';


test.beforeEach(async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
    await suppressTour(page);
    await installDemoApi(page);
});


async function openSidebar(page: Page): Promise<void> {
    await page.goto('/builder');
    await expect(page.getByRole('button', { name: /Core Targets/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Selection Logic/ })).toBeVisible();
}


test.describe('builder sidebar visual @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('sidebar with five groups collapsed', async ({ page }) => {
        await openSidebar(page);
        const sidebar = page.locator('.xl\\:w-\\[350px\\]');
        await expect(sidebar).toHaveScreenshot('builder-sidebar-desktop.png', {
            mask: [page.locator('header .font-mono')],
        });
    });
});

test.describe('builder sidebar visual @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('sidebar stacks above content at 375px', async ({ page }) => {
        await openSidebar(page);
        const sidebar = page.locator('.xl\\:w-\\[350px\\]');
        await expect(sidebar).toHaveScreenshot('builder-sidebar-mobile.png', {
            mask: [page.locator('header .font-mono')],
        });
    });
});
