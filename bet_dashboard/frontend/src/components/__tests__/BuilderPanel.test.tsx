// BuilderPanel. ACTUAL (post-merge contract): immediate
// onChange (NO debounce); AccordionSection sections (Bet Shape, Filters >
// Markets/Leagues/Sources, Quality, Strategy, Advanced); ChipGrid market /
// league / source toggles with null-means-all semantics (chip renders the
// presentation label via marketLabel, title keeps the canonical key);
// NullableRow toggles gate their slider body (enabled-only render);
// balance_decay select; NO date pickers (Layout owns dates).

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BuilderPanel from '../BuilderPanel';
import type { BuilderConfig } from '../../types';
import { ALL_MARKETS, marketLabel } from '../../config/marketConfig';


function baseCfg(overrides: Partial<BuilderConfig> = {}): BuilderConfig {
    return {
        target_odds: 6.0,
        target_legs: 3,
        max_legs_overflow: null,
        consensus_floor: 50,
        min_leg_odds: 1.05,
        included_markets: null,
        included_leagues: null,
        tolerance_factor: null,
        stop_threshold: null,
        min_legs_fill_ratio: 0.7,
        quality_vs_balance: 0.5,
        consensus_vs_sources: 0.5,
        date_from: null,
        date_to: null,
        excluded_sources: null,
        consensus_shrinkage_k: null,
        min_source_edge: null,
        max_leg_odds: 10.0,
        tol_lower: null,
        tol_upper: null,
        balance_decay: 'gaussian',
        min_pick_quality: null,
        odds_movement_weight: null,
        odds_movement_strength_min: null,
        ...overrides,
    };
}


function renderPanel(cfgOverrides: Partial<BuilderConfig> = {}, leagues: string[] = [], sources: string[] = []) {
    const onChange = vi.fn();
    const cfg = baseCfg(cfgOverrides);
    const utils = render(<BuilderPanel cfg={cfg} availableLeagues={leagues} availableSources={sources} onChange={onChange} />);
    return { onChange, cfg, unmount: utils.unmount };
}


// DualSlider (restored from the earlier design): label + tooltip row, then the
// SliderWithTicks range input flanked by left/right caption spans. The range
// input carries no aria-label, so locate it through the label span's row.
function dualSliderInput(label: string): HTMLInputElement | undefined {
    const span = Array.from(document.querySelectorAll('span')).find(
        (s) => s.textContent === label
    );
    if (!span) return undefined;
    const row = span.closest('div[style*="border-bottom"]') ?? span.parentElement;
    return (row?.querySelector('input[type="range"]') as HTMLInputElement | undefined) ?? undefined;
}

// ToggleSwitch's clickable <button> ('w-10 h-5') contains only the knob span —
// the 'Auto'/'Set' labels are OUTSIDE the button, so text queries can't reach it.
function toggleButtons(): HTMLElement[] {
    return Array.from(document.querySelectorAll('button')).filter(
        (b) => b.className.includes('w-10 h-5'),
    ) as HTMLElement[];
}

// Sections render collapsed children with opacity 0 + pointerEvents none, but
// they stay in the DOM — open the section by clicking its header button first.
async function openSection(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
    await user.click(screen.getByRole('button', { name }));
}


