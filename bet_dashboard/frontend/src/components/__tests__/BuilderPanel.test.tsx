// BuilderPanel (issue #64 P2). ACTUAL (cycle-12 divergence): immediate
// onChange (NO debounce); AccordionSection sections; market toggle
// null-means-all; league/source multi-selects; balance_decay select;
// NO date pickers (Layout owns dates).

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BuilderPanel from '../BuilderPanel';
import type { BuilderConfig } from '../../types';
import { ALL_MARKETS } from '../../config/marketConfig';


function baseCfg(overrides: Partial<BuilderConfig> = {}): BuilderConfig {
    return {
        target_odds: 6.0,
        target_legs: 3,
        max_legs_overflow: null,
        consensus_floor: 50,
        min_odds: 1.05,
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
        max_single_leg_odds: null,
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


describe('BuilderPanel', () => {
    it('renders all accordion section titles', () => {
        renderPanel();
        for (const title of ['Bet Shape', 'Quality Gate', 'Markets', 'Tolerance & Stop', 'Scoring', 'Odds Movement', 'Advanced']) {
            expect(screen.getByText(title)).toBeInTheDocument();
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

    it('league toggle: single add from null cfg, add to populated, remove, remove-to-null', async () => {
        // Controlled component: each click computes next state from the CURRENT
        // cfg prop. Multi-click sequences in one render drift (the parent
        // applies onChange → re-renders; a test that doesn't rerender keeps
        // stale cfg). Fresh render per toggle keeps assertions deterministic.
        const user = userEvent.setup();

        // 1. add England from null cfg → ['England']
        const t1 = renderPanel({}, ['England', 'Spain']);
        await user.click(screen.getByRole('button', { name: /Leagues/ }));
        await user.click(screen.getByTitle('England'));
        let last = t1.onChange.mock.calls[t1.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toEqual(['England']);

        t1.unmount();

        // 2. add Spain to cfg already containing England → ['England', 'Spain']
        const t2 = renderPanel({ included_leagues: ['England'] }, ['England', 'Spain']);
        await user.click(screen.getByRole('button', { name: /Leagues/ }));
        await user.click(screen.getByTitle('Spain'));
        last = t2.onChange.mock.calls[t2.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toEqual(['England', 'Spain']);

        t2.unmount();

        // 3. remove England from populated cfg → ['Spain']
        const t3 = renderPanel({ included_leagues: ['England', 'Spain'] }, ['England', 'Spain']);
        await user.click(screen.getByRole('button', { name: /Leagues/ }));
        await user.click(screen.getByTitle('England'));
        last = t3.onChange.mock.calls[t3.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toEqual(['Spain']);

        t3.unmount();

        // 4. remove last remaining → null (all)
        const t4 = renderPanel({ included_leagues: ['Spain'] }, ['England', 'Spain']);
        await user.click(screen.getByRole('button', { name: /Leagues/ }));
        await user.click(screen.getByTitle('Spain'));
        last = t4.onChange.mock.calls[t4.onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toBeNull();
    });

    it('source toggle adds to excluded_sources', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({}, [], ['forebet', 'predictz']);
        await user.click(screen.getByRole('button', { name: /Sources/ }));
        await user.click(screen.getByTitle('forebet'));
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.excluded_sources).toEqual(['forebet']);
    });

    it('Clear All leagues resets to null', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ included_leagues: ['England'] }, ['England']);
        await user.click(screen.getByText(/Leagues/));
        await user.click(screen.getByText('Clear All'));
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_leagues).toBeNull();
    });

    it('market toggle: removing last-but-one market keeps array; removing to all → null', async () => {
        const user = userEvent.setup();
        // cfg has ONE market excluded → included_markets is array of all-but-one
        const allButOne = ALL_MARKETS.slice(1);
        const { onChange } = renderPanel({ included_markets: allButOne });
        // toggle the one market NOT in the list (ALL_MARKETS[0]) → adds it back → all → null
        await user.click(screen.getByText(ALL_MARKETS[0]));
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.included_markets).toBeNull(); // complete set → null (all)
    });

    it('balance_decay select switches linear/gaussian', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ balance_decay: 'gaussian' });
        const select = screen.getByDisplayValue('Gaussian');
        await user.selectOptions(select, 'linear');
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.balance_decay).toBe('linear');
    });
});

// ── Gap-closing: NullableRow toggles + slider helpers (coverage cycle) ──
// NOTE: ToggleSwitch's clickable <button> contains only the knob span — the
// 'Auto'/'Set' labels are OUTSIDE the button, so text queries can't reach it.
// Select toggle buttons structurally (className 'w-10 h-5').

