// BetComponents (issue #64 P2). ACTUAL divergences (cycle 12): BetPreview
// lives HERE (no separate file); empty text 'No matches meet the current
// criteria.'; NO loading skeleton; pendingUrls → 'In pending slip' strip;
// tier-2 legs → 'N out-of-band' badge; onExclude fires only with truthy
// result_url. Helpers: TierBadge, OddsMovementBadge, QualityIndicator,
// BetLegRow, SlipCard, SlipDetailModal.

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BetPreview, BetLegRow, SlipCard, SlipDetailModal } from '../BetComponents';
import { makeCandidateLeg, makeSlip, makeBetLeg } from '../../test/factories';


describe('BetPreview', () => {
    it('empty state shows the divergence-pinned text (not "No legs generated")', () => {
        render(<BetPreview legs={[]} pendingUrls={[]} onExclude={() => {}} totalOdds={0} />);
        expect(screen.getByText('No matches meet the current criteria.')).toBeInTheDocument();
        expect(screen.queryByText('No legs generated')).not.toBeInTheDocument();
    });

    it('renders leg cards with parsed team names and market badge', () => {
        render(<BetPreview legs={[makeCandidateLeg({ match_name: 'Arsenal - Chelsea' })]} pendingUrls={[]} onExclude={() => {}} totalOdds={0} />);
        // parseTeamNames splits on ' - ' (dash format, not 'vs')
        expect(screen.getByText('Arsenal')).toBeInTheDocument();
        expect(screen.getByText('Chelsea')).toBeInTheDocument();
        expect(screen.getByText(/Home @1\.90/)).toBeInTheDocument();
    });

    it('highlights legs already in a pending slip (divergence: strip, not toast)', () => {
        render(
            <BetPreview legs={[makeCandidateLeg()]} pendingUrls={['https://example.com/match/1']} onExclude={() => {}} totalOdds={0} />,
        );
        expect(screen.getByText(/In pending slip/)).toBeInTheDocument();
    });

    it('shows out-of-band badge when tier-2 legs exist', () => {
        render(
            <BetPreview legs={[makeCandidateLeg({ tier: 2 })]} pendingUrls={[]} onExclude={() => {}} totalOdds={0} />,
        );
        expect(screen.getByText('1 out-of-band')).toBeInTheDocument();
        expect(screen.getByText('⚠ Drift')).toBeInTheDocument();
    });

    it('tier-1 legs show Balanced badge, no out-of-band warning', () => {
        render(<BetPreview legs={[makeCandidateLeg({ tier: 1 })]} pendingUrls={[]} onExclude={() => {}} totalOdds={0} />);
        expect(screen.getByText('✓ Balanced')).toBeInTheDocument();
        expect(screen.queryByText(/out-of-band/)).not.toBeInTheDocument();
    });

    it('onExclude fires with result_url on exclude click', async () => {
        const user = userEvent.setup();
        const onExclude = vi.fn();
        render(<BetPreview legs={[makeCandidateLeg()]} pendingUrls={[]} onExclude={onExclude} totalOdds={0} />);
        await user.click(screen.getByText('✕'));
        expect(onExclude).toHaveBeenCalledWith('https://example.com/match/1');
    });

    it('exclude button renders but onExclude NOT fired when result_url empty (onClick guard pin)', async () => {
        const user = userEvent.setup();
        const onExclude = vi.fn();
        render(<BetPreview legs={[makeCandidateLeg({ result_url: '' })]} pendingUrls={[]} onExclude={onExclude} totalOdds={0} />);
        // source: onClick={() => leg.result_url && onExclude(leg.result_url)} — guard, not conditional render
        const btn = screen.getByText('✕').closest('button');
        expect(btn).not.toBeNull();
        await user.click(btn as HTMLElement);
        expect(onExclude).not.toHaveBeenCalled();
    });

    it('OddsMovementBadge: down + strength ≥ min → confirm badge with title', () => {
        render(
            <BetPreview
                legs={[makeCandidateLeg({ odds_movement_direction: 'down', odds_movement_strength: 0.08, tier: 1 })]}
                pendingUrls={[]}
                onExclude={() => {}}
                minStrength={0.05}
                totalOdds={0}
            />,
        );
        expect(screen.getByTitle(/Odds dropped 8\.0% — bookmaker confirms/)).toBeInTheDocument();
    });

    it('OddsMovementBadge: strength below minStrength → hidden', () => {
        render(
            <BetPreview
                legs={[makeCandidateLeg({ odds_movement_direction: 'down', odds_movement_strength: 0.02, tier: 1 })]}
                pendingUrls={[]}
                onExclude={() => {}}
                minStrength={0.05}
                totalOdds={0}
            />,
        );
        expect(screen.queryByTitle(/Odds dropped/)).not.toBeInTheDocument();
    });

    it('QualityIndicator renders score as percentage', () => {
        render(<BetPreview legs={[makeCandidateLeg({ score: 0.83 })]} pendingUrls={[]} onExclude={() => {}} totalOdds={0} />);
        expect(screen.getByText('83%')).toBeInTheDocument();
    });
});