describe('BuilderPanel', () => {
    it('renders all accordion section titles', () => {
        renderPanel();
        // section headers are the only BUTTONS with these names (Strategy's
        // 'Agreement Logic' caption span also says 'Quality' — role query
        // disambiguates headers from caption text). Header buttons prefix an
        // emoji icon, so match the title as a substring.
        for (const title of ['Bet Shape', 'Filters', 'Quality', 'Strategy', 'Advanced']) {
            expect(screen.getByRole('button', { name: new RegExp(title) })).toBeInTheDocument();
        }
    });

    it('renders numeric inputs with current cfg values', () => {
        renderPanel({ target_odds: 8.5, target_legs: 5 });
        expect((screen.getByDisplayValue('8.5') as HTMLInputElement).type).toBe('number');
        expect(screen.getByDisplayValue('5')).toBeInTheDocument();
    });

    it('numeric input change fires onChange with updated cfg (immediate — no debounce, divergence pin)', () => {
        // Controlled number input + re-render mid-typing breaks user-event;
        // fireEvent.change sets the full value deterministically (same
        // approach as SlipBuilderPanel units test).
        const { onChange } = renderPanel({ target_odds: 6 });
        const oddsInput = screen.getByDisplayValue('6');
        fireEvent.change(oddsInput, { target: { value: '7' } });
        expect(onChange).toHaveBeenCalledTimes(1);
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.target_odds).toBe(7);
    });

    it('Leagues section renders only when availableLeagues non-empty', () => {
        const { rerender } = render(<BuilderPanel cfg={baseCfg()} availableLeagues={[]} availableSources={[]} onChange={() => {}} />);
        expect(screen.queryByText(/Leagues/)).not.toBeInTheDocument();
        rerender(<BuilderPanel cfg={baseCfg()} availableLeagues={['England', 'Spain']} availableSources={[]} onChange={() => {}} />);
        expect(screen.getByText(/Leagues/)).toBeInTheDocument();
    });

    it('league toggle: single add from null cfg, add to populated, remove', async () => {
        // Controlled component: each click computes next state from the CURRENT
        // cfg prop. A test that doesn't rerender keeps a stale cfg, so fresh
        // render per toggle keeps assertions deterministic.
        const user = userEvent.setup();

        // 1. null cfg selects ALL leagues — chip is active; removing England
        //    leaves ['Spain'] (null → array transition).
        const t1 = renderPanel({}, ['England', 'Spain']);
        // Filters is defaultOpen — do NOT click its header (it would close it).
        await openSection(user, /Leagues/);
        await user.click(screen.getByTitle('England'));
        let last = t1.onChange.mock.calls[t1.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toEqual(['Spain']);
        t1.unmount();

        // 2. remove England from a FULL explicit set → ['Spain'].
        const t2 = renderPanel({ included_leagues: ['England', 'Spain'] }, ['England', 'Spain']);
        await openSection(user, /Leagues/);
        await user.click(screen.getByTitle('England'));
        last = t2.onChange.mock.calls[t2.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toEqual(['Spain']);
        t2.unmount();

        // 3. re-adding the removed league completes the set → null (all).
        const t3 = renderPanel({ included_leagues: ['Spain'] }, ['England', 'Spain']);
        await openSection(user, /Leagues/);
        await user.click(screen.getByTitle('England'));
        last = t3.onChange.mock.calls[t3.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toBeNull();
        t3.unmount();
    });

    it('source toggle adds to excluded_sources', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({}, [], ['forebet', 'predictz']);
        await openSection(user, /Sources/);
        // all sources selected (excluded_sources null) → clicking excludes it.
        await user.click(screen.getByTitle('forebet'));
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.excluded_sources).toEqual(['forebet']);
    });

    it('market toggle: complete-set chip click → null; partial set stays array', async () => {
        const user = userEvent.setup();
        // null cfg = ALL markets selected. Clicking one chip excludes it →
        // an all-but-one array (first click never jumps straight to null;
        // only completing the set again does).
        const t1 = renderPanel({ included_markets: null });
        await openSection(user, /Markets/);
        await user.click(screen.getByRole('button', { name: marketLabel(ALL_MARKETS[0]) }));
        let last = t1.onChange.mock.calls[t1.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_markets).toHaveLength(ALL_MARKETS.length - 1);
        expect(last.included_markets).not.toContain(ALL_MARKETS[0]);
        t1.unmount();

        // cfg already EXCLUDES one market — clicking that same market chip
        // re-completes the set → null (means all).
        const t2 = renderPanel({ included_markets: ALL_MARKETS.slice(1) });
        await openSection(user, /Markets/);
        await user.click(screen.getByRole('button', { name: marketLabel(ALL_MARKETS[0]) }));
        last = t2.onChange.mock.calls[t2.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_markets).toBeNull();
        t2.unmount();
    });

    it('Markets filter chips render presentation labels, NOT raw canonical keys', () => {
        // Pre-U1 bug: BuilderPanel rendered the raw canonical key ('home' -> CSS-uppercased
        // 'HOME'). Fix: render marketLabel(m) like Discover/Live Preview do.
        renderPanel();
        for (const m of ALL_MARKETS) {
            const label = marketLabel(m);
            expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
            if (label !== m) {
                // the raw key text must NOT be rendered as a chip button name
                // (title attribute keeps the canonical key for identity — see
                // the getByTitle locators above — which is intentional).
                expect(screen.queryByRole('button', { name: m })).not.toBeInTheDocument();
            }
        }
        // pin a known key/label pair so a catalog rename cannot silently pass
        expect(marketLabel('home')).toBe('1');
        expect(marketLabel(ALL_MARKETS[0])).not.toBe(ALL_MARKETS[0]);
    });

    it('market identity stays canonical in included_markets (chip title = key)', () => {
        renderPanel();
        // ChipGrid sets title={item} (canonical key) for every market chip.
        for (const m of ALL_MARKETS) {
            expect(screen.getByTitle(m)).toBeInTheDocument();
        }
    });

    it('balance_decay select switches linear/gaussian', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ balance_decay: 'gaussian' });
        await openSection(user, /Advanced/);
        const select = screen.getByDisplayValue('Gaussian');
        await user.selectOptions(select, 'linear');
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.balance_decay).toBe('linear');
    });
});