function toggleButtons(): HTMLElement[] {
    return Array.from(document.querySelectorAll('button')).filter(
        (b) => b.className.includes('w-10 h-5'),
    ) as HTMLElement[];
}

describe('BuilderPanel — Tolerance & Stop / Scoring / Advanced sections', () => {
    it('NullableRow toggle (Max Overflow) fires onChange with the enabled default', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ max_legs_overflow: null });
        // Bet Shape is defaultOpen; Max Overflow is its only toggle (toggles[0])
        const toggles = toggleButtons();
        expect(toggles.length).toBeGreaterThan(0);
        await user.click(toggles[0]);
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.max_legs_overflow).toBe(1);
    });

    it('InlineSlider onChange fires via range input (Tolerance Factor)', () => {
        // Controlled panel: the test cfg is what renders — pass tolerance_factor
        // ENABLED from the start so the InlineSlider mounts (the toggle-onclick
        // path is covered by the Max Overflow test; the parent applying onChange
        // and re-rendering is the app's job, not the test's).
        const { onChange } = renderPanel({ tolerance_factor: 0.25 });
        // find the TolFactor slider by its rendered value (0.25 * 100 = 25)
        const sliders = Array.from(document.querySelectorAll('input[type="range"]')) as HTMLInputElement[];
        const tolSlider = sliders.find((s) => s.value === '25');
        expect(tolSlider).toBeDefined();
        fireEvent.change(tolSlider as HTMLInputElement, { target: { value: '50' } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.tolerance_factor).toBe(0.5);
    });

    it('Scoring DualSliders fire quality_vs_balance and consensus_vs_sources', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ consensus_floor: 80 });
        await user.click(screen.getByRole('button', { name: /Scoring/ }));
        // sliders in DOM (T&S closed): QG floor(0), MinLegsFill(1),
        // Distribution Logic(2), Agreement Logic(3)
        const sliders = document.querySelectorAll('input[type="range"]');
        fireEvent.change(sliders[2], { target: { value: '80' } });
        let last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.quality_vs_balance).toBe(0.8);
        fireEvent.change(sliders[3], { target: { value: '30' } });
        last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.consensus_vs_sources).toBe(0.3);
    });

    it('Advanced NullableRow slider (Shrinkage k) change', () => {
        // Same controlled-panel pattern as TolFactor: pass enabled cfg so the
        // InlineSlider mounts. Find by rendered value (cfg 3 → '3').
        const { onChange } = renderPanel({ consensus_shrinkage_k: 3 });
        const sliders = Array.from(document.querySelectorAll('input[type="range"]')) as HTMLInputElement[];
        const shrinkSlider = sliders.find((s) => s.value === '3');
        expect(shrinkSlider).toBeDefined();
        fireEvent.change(shrinkSlider as HTMLInputElement, { target: { value: '6' } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.consensus_shrinkage_k).toBe(6);
    });

    it('Quality Gate SliderRow (Consensus Floor) fires onChange', () => {
        const { onChange } = renderPanel({ consensus_floor: 70 });
        const sliders = document.querySelectorAll('input[type="range"]');
        // Quality Gate is defaultOpen — its slider is the first in the DOM
        fireEvent.change(sliders[0], { target: { value: '85' } });
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.consensus_floor).toBe(85);
    });

    it('Agreement Logic disabled at consensus_floor 100 (DualSlider disabled)', async () => {
        const user = userEvent.setup();
        renderPanel({ consensus_floor: 100 });
        await user.click(screen.getByRole('button', { name: /Scoring/ }));
        const sliders = document.querySelectorAll('input[type="range"]');
        // Agreement Logic is sliders[3] (see Scoring test comment)
        expect((sliders[3] as HTMLInputElement).disabled).toBe(true);
    });
});

describe('BuilderPanel — parametrized slider onChange paths', () => {
    // Each field: [cfgValue, renderedSliderValue, fireValue, expected]
    // Unique slider values per render (others null) disambiguate the by-value find.
    const cases: Array<[keyof BuilderConfig, number, string, string, number]> = [
        ['stop_threshold', 0.92, '92', '95', 0.95],
        ['odds_movement_weight', 0.06, '6', '10', 0.1],
        ['odds_movement_strength_min', 0.07, '7', '12', 0.12],
        ['min_source_edge', 0.04, '4', '10', 0.1],
        ['max_single_leg_odds', 3.7, '37', '40', 4.0],
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

    it('NullableRow toggle-off fires onChange with null (Max Overflow enabled → off)', async () => {
        const user = userEvent.setup();
        const { onChange } = renderPanel({ max_legs_overflow: 1 });
        await user.click(toggleButtons()[0]);
        const last = onChange.mock.calls[onChange.mock.calls.length - 1][0] as BuilderConfig;
        expect(last.max_legs_overflow).toBeNull();
    });
});
