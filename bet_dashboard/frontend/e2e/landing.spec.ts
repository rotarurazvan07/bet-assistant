// E2E smoke (issue #63): the SPA shell renders on the dev server.
// Full-journey E2E tests come in later cycles; CI wiring in cycle 15.

import { test, expect } from '@playwright/test';
import { suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page }) => {
    await suppressTour(page);
});

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
        // Network-layer XHR failures are environmental noise, not routing errors.
        // Local dev has no backend, so Axios reports them as AxiosError (502
        // proxy failure). CI's real backend on :3002 produces the SAME noise
        // class under WebKit, which surfaces an uncaught
        // "XMLHttpRequest cannot load ... due to access control checks" string
        // instead of an AxiosError — the message differs, the failure class
        // does not. Routing errors (render crashes, bad imports) still fail.
        const msg = String(err);
        const networkNoise =
            msg.includes('AxiosError') ||
            msg.includes('XMLHttpRequest cannot load') ||
            msg.includes('due to access control checks') ||
            msg.includes('NetworkError when attempting to fetch');
        if (!networkNoise) errors.push(msg);
    });
    for (const route of NAV_ROUTES) {
        await page.goto(route);
        await expect(page.locator('#root')).not.toBeEmpty();
    }
    expect(errors).toEqual([]);
});
