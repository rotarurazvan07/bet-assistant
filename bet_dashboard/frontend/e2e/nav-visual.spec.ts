// Visual regression (issue #36 AC-07): header nav baselines — desktop 1280x800
// + mobile 375x667, per key state (default + active-tab per group).
// Ponytail calls:
// - chromium-only: one baseline set; cross-engine pixel diffs are noise.
// - skipped in CI (E2E_BASE_URL set): baselines are host-rendering-sensitive
//   (container fonts); generate/verify locally, commit snapshots. CI keeps
//   the deterministic landing.spec.ts nav assertions as its blocking gate.
// - header-locator screenshots: page content below the header is backend-
//   dependent (loading/error states) and would flake baselines needlessly.

import { test, expect } from '@playwright/test';
import { suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
    await suppressTour(page);
});

// Desktop 1280x800 — mask the lastPull timestamp (backend-dependent text).
test.describe('nav header @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });
    const maskOpts = (page: import('@playwright/test').Page) => ({
        mask: [page.locator('header .font-mono')],
    });

    test('header default state (Discover active)', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('header')).toHaveScreenshot('header-desktop-default.png', maskOpts(page));
    });

    test('header with Analytics active (Insights group)', async ({ page }) => {
        await page.goto('/analytics');
        await expect(page.locator('header')).toHaveScreenshot('header-desktop-analytics.png', maskOpts(page));
    });

    test('header with Services active (System group)', async ({ page }) => {
        await page.goto('/services');
        await expect(page.locator('header')).toHaveScreenshot('header-desktop-services.png', maskOpts(page));
    });
});

// Mobile 375x667 — capture current behavior as-is (SM Q3: no hamburger in
// this story; Workstream E decides mobile nav). lastPull span is hidden md:block.
test.describe('nav header @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('header default state', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('header')).toHaveScreenshot('header-mobile-default.png');
    });

    test('header with Analytics active', async ({ page }) => {
        await page.goto('/analytics');
        await expect(page.locator('header')).toHaveScreenshot('header-mobile-analytics.png');
    });
});