// ── Gap-closing: NullableRow toggles + slider helpers (coverage cycle) ──

describe('BuilderPanel — Quality / Strategy / Advanced sections', () => {
    it('NullableRow toggle (Min Quality) fires onChange with the enabled default', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ min_pick_quality: null });
        // Quality is defaultOpen; Min Quality is its only toggle (toggles[0]).
        const toggles = toggleButtons();
        expect(toggles.length).toBeGreaterThan(0);
        await user.click(toggles[0]);
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.min_pick_quality).toBe(0.2);
    });

    it('Min Quality InlineSlider onChange fires via range input', () => {
        // Controlled panel: the test cfg is what renders — pass min_pick_quality
        // ENABLED from the start so the InlineSlider mounts (the toggle-onclick
        // path is covered by the test above; the parent applying onChange and
        // re-rendering is the app's job, not the test's).
        const { onChange } = renderPanel({ min_pick_quality: 0.2 });
        // find the slider by its rendered value (0.2 * 100 = 20)
        const sliders = Array.from(document.querySelectorAll('input[type="range"]')) as HTMLInputElement[];
        const qSlider = sliders.find((s) => s.value === '20');
        expect(qSlider).toBeDefined();
        fireEvent.change(qSlider as HTMLInputElement, { target: { value: '45' } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.min_pick_quality).toBe(0.45);
    });

    it('Strategy DualSliders fire quality_vs_balance and consensus_vs_sources', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ consensus_floor: 80 });
        await openSection(user, /Strategy/);
        // DualSlider renders SliderWithTicks (range input, no aria-label) between
        // its left/right caption spans — locate each row by its label text.
        const quality = dualSliderInput('Distribution Logic');
        const agreement = dualSliderInput('Agreement Logic');
        expect(quality, 'Distribution Logic DualSlider not found').toBeDefined();
        expect(agreement, 'Agreement Logic DualSlider not found').toBeDefined();
        fireEvent.change(quality as HTMLInputElement, { target: { value: '80' } });
        let last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.quality_vs_balance).toBe(0.8);
        fireEvent.change(agreement as HTMLInputElement, { target: { value: '30' } });
        last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.consensus_vs_sources).toBe(0.3);
    });

    it('Advanced NullableRow slider (Shrinkage k) change', () => {
        // Same controlled-panel pattern: pass enabled cfg so the InlineSlider
        // mounts. Find by rendered value (cfg 3 → '3').
        const { onChange } = renderPanel({ consensus_shrinkage_k: 3 });
        const sliders = Array.from(document.querySelectorAll('input[type="range"]')) as HTMLInputElement[];
        const shrinkSlider = sliders.find((s) => s.value === '3');
        expect(shrinkSlider).toBeDefined();
        fireEvent.change(shrinkSlider as HTMLInputElement, { target: { value: '6' } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.consensus_shrinkage_k).toBe(6);
    });

    it('Quality SliderRow (Consensus Floor) fires onChange', () => {
        const { onChange } = renderPanel({ consensus_floor: 70 });
        const sliders = document.querySelectorAll('input[type="range"]');
        // Quality is defaultOpen — its slider is the first in the DOM
        fireEvent.change(sliders[0], { target: { value: '85' } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.consensus_floor).toBe(85);
    });

    it('Agreement Logic disabled at consensus_floor 100 (DualSlider disabled)', async () => {
        const user = userEvent.setup();
        renderPanel({ consensus_floor: 100 });
        await openSection(user, /Strategy/);
        const agreement = dualSliderInput('Agreement Logic');
        expect(agreement, 'Agreement Logic DualSlider not found').toBeDefined();
        expect((agreement as HTMLInputElement).disabled).toBe(true);
    });
});

