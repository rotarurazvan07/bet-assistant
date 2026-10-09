// Accessibility (issue #36 AC-08): axe-core scan on the header/nav + a
// keyboard-only walk of the nav links. Runs in CI (external stack) and local.

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page }) => {
    await suppressTour(page);
});

async function expectHeaderAxeClean(page: import('@playwright/test').Page) {
    const results = await new AxeBuilder({ page })
        .include('header')
        .analyze();
    expect(results.violations).toEqual([]);
}

test('header/nav passes axe-core with no violations', async ({ page }) => {
    await page.goto('/');
    await expectHeaderAxeClean(page);
});

test('header/nav passes axe-core on System routes (services, odds-alert)', async ({ page }) => {
    for (const route of ['/services', '/odds-alert']) {
        await page.goto(route);
        await expectHeaderAxeClean(page);
    }
});

test('keyboard-only walk through nav reaches every tab in order', async ({ page }) => {
    await page.goto('/');
    const labels = ['Discover', 'Build', 'Track', 'Analytics', 'Services', 'Odds Alert'];
    // Focus first nav link, then Tab through the full sequence.
    await page.locator('nav a').first().focus();
    for (const label of labels) {
        await expect(page.locator('nav a', { hasText: label })).toBeFocused();
        if (label !== labels[labels.length - 1]) {
            await page.keyboard.press('Tab');
        }
    }
    // Return focus to the first link, then Enter activates it (we are on '/'
    // already, so the assertion is about NavLink active state, not URL).
    await page.locator('nav a').first().focus();
    await expect(page.locator('nav a', { hasText: 'Discover' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('nav a', { hasText: 'Discover' })).toHaveClass(/active/);
});
