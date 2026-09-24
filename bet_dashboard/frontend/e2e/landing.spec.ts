// E2E smoke (issue #63): the SPA shell renders on the dev server.
// Full-journey E2E tests come in later cycles; CI wiring in cycle 15.

import { test, expect } from '@playwright/test';

test('landing page renders the app root', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle('frontend');
    await expect(page.locator('#root')).not.toBeEmpty();
});
