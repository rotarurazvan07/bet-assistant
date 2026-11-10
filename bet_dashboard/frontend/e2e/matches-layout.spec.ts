// Layout invariants of the matches table.
// A Tailwind pipeline failure removes the whole utilities layer: spacing,
// fonts and theme colors silently vanish from the built stylesheet while
// every unit test stays green, because none of them assert computed styles.
// This spec fails that class of regression in the E2E lane instead.
import { test, expect } from '@playwright/test';
import { suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page }) => {
    await suppressTour(page);
    // Pathname-only matchers: globs like **/api/matches* steal Vite /src/api/*.ts.
    await page.route((url) => url.pathname === '/api/matches', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                total: 2,
                page: 1,
                page_size: 20,
                total_pages: 1,
                matches: [
                    {
                        id: 'layout-1',
                        home_team: 'Team A',
                        away_team: 'Team B',
                        league: 'Test League',
                        kickoff: '2026-11-10 18:00',
                        odds: { home: 2.15, draw: 3.4, away: 3.1 },
                        consensus: 78,
                    },
                    {
                        id: 'layout-2',
                        home_team: 'Team C',
                        away_team: 'Team D',
                        league: 'Test League',
                        kickoff: '2026-11-10 20:00',
                        odds: { home: 1.85, draw: 3.6, away: 4.2 },
                        consensus: 55,
                    },
                ],
            }),
        });
    });
});

test('matches table keeps its layout after the CSS build', async ({ page }) => {
    await page.goto('/');
    const table = page.locator('table').first();
    await expect(table).toBeVisible();

    // Typography: the sans theme font must be applied, not a browser default.
    const bodyFont = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    expect(bodyFont).toContain('Inter');

    // Spacing: the table header cells carry spacing utilities; a build that
    // drops the utilities layer collapses them to zero padding, which is the
    // "odds columns crammed, whites gone" symptom.
    const header = table.locator('thead th').first();
    await expect(header).toBeVisible();
    const padding = await header.evaluate((el) => {
        const style = getComputedStyle(el);
        return { x: parseFloat(style.paddingLeft), y: parseFloat(style.paddingTop) };
    });
    expect(padding.x).toBeGreaterThan(8);
    expect(padding.y).toBeGreaterThan(8);
});

