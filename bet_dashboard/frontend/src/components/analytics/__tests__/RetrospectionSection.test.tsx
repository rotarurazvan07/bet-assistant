import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RetrospectionSection from '../RetrospectionSection';
import type { SourceBreakdown } from '../../../types';

const makeSource = (overrides: Partial<SourceBreakdown> = {}): SourceBreakdown => ({
    source: 'forebet',
    total_predictions: 20,
    correct_predictions: 12,
    accuracy: 60.0,
    score_mae: 1.2,
    implied_win_rate: 52.6,
    edge: 7.4,
    trust_score: 0.55,
    recency_weight: 1.0,
    latest_prediction_date: '2026-11-10',
    markets: [],
    ...overrides,
});

const baseProps = {
    marketBreakdown: [],
    leagueBreakdown: [],
    defaultExpanded: true,
};

describe('RetrospectionSection trust score', () => {
    it('renders Trust column with badge and numeric score', () => {
        render(
            <RetrospectionSection
                {...baseProps}
                sourceBreakdown={[makeSource({ source: 'forebet', trust_score: 0.75 })]}
            />
        );
        expect(screen.getByText('Trust')).toBeInTheDocument();
        expect(screen.getByText('High')).toBeInTheDocument();
        expect(screen.getByText('0.75')).toBeInTheDocument();
    });

    it('renders Medium and Low badges at boundaries', () => {
        render(
            <RetrospectionSection
                {...baseProps}
                sourceBreakdown={[
                    makeSource({ source: 'a', trust_score: 0.6 }),
                    makeSource({ source: 'b', trust_score: 0.29, total_predictions: 15 }),
                ]}
            />
        );
        expect(screen.getByText('Medium')).toBeInTheDocument();
        expect(screen.getByText('Low')).toBeInTheDocument();
    });

    it('sorts by trust descending by default with source name tiebreaker', () => {
        render(
            <RetrospectionSection
                {...baseProps}
                sourceBreakdown={[
                    makeSource({ source: 'zeta', trust_score: 0.5, total_predictions: 15 }),
                    makeSource({ source: 'alpha', trust_score: 0.9, total_predictions: 20 }),
                    makeSource({ source: 'beta', trust_score: 0.5, total_predictions: 12 }),
                ]}
            />
        );
        const table = screen.getByRole('table');
        const rows = within(table).getAllByRole('row').slice(1); // skip header
        const firstCells = rows.map(r => within(r).getAllByRole('cell')[0].textContent);
        expect(firstCells).toEqual(['alpha', 'beta', 'zeta']);
    });

    it('always shows all sources (no trust filter buttons)', () => {
        render(
            <RetrospectionSection
                {...baseProps}
                sourceBreakdown={[
                    makeSource({ source: 'high1', trust_score: 0.8, total_predictions: 20 }),
                    makeSource({ source: 'med1', trust_score: 0.45, total_predictions: 15 }),
                    makeSource({ source: 'low1', trust_score: 0.1, total_predictions: 12 }),
                ]}
            />
        );
        expect(screen.queryByRole('button', { name: /high trust/i })).not.toBeInTheDocument();
        const table = screen.getByRole('table');
        expect(within(table).getAllByRole('row')).toHaveLength(4); // header + 3 rows
        expect(within(table).getByText('high1')).toBeInTheDocument();
        expect(within(table).getByText('med1')).toBeInTheDocument();
        expect(within(table).getByText('low1')).toBeInTheDocument();
    });

    it('tooltip text says date unavailable when latest_prediction_date is missing', async () => {
        const user = userEvent.setup();
        render(
            <RetrospectionSection
                {...baseProps}
                sourceBreakdown={[makeSource({ source: 'nodate', latest_prediction_date: null, trust_score: 0.4 })]}
            />
        );
        // Hover the trust badge cell to reveal tooltip
        const badge = screen.getByText('Medium');
        await user.hover(badge);
        expect(await screen.findByText(/Latest prediction date unavailable/)).toBeInTheDocument();
    });

    it('tooltip shows latest prediction date when present', async () => {
        const user = userEvent.setup();
        render(
            <RetrospectionSection
                {...baseProps}
                sourceBreakdown={[makeSource({ source: 'dated', latest_prediction_date: '2026-11-10', trust_score: 0.7 })]}
            />
        );
        await user.hover(screen.getByText('High'));
        expect(await screen.findByText(/Latest prediction: 2026-11-10/)).toBeInTheDocument();
        expect(await screen.findByText(/Trust score: 0\.700/)).toBeInTheDocument();
    });
});