describe('BetLegRow', () => {
    it('renders match name, date, league and market@odds badge', () => {
        render(<BetLegRow leg={makeBetLeg()} slipStatus="Pending" />);
        expect(screen.getByText('Arsenal vs Chelsea')).toBeInTheDocument();
        expect(screen.getByText(/Home @1\.90/)).toBeInTheDocument();
        expect(screen.getByText('England')).toBeInTheDocument();
    });

    it('result_url renders as link; absent renders as plain text', () => {
        const { unmount } = render(<BetLegRow leg={makeBetLeg()} slipStatus="Pending" />);
        expect(screen.getByRole('link', { name: /Arsenal vs Chelsea/ })).toHaveAttribute('href', 'https://example.com/match/1');
        unmount();
        render(<BetLegRow leg={makeBetLeg({ result_url: '' })} slipStatus="Pending" />);
        expect(screen.queryByRole('link')).not.toBeInTheDocument();
        expect(screen.getByText('Arsenal vs Chelsea')).toBeInTheDocument();
    });

    it('live data shows score + minute when leg is Live', () => {
        render(
            <BetLegRow
                leg={makeBetLeg({ status: 'Live' })}
                liveData={{ 'Arsenal vs Chelsea': { score: '2-1', minute: '67’' } }}
                slipStatus="Live"
            />,
        );
        expect(screen.getByText('2-1')).toBeInTheDocument();
        expect(screen.getByText('67’')).toBeInTheDocument();
    });
});