describe('BuilderPanel — Advanced slider onChange paths', () => {
    // Each field: [cfgValue, renderedSliderValue, fireValue, expected]
    // Unique slider values per render (others null) disambiguate the by-value find.
    // All these sliders live in the (closed-by-default) Advanced section — its
    // children stay in the DOM, so the by-value query reaches them directly.
    const cases: Array<[keyof BuilderConfig, number, string, string, number]> = [
        ['stop_threshold', 0.92, '92', '95', 0.95],
        ['odds_movement_weight', 0.06, '6', '10', 0.1],
        ['odds_movement_strength_min', 0.07, '7', '12', 0.12],
        ['min_source_edge', 0.04, '4', '10', 0.1],
        ['min_pick_quality', 0.23, '23', '30', 0.3],
        ['tol_lower', 0.21, '21', '30', 0.3],
        ['tol_upper', 0.16, '16', '25', 0.25],
        ['min_legs_fill_ratio', 0.72, '72', '75', 0.75],
    ];

    it.each(cases)('%s slider fires onChange', (field, cfgValue, sliderValue, fireValue, expected) => {
        const { onChange, unmount } = renderPanel({ [field]: cfgValue } as Partial<BuilderConfig>);
        const sliders = Array.from(document.querySelectorAll('input[type="range"]')) as HTMLInputElement[];
        const target = sliders.find((s) => s.value === sliderValue);
        expect(target, `slider with value ${sliderValue} not found`).toBeDefined();
        fireEvent.change(target as HTMLInputElement, { target: { value: fireValue } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last[field]).toBe(expected);
        unmount();
    });

    it('Max Leg Odds number input fires onChange with updated cfg', () => {
        // WS-D rename pin: max_single_leg_odds → max_leg_odds. Bet Shape renders
        // Max Leg Odds as a number input (min 1.01, step 0.01), not a slider.
        const { onChange } = renderPanel({ max_leg_odds: 3.7 });
        const input = screen.getByDisplayValue('3.7') as HTMLInputElement;
        expect(input.type).toBe('number');
        fireEvent.change(input, { target: { value: '4.5' } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.max_leg_odds).toBe(4.5);
    });

    it('NullableRow toggle-off fires onChange with null (Min Quality enabled → off)', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ min_pick_quality: 0.2 });
        await user.click(toggleButtons()[0]);
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.min_pick_quality).toBeNull();
    });
});
