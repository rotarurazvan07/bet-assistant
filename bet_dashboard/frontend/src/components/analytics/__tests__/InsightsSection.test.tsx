import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InsightsSection from '../InsightsSection';
import type { AnalyticsInsight } from '../../../types';

const insight = (overrides: Partial<AnalyticsInsight> = {}): AnalyticsInsight => ({
    id: 'market:home',
    priority: 'high',
    confidence: 'high',
    direction: 'opportunity',
    edge: 7.4,
    sample_size: 30,
    win_rate: 60,
    implied_win_rate: 52.6,
    target: { section: 'market', market: 'home' },
    ...overrides,
});

describe('InsightsSection', () => {
    it('does not render when no actionable insights are available', () => {
        render(<InsightsSection insights={[]} />);

        expect(screen.queryByRole('region', { name: 'Actionable insights' })).not.toBeInTheDocument();
    });

    it('renders grouped actions using presentation market labels', () => {
        render(
            <InsightsSection
                insights={[
                    insight(),
                    insight({
                        id: 'source:forebet',
                        priority: 'medium',
                        confidence: 'medium',
                        direction: 'risk',
                        edge: -4.2,
                        target: { section: 'source', source: 'forebet' },
                    }),
                ]}
            />
        );

        expect(screen.getByRole('heading', { name: 'Actionable insights' })).toBeInTheDocument();
        expect(screen.getByText('Prioritize 1')).toBeInTheDocument();
        expect(screen.getByText('Avoid forebet')).toBeInTheDocument();
        expect(screen.getAllByText('high confidence')).toHaveLength(1);
        expect(screen.getByText('medium confidence')).toBeInTheDocument();
    });

    it('uses a league name for league insights', () => {
        render(
            <InsightsSection
                insights={[
                    insight({
                        id: 'league:Championship',
                        direction: 'risk',
                        target: { section: 'league', league: 'Championship' },
                    }),
                ]}
            />
        );

        expect(screen.getByText('Reduce Championship')).toBeInTheDocument();
    });

    it('shows a preview and expands each priority group on demand', async () => {
        const user = userEvent.setup();
        render(
            <InsightsSection
                insights={[
                    insight({ id: 'market:home', target: { section: 'market', market: 'home' } }),
                    insight({ id: 'market:draw', target: { section: 'market', market: 'draw' } }),
                    insight({ id: 'market:away', target: { section: 'market', market: 'away' } }),
                    insight({ id: 'market:over_25', target: { section: 'market', market: 'over_25' } }),
                ]}
            />
        );

        expect(screen.getByText('View 1 more')).toBeInTheDocument();
        expect(screen.queryByText('Prioritize O2.5')).not.toBeInTheDocument();

        await user.click(screen.getByRole('button', { name: 'View 1 more' }));
        expect(screen.getByText('Prioritize O2.5')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Show less' })).toBeInTheDocument();
    });
});
