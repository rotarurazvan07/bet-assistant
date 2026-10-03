// E2E smoke (issue #63): the SPA shell renders on the dev server.
// Full-journey E2E tests come in later cycles; CI wiring in cycle 15.

import { test, expect } from '@playwright/test';

test('landing page renders the app root', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle('frontend');
    await expect(page.locator('#root')).not.toBeEmpty();
});

// Issue #36: workflow-grouped nav (AC-06) — labels, order, captions, routes.
const NAV_LABELS = ['Discover', 'Build', 'Track', 'Analytics', 'Services', 'Odds Alert'] as const;
const NAV_ROUTES = ['/', '/builder', '/slips', '/analytics', '/services', '/odds-alert'] as const;

test('nav renders renamed labels in grouped order', async ({ page }) => {
    await page.goto('/');
    const links = page.locator('nav a');
    await expect(links).toHaveCount(6);
    for (let i = 0; i < NAV_LABELS.length; i++) {
        await expect(links.nth(i)).toHaveText(NAV_LABELS[i]);
    }
});

test('nav renders group micro-captions and separators', async ({ page }) => {
    await page.goto('/');
    for (const caption of ['Core', 'Insights', 'System']) {
        await expect(page.locator('nav .nav-caption', { hasText: caption })).toBeVisible();
    }
    await expect(page.locator('nav .nav-separator')).toHaveCount(2);
});

test('click-through navigates to all 6 routes without error', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => {
        // Local dev has no backend: Axios proxy failures (502) are environmental
        // noise, not routing errors. CI's real backend surfaces everything else.
        if (!String(err).includes('AxiosError')) errors.push(String(err));
    });
    for (const route of NAV_ROUTES) {
        await page.goto(route);
        await expect(page.locator('#root')).not.toBeEmpty();
    }
    expect(errors).toEqual([]);
});
