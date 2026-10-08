// Tour visual baselines (issue #50 AC-11). Chromium-only, local-only.
// installDemoApi + slips/profiles. Do NOT suppress tour. Mask lastPull.
import { test, expect, type Page } from '@playwright/test';
import { installDemoApi } from './fixtures/mock-api';
import { DEMO_PROFILES, DEMO_SLIPS_PAGE } from './fixtures/demo-data';

test.beforeEach(async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'visual baselines are chromium-only');
    test.skip(!!process.env.E2E_BASE_URL, 'visual baselines are local-only (CI stack fonts differ)');
    await page.addInitScript(() => {
        try {
            localStorage.removeItem('bet-assistant-tour-done');
            localStorage.removeItem('bet-assistant-first-slip-done');
        } catch {
            // ignore
        }
    });
    await installDemoApi(page, { slips: DEMO_SLIPS_PAGE, profiles: DEMO_PROFILES });
});

const mask = (page: Page) => ({
    mask: [page.locator('header .font-mono')],
});

async function waitStep(page: Page, title: string) {
    await expect(page.getByRole('dialog', { name: title })).toBeVisible();
}

test.describe('onboarding tour @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('step 0 Find value bets', async ({ page }) => {
        await page.goto('/');
        await waitStep(page, 'Find value bets');
        await expect(page.getByText('Arsenal')).toBeVisible();
        await expect(page).toHaveScreenshot('tour-step0-desktop.png', mask(page));
    });

    test('step 1 Create your strategy', async ({ page }) => {
        await page.goto('/');
        await waitStep(page, 'Find value bets');
        await page.getByRole('button', { name: 'Next' }).click();
        await waitStep(page, 'Create your strategy');
        await expect(page).toHaveScreenshot('tour-step1-desktop.png', mask(page));
    });

    test('step 2 Monitor performance', async ({ page }) => {
        await page.goto('/');
        await waitStep(page, 'Find value bets');
        await page.getByRole('button', { name: 'Next' }).click();
        await page.getByRole('button', { name: 'Next' }).click();
        await waitStep(page, 'Monitor performance');
        await expect(page).toHaveScreenshot('tour-step2-desktop.png', mask(page));
    });
});

test.describe('onboarding tour @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('step 0 Find value bets', async ({ page }) => {
        await page.goto('/');
        await waitStep(page, 'Find value bets');
        await expect(page).toHaveScreenshot('tour-step0-mobile.png', mask(page));
    });

    test('step 1 Create your strategy', async ({ page }) => {
        await page.goto('/');
        await waitStep(page, 'Find value bets');
        await page.getByRole('button', { name: 'Next' }).click();
        await waitStep(page, 'Create your strategy');
        await expect(page).toHaveScreenshot('tour-step1-mobile.png', mask(page));
    });

    test('step 2 Monitor performance', async ({ page }) => {
        await page.goto('/');
        await waitStep(page, 'Find value bets');
        await page.getByRole('button', { name: 'Next' }).click();
        await page.getByRole('button', { name: 'Next' }).click();
        await waitStep(page, 'Monitor performance');
        await expect(page).toHaveScreenshot('tour-step2-mobile.png', mask(page));
    });
});
