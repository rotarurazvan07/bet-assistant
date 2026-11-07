import { expect, test } from '@playwright/test';
import { DEMO_SLIP_CALENDAR, DEMO_SLIPS_PAGE } from './fixtures/demo-data';
import { installDemoApi, suppressTour } from './fixtures/mock-api';

test.beforeEach(async ({ page }) => {
    await suppressTour(page);
});

async function navigateToOctober2026(page: import('@playwright/test').Page) {
    const heading = page.getByRole('heading', { level: 2 });
    for (let attempt = 0; attempt < 36; attempt++) {
        const label = await heading.innerText();
        const current = new Date(`${label} 1`);
        if (current.getFullYear() === 2026 && current.getMonth() === 9) return;
        const step = current > new Date(2026, 9, 1) ? 'Previous month' : 'Next month';
        await page.getByRole('button', { name: step }).click();
    }
    throw new Error('October 2026 is not reachable with month navigation');
}

test('calendar navigates months and clicking a day filters slips', async ({ page }) => {
    if (!process.env.E2E_BASE_URL) {
        await installDemoApi(page, { slips: DEMO_SLIPS_PAGE, calendar: { days: DEMO_SLIP_CALENDAR } });
    }
    const requests: string[] = [];
    page.on('request', request => {
        if (new URL(request.url()).pathname === '/api/slips') requests.push(request.url());
    });

    await page.goto('/slips');
    await page.getByRole('button', { name: 'Calendar view' }).click();
    await expect(page.getByRole('region', { name: 'Daily profit calendar' })).toBeVisible();
    await expect(page.getByText('Arsenal vs Chelsea')).toHaveCount(0);
    await navigateToOctober2026(page);

    const wonDay = page.getByRole('button', { name: '2026-10-07: 1 slip, +0.9U, 1W/0L' });
    await expect(wonDay).toHaveAttribute('title', '1 slip, +0.9U, 1W/0L');
    await expect(page.getByRole('button', { name: '2026-10-08: 1 slip, -1.0U, 0W/1L' })).toBeVisible();
    await expect(page.getByRole('button', { name: '2026-10-10: 1 slip, 0.0U, 0W/0L' })).toBeVisible();

    await page.getByRole('button', { name: 'Previous month' }).click();
    await expect(page.getByRole('heading', { name: 'September 2026' })).toBeVisible();
    await page.getByRole('button', { name: 'Next month' }).click();
    await expect(page.getByRole('heading', { name: 'October 2026' })).toBeVisible();
    await page.getByRole('button', { name: 'Today' }).click();

    await navigateToOctober2026(page);
    await page.getByRole('button', { name: '2026-10-07: 1 slip, +0.9U, 1W/0L' }).click();
    await expect(page.getByText('Arsenal vs Chelsea')).toBeVisible();
    await expect.poll(() => requests.some(url => {
        const query = new URL(url).searchParams;
        return query.get('date_from') === '2026-10-07' && query.get('date_to') === '2026-10-07';
    })).toBe(true);

    await page.getByRole('button', { name: 'Filters' }).click();
    await expect(page.getByLabel('Date from')).toHaveValue('2026-10-07');
    await expect(page.getByLabel('Date to')).toHaveValue('2026-10-07');
});

test('calendar stays usable on a narrow viewport', async ({ page }) => {
    if (!process.env.E2E_BASE_URL) {
        await installDemoApi(page, { slips: DEMO_SLIPS_PAGE, calendar: { days: DEMO_SLIP_CALENDAR } });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/slips');
    await page.getByRole('button', { name: 'Calendar view' }).click();
    await navigateToOctober2026(page);
    await expect(page.getByRole('button', { name: '2026-10-08: 1 slip, -1.0U, 0W/1L' })).toBeVisible();
    await expect(page.getByText('-5U')).toBeVisible();
    await expect(page.getByText('+5U')).toBeVisible();
});
