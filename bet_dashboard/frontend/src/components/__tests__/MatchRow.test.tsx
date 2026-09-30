// MatchRow (issue #64 P1). ACTUAL (cycle-12 divergence): NO navigation —
// cells build CandidateLeg and fire onCellClick; buildLeg gates on
// odds>0, consensus>0, result_url, datetime, sources; movement keys derived
// from MARKET_COLUMNS oddsKey (odds_home → home); row opacity 1 vs 0.25 by
// hasResultUrl.

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MatchRow from '../MatchRow';
import type { CandidateLeg } from '../../types';
import { makeMatch } from '../../test/factories';


function renderRow(overrides: Partial<Parameters<typeof MatchRow>[0]> = {}) {
    const defaults: Parameters<typeof MatchRow>[0] = {
        match: makeMatch(),
        index: 1,
    };
    const { container } = render(
        <table><tbody>
            <MatchRow {...defaults} {...overrides} />
        </tbody></table>,
    );
    return { container };
}


describe('MatchRow', () => {
    it('renders home, away, sources, league and formatted datetime', () => {
        renderRow({ match: makeMatch({ home: 'Arsenal', away: 'Chelsea', sources: 4, league: 'England', datetime: '2026-09-25T15:00:00' }) });
        expect(screen.getByText('Arsenal')).toBeInTheDocument();
        expect(screen.getByText('Chelsea')).toBeInTheDocument();
        expect(screen.getByText('4')).toBeInTheDocument();
        expect(screen.getByText('England')).toBeInTheDocument();
        expect(screen.getByText(/25\/09/)).toBeInTheDocument();
    });

    it('datetime placeholder — when null', () => {
        renderRow({ match: makeMatch({ datetime: null }) });
        expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    });

    it('consensus cell shows pct and odds with aria-label', () => {
        renderRow({ match: makeMatch({ cons_home: 75, odds_home: 1.9 }) });
        const cell = screen.getByRole('button', { name: 'Select 75% at @1.90' });
        expect(cell).toBeInTheDocument();
    });

    it('zero-consensus cell renders dash placeholder (no button)', () => {
        renderRow({ match: makeMatch({ cons_home: 0, odds_home: 1.9 }) });
        expect(screen.queryByRole('button', { name: /Select 0%/ })).not.toBeInTheDocument();
        expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    });

    it('cell click fires onCellClick with a fully-built CandidateLeg', async () => {
        const user = userEvent.setup();
        const onCellClick = vi.fn();
        const match = makeMatch({ cons_home: 75, odds_home: 1.9, sources: 4, result_url: 'https://example.com/m/1', datetime: '2026-09-25T15:00:00' });
        renderRow({ match, onCellClick });
        await user.click(screen.getByRole('button', { name: 'Select 75% at @1.90' }));
        expect(onCellClick).toHaveBeenCalledTimes(1);
        const leg = onCellClick.mock.calls[0][0] as CandidateLeg;
        expect(leg.market).toBe('1'); // MARKET_COLUMNS home market key is '1' (not 'Home')
        expect(leg.market_type).toBe('result');
        expect(leg.consensus).toBe(75);
        expect(leg.odds).toBe(1.9);
        expect(leg.match_name).toBe('Arsenal - Chelsea');
        expect(leg.sources).toBe(4);
        expect(leg.result_url).toBe('https://example.com/m/1');
    });

    it('buildLeg gating: empty result_url blocks onCellClick', async () => {
        const user = userEvent.setup();
        const onCellClick = vi.fn();
        const match = makeMatch({ cons_home: 75, odds_home: 1.9, result_url: '' });
        renderRow({ match, onCellClick });
        await user.click(screen.getByRole('button', { name: /Select 75%/ }));
        expect(onCellClick).not.toHaveBeenCalled();
    });

    it('buildLeg gating: null odds blocks onCellClick', async () => {
        const user = userEvent.setup();
        const onCellClick = vi.fn();
        const match = makeMatch({ cons_home: 75, odds_home: undefined });
        renderRow({ match, onCellClick });
        const cell = screen.getByRole('button', { name: /Select 75% at @—/ });
        await user.click(cell);
        expect(onCellClick).not.toHaveBeenCalled();
    });

    it('visibleColumns filters market cells', () => {
        renderRow({ visibleColumns: new Set(['1']) });
        expect(screen.getByRole('button', { name: /Select 75% at @1\.90/ })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /55% at @1\.80/ })).not.toBeInTheDocument();
    });

    it('inSlipMarkets cells show loss styling', () => {
        renderRow({ inSlipMarkets: new Set(['1']) });
        const cell = screen.getByRole('button', { name: /Select 75% at @1\.90/ });
        expect(cell.getAttribute('style')).toContain('var(--loss-bg)');
    });

    it('movement prop maps to OddsMovementIndicator via oddsKey derivation', () => {
        renderRow({ movement: { home: 'up' } });
        expect(screen.getByTitle('Odds rising (market disagrees)')).toBeInTheDocument();
    });
});
