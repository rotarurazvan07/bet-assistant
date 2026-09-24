// AnalyticsDashboard (issue #64 P2). ACTUAL (cycle-12 divergence): this is
// the SLIP-PREVIEW dashboard — MetricCards + risk GaugeChart + recharts
// RadarChart; NOT a P&L/market-breakdown page; takes legs+totalOdds props;
// returns null with no legs; NO filters. Assert radarData shape reaches
// recharts via vi.mock capture.

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';


const { radarChartMock } = vi.hoisted(() => ({
    radarChartMock: vi.fn(),
}));
vi.mock('recharts', () => ({
    RadarChart: (props: unknown) => { radarChartMock(props); return <div data-testid="radar-mock" />; },
    PolarGrid: () => <div />,
    PolarAngleAxis: () => <div />,
    PolarRadiusAxis: () => <div />,
    Radar: () => <div />,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="responsive-mock">{children}</div>,
}));


import AnalyticsDashboard from '../AnalyticsDashboard';
import { makeCandidateLeg } from '../../test/factories';


function legs(n: number, overrides: (i: number) => Record<string, unknown> = () => ({})) {
    return Array.from({ length: n }, (_, i) => makeCandidateLeg({
        consensus: 60 + i,
        sources: 4,
        score: 0.5,
        tier: 1,
        market: i === 0 ? 'Home' : `Over ${(i + 1.5).toFixed(1)}`,
        ...overrides(i),
    } as never));
}


describe('AnalyticsDashboard', () => {
    it('renders nothing with no legs (divergence pin: null, not empty-state)', () => {
        const { container } = render(<AnalyticsDashboard legs={[]} totalOdds={0} />);
        expect(container).toBeEmptyDOMElement();
    });

    it('renders the 4 MetricCards with computed values', () => {
        render(<AnalyticsDashboard legs={legs(3)} totalOdds={6.66} />);
        expect(screen.getByText('Cumulative Odds')).toBeInTheDocument();
        expect(screen.getByText('@6.66')).toBeInTheDocument();
        expect(screen.getByText(/implied probability/)).toBeInTheDocument();
        expect(screen.getByText('3 Selects')).toBeInTheDocument();
        expect(screen.getByText('100% tier 1 profile')).toBeInTheDocument();
        expect(screen.getByText('61%')).toBeInTheDocument(); // avg consensus (60+61+62)/3
        expect(screen.getByText('Avg Sources')).toBeInTheDocument();
    });

    it('passes radarData [{axis,value}]×5 to recharts RadarChart', () => {
        render(<AnalyticsDashboard legs={legs(3)} totalOdds={6.66} />);
        expect(radarChartMock).toHaveBeenCalled();
        const props = radarChartMock.mock.calls[radarChartMock.mock.calls.length - 1][0] as { data: Array<{ axis: string; value: number }> };
        expect(props.data).toHaveLength(5);
        expect(props.data.map((d) => d.axis)).toEqual(['Win Prob', 'Consensus', 'Diversity', 'Sources', 'Quality']);
        for (const d of props.data) {
            expect(typeof d.value).toBe('number');
            expect(d.value).toBeGreaterThanOrEqual(0);
            expect(d.value).toBeLessThanOrEqual(100);
        }
    });

    it('renders Risk Assessment + Profile Matrix sections', () => {
        render(<AnalyticsDashboard legs={legs(2)} totalOdds={4} />);
        expect(screen.getByText('Risk Assessment')).toBeInTheDocument();
        expect(screen.getByText('Profile Matrix')).toBeInTheDocument();
    });

    it('market spread (Diversity) counts unique markets', () => {
        render(<AnalyticsDashboard legs={legs(2)} totalOdds={4} />);
        const props = radarChartMock.mock.calls[radarChartMock.mock.calls.length - 1][0] as { data: Array<{ axis: string; value: number }> };
        const diversity = props.data.find((d) => d.axis === 'Diversity');
        expect(diversity).toBeDefined();
        // calculateDiversityScore(unique=2, total=18, legs=2) — assert bounds only (formula owned by utils)
        expect(diversity?.value).toBeGreaterThan(0);
        expect(diversity?.value).toBeLessThanOrEqual(100);
    });

    it('win prob derived from totalOdds (implied probability scale)', () => {
        render(<AnalyticsDashboard legs={legs(1)} totalOdds={2} />);
        const props = radarChartMock.mock.calls[radarChartMock.mock.calls.length - 1][0] as { data: Array<{ axis: string; value: number }> };
        const winProb = props.data.find((d) => d.axis === 'Win Prob');
        expect(winProb).toBeDefined();
        expect(winProb?.value).toBeGreaterThan(0);
        expect(winProb?.value).toBeLessThanOrEqual(100);
    });
});

// ── Gap-closing: more legs variety exercises metric branches ──

describe('AnalyticsDashboard — metric edge branches', () => {
    it('mixed tiers produce <100% tier-1 ratio', () => {
        render(
            <AnalyticsDashboard
                legs={[
                    makeCandidateLeg({ tier: 1, market: 'Home' }),
                    makeCandidateLeg({ tier: 2, market: 'Over 2.5' }),
                ]}
                totalOdds={4}
            />,
        );
        expect(screen.getByText('50% tier 1 profile')).toBeInTheDocument();
    });

    it('high source count saturates sourceDepth at 100', () => {
        render(
            <AnalyticsDashboard
                legs={[makeCandidateLeg({ sources: 8, market: 'Home' })]}
                totalOdds={2}
            />,
        );
        const props = radarChartMock.mock.calls[radarChartMock.mock.calls.length - 1][0] as { data: Array<{ axis: string; value: number }> };
        const sources = props.data.find((d) => d.axis === 'Sources');
        expect(sources?.value).toBe(100);
    });

    it('low consensus (<50) clamps radarConsensus at 0', () => {
        render(
            <AnalyticsDashboard legs={[makeCandidateLeg({ consensus: 40 })]} totalOdds={2} />,
        );
        const props = radarChartMock.mock.calls[radarChartMock.mock.calls.length - 1][0] as { data: Array<{ axis: string; value: number }> };
        const consensus = props.data.find((d) => d.axis === 'Consensus');
        expect(consensus?.value).toBe(0);
    });
});

describe('AnalyticsDashboard — risk gauge branches', () => {
    it('low and high risk renders exercise GaugeChart color branches', () => {
        const { unmount } = render(<AnalyticsDashboard legs={[makeCandidateLeg()]} totalOdds={1.5} />);
        expect(screen.getByText('Risk Assessment')).toBeInTheDocument();
        unmount();
        render(<AnalyticsDashboard legs={[makeCandidateLeg()]} totalOdds={80} />);
        expect(screen.getByText('Risk Assessment')).toBeInTheDocument();
    });
});
