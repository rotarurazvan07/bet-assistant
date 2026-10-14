// Workstream B visual baseline: per-profile auto-generation scheduler panel.
import { test, expect } from '@playwright/test';
import { installDemoApi, suppressTour } from './fixtures/mock-api';


test.beforeEach(async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
    await suppressTour(page);
    await installDemoApi(page);
});


test.describe('services scheduler visual @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('per-profile scheduler panel with three rows', async ({ page }) => {
        await page.goto('/services');
        await expect(page.getByText('Per-profile Auto-Generation')).toBeVisible();
        await expect(page.getByRole('switch', { name: 'Auto-generate low' })).toBeVisible();
        await expect(page.locator('[data-testid="profile-scheduler"]')).toHaveScreenshot('services-scheduler.png', {
            mask: [page.locator('header .font-mono')],
        });
    });
});
