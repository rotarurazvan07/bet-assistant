// Empty-state visual baselines (issue #46 AC-10).
// THIS STORY IS THE EXPLICIT DEMO-DATA EXCEPTION.
// Do NOT call installDemoApi. Do NOT import DEMO_MATCHES.
// Chromium-only. Skip when E2E_BASE_URL (CI docker may have real data).
// Mask header .font-mono (lastPull). Viewports 1280x800 + 375x667.
import { test, expect, type Page } from '@playwright/test';

test.beforeEach(async ({ browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack may have real data)');
});

const mask = (page: Page) => ({
    mask: [page.locator('header .font-mono')],
});

async function mockAnalyticsEmpty(page: Page) {
    await page.route('**/api/analytics**', async (route) => {
        await route.fulfill({ status: 200, contentType: 'application/json', body: 'null' });
    });
}

async function mockServicesGeneratorOff(page: Page) {
    await page.route('**/api/services**', async (route) => {
        if (route.request().method() !== 'GET') {
            await route.continue();
            return;
        }
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                services: {
                    puller: { name: 'puller', description: 'pull', enabled: true, alive: true },
                    generator: { name: 'generator', description: 'gen', enabled: false, alive: false },
                    verifier: { name: 'verifier', description: 'verify', enabled: true, alive: true },
                },
                generate_hour: 9,
                generate_minute: 0,
                server_time: '2026-09-24T12:00:00',
            }),
        });
    });
}

async function waitEmpty(page: Page) {
    await expect(page.locator('[data-empty-state]')).toBeVisible();
}

test.describe('empty states @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('Discover empty', async ({ page }) => {
        await page.goto('/');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-discover-desktop.png', mask(page));
    });

    test('Build empty', async ({ page }) => {
        await page.goto('/builder');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-build-desktop.png', mask(page));
    });

    test('Track empty', async ({ page }) => {
        await page.goto('/slips');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-track-desktop.png', mask(page));
    });

    test('Analytics empty', async ({ page }) => {
        await mockAnalyticsEmpty(page);
        await page.goto('/analytics');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-analytics-desktop.png', mask(page));
    });

    test('Services empty', async ({ page }) => {
        await mockServicesGeneratorOff(page);
        await page.goto('/services');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-services-desktop.png', mask(page));
    });
});

test.describe('empty states @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('Discover empty', async ({ page }) => {
        await page.goto('/');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-discover-mobile.png', mask(page));
    });

    test('Build empty', async ({ page }) => {
        await page.goto('/builder');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-build-mobile.png', mask(page));
    });

    test('Track empty', async ({ page }) => {
        await page.goto('/slips');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-track-mobile.png', mask(page));
    });

    test('Analytics empty', async ({ page }) => {
        await mockAnalyticsEmpty(page);
        await page.goto('/analytics');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-analytics-mobile.png', mask(page));
    });

    test('Services empty', async ({ page }) => {
        await mockServicesGeneratorOff(page);
        await page.goto('/services');
        await waitEmpty(page);
        await expect(page).toHaveScreenshot('empty-services-mobile.png', mask(page));
    });
});
