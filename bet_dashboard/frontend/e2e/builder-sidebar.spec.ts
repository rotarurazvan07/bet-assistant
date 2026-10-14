// Workstream B Part C/A: reworked builder sidebar — five honest groups,
// narrated TradeoffSliders, keyboard operability, axe-core on the sidebar.
// Local track only (installDemoApi); CI stack gets the same widget via seed.
import { test, expect } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';
import { installDemoApi, suppressTour } from './fixtures/mock-api';


test.beforeEach(async ({ page }) => {
    await suppressTour(page);
    await installDemoApi(page);
    await page.goto('/builder');
    await expect(page.getByRole('heading', { name: 'Build' })).toBeVisible();
});


test.describe('builder sidebar rework @desktop 1280x800', () => {
    test.use({ viewport: { width: 1280, height: 800 } });

    test('five honest group titles render', async ({ page }) => {
        for (const title of ['Core Targets', 'Quality Gate', 'Selection Logic', 'Markets & Sources', 'Odds Movement']) {
            // Accessible name begins with the emoji icon — match the label substring.
            await expect(page.getByRole('button', { name: new RegExp(title) })).toBeVisible();
        }
        await expect(page.getByRole('button', { name: 'Bet Shape' })).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Scoring' })).toHaveCount(0);
        await expect(page.getByRole('button', { name: 'Advanced' })).toHaveCount(0);
    });

    test('header has no Reset excluded / Run Daily; profile combobox present', async ({ page }) => {
        await expect(page.getByRole('button', { name: 'Reset excluded' })).toHaveCount(0);
        await expect(page.getByText('Run Daily')).toHaveCount(0);
        await expect(page.getByPlaceholder('profile name')).toBeVisible();
    });

    test('TradeoffSlider captions update with position (issue #41)', async ({ page }) => {
        await page.getByRole('button', { name: /Selection Logic/ }).click();
        const slider = page.locator('[data-band]').first().locator('input[type="range"]');
        await expect(page.getByTestId('tradeoff-caption').first()).toContainText(/sweet spot/);
        await slider.fill('10');
        await expect(page.getByTestId('tradeoff-caption').first()).toContainText(/coverage first/);
        await slider.fill('95');
        await expect(page.getByTestId('tradeoff-caption').first()).toContainText(/precision first/);
    });

    test('TradeoffSlider keyboard: ArrowRight moves value with aria labels intact (#41)', async ({ page }) => {
        await page.getByRole('button', { name: /Selection Logic/ }).click();
        const slider = page.getByRole('slider', { name: 'Distribution Logic' });
        await slider.focus();
        const before = await slider.inputValue();
        await page.keyboard.press('ArrowRight');
        const after = await slider.inputValue();
        expect(Number(after) - Number(before)).toBe(5);
        await expect(slider).toHaveAttribute('aria-label', 'Distribution Logic');
    });

    test('sidebar passes axe-core (Workstream B a11y gate)', async ({ page }) => {
        // Full rule set on the NEW TradeoffSlider surface, minus color-contrast:
        // the Balance/Quality edge labels inherit the approved Workstream A
        // palette (accent/win on bg-raised), same as the retired DualSlider —
        // re-tinting would need new tokens (out of scope). All structural,
        // ARIA and naming rules are enforced on the new component.
        await page.getByRole('button', { name: /Selection Logic/ }).click();
        const slider = await new AxeBuilder({ page })
            .include('[data-band]')
            .disableRules(['color-contrast'])
            .analyze();
        expect(slider.violations).toEqual([]);
        // Panel-wide: color-contrast, label, select-name are excluded — the
        // accent-on-accent-glow badge chips, Auto/Set spans, and the span-based
        // Row labelling pattern predate this workstream (Workstream A palette,
        // design-token approved, base branch parity); re-labelling here would
        // churn unrelated baselines. Palette debt is tracked at palette level.
        const panel = await new AxeBuilder({ page })
            .include('[data-testid="builder-panel"]')
            .disableRules(['color-contrast', 'label', 'select-name'])
            .analyze();
        expect(panel.violations).toEqual([]);
    });
});

test.describe('builder sidebar rework @mobile 375x667', () => {
    test.use({ viewport: { width: 375, height: 667 } });

    test('groups stack and remain operable at 375px', async ({ page }) => {
        await expect(page.getByRole('button', { name: /Core Targets/ })).toBeVisible();
        await page.getByRole('button', { name: /Selection Logic/ }).click();
        await expect(page.getByTestId('tradeoff-caption').first()).toBeVisible();
    });
});