describe('SlipCard', () => {
    it('renders header badges: date, profile, status', () => {
        render(<SlipCard slip={makeSlip()} />);
        expect(screen.getByText('2026-09-24')).toBeInTheDocument();
        expect(screen.getByText('low')).toBeInTheDocument();
        expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    it('footer shows units @ total_odds', () => {
        render(<SlipCard slip={makeSlip()} />);
        expect(screen.getByText('1u')).toBeInTheDocument();
        expect(screen.getByText('@ 1.90')).toBeInTheDocument();
    });

    it('delete button shows only for Pending slips with onDelete', async () => {
        const user = userEvent.setup();
        const onDelete = vi.fn();
        const { unmount } = render(<SlipCard slip={makeSlip()} onDelete={onDelete} />);
        const del = screen.getByTitle('Delete slip');
        await user.click(del);
        expect(onDelete).toHaveBeenCalledWith(1);
        unmount();
        render(<SlipCard slip={makeSlip({ slip_status: 'Won' })} onDelete={onDelete} />);
        expect(screen.queryByTitle('Delete slip')).not.toBeInTheDocument();
    });

    it('leg truncation: 3 non-live legs → shows 2 + Show Details (1 more)', () => {
        const slip = makeSlip({
            legs: [
                makeBetLeg({ match_name: 'Match A', datetime: '2026-09-25T10:00:00' }),
                makeBetLeg({ match_name: 'Match B', datetime: '2026-09-25T12:00:00' }),
                makeBetLeg({ match_name: 'Match C', datetime: '2026-09-25T14:00:00' }),
            ],
        });
        render(<SlipCard slip={slip} onCardClick={() => {}} />);
        expect(screen.getByText('Match A')).toBeInTheDocument();
        expect(screen.getByText('Match B')).toBeInTheDocument();
        expect(screen.queryByText('Match C')).not.toBeInTheDocument();
        expect(screen.getByText(/Show Details \(1 more\)/)).toBeInTheDocument();
    });

    it('live legs sort first and display when ≥2 live', () => {
        const slip = makeSlip({
            slip_status: 'Live',
            legs: [
                makeBetLeg({ match_name: 'Done A', status: 'Won', datetime: '2026-09-25T10:00:00' }),
                makeBetLeg({ match_name: 'Live B', status: 'Live', datetime: '2026-09-25T12:00:00' }),
                makeBetLeg({ match_name: 'Live C', status: 'Live', datetime: '2026-09-25T13:00:00' }),
            ],
        });
        render(<SlipCard slip={slip} onCardClick={() => {}} />);
        expect(screen.getByText('Live B')).toBeInTheDocument();
        expect(screen.getByText('Live C')).toBeInTheDocument();
        expect(screen.queryByText('Done A')).not.toBeInTheDocument();
    });

    it('won slip footer shows net profit', () => {
        render(<SlipCard slip={makeSlip({ slip_status: 'Won', total_odds: 2.5, units: 1 })} />);
        // netProfit = (2.5-1)*1 = +1.50
        expect(screen.getByText('+1.50')).toBeInTheDocument();
    });

    it('card click fires onCardClick', async () => {
        const user = userEvent.setup();
        const onCardClick = vi.fn();
        render(<SlipCard slip={makeSlip()} onCardClick={onCardClick} />);
        // match-name anchor has stopPropagation — click a neutral area (footer)
        await user.click(screen.getByText('1u'));
        expect(onCardClick).toHaveBeenCalledTimes(1);
    });
});


describe('SlipDetailModal', () => {
    it('renders nothing when slip is null', () => {
        const { container } = render(<SlipDetailModal slip={null} onClose={() => {}} />);
        expect(container).toBeEmptyDOMElement();
    });

    it('backdrop click fires onClose', async () => {
        const user = userEvent.setup();
        const onClose = vi.fn();
        const { container } = render(<SlipDetailModal slip={makeSlip()} onClose={onClose} />);
        const backdrop = container.querySelector('[class*="backdrop-blur-sm"]');
        expect(backdrop).not.toBeNull();
        await user.click(backdrop as HTMLElement);
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('Escape key fires onClose', () => {
        const onClose = vi.fn();
        render(<SlipDetailModal slip={makeSlip()} onClose={onClose} />);
        fireEvent.keyDown(window, { key: 'Escape' });
        expect(onClose).toHaveBeenCalledTimes(1);
    });
});

// ── Gap-closing: SlipDetailModal content ──

describe('SlipDetailModal — content', () => {
    it('renders all legs (no truncation in modal)', () => {
        const slip = makeSlip({
            legs: [
                makeBetLeg({ match_name: 'Match A' }),
                makeBetLeg({ match_name: 'Match B' }),
                makeBetLeg({ match_name: 'Match C' }),
                makeBetLeg({ match_name: 'Match D' }),
            ],
        });
        render(<SlipDetailModal slip={slip} onClose={() => {}} />);
        expect(screen.getByText('Match A')).toBeInTheDocument();
        expect(screen.getByText('Match B')).toBeInTheDocument();
        expect(screen.getByText('Match C')).toBeInTheDocument();
        expect(screen.getByText('Match D')).toBeInTheDocument();
    });

    it('renders slip profile + status badges in modal header', () => {
        render(<SlipDetailModal slip={makeSlip()} onClose={() => {}} />);
        // header: title 'Betting Slip' + date • PROFILE.toUpperCase() + status badge
        expect(screen.getByText('Betting Slip')).toBeInTheDocument();
        expect(screen.getByText(/LOW/)).toBeInTheDocument();
        expect(screen.getByText('Pending')).toBeInTheDocument();
        expect(screen.getByText('Status')).toBeInTheDocument();
        expect(screen.getByText('Stake')).toBeInTheDocument();
    });
});

describe('SlipDetailModal — settled footer', () => {
    it('Won slip shows net profit in header (calculateNetProfit branch)', () => {
        render(<SlipDetailModal slip={makeSlip({ slip_status: 'Won', total_odds: 2.5, units: 1 })} onClose={() => {}} />);
        expect(screen.getByText(/\+1\.50/)).toBeInTheDocument();
    });
});
