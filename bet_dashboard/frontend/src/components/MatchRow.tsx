import type { Match, CandidateLeg } from '../types';
import { BaseDataRow } from './ui/BaseDataRow';

// Consensus cell coloring
function consCell(pct: number, odds: number | null | undefined) {
    if (!pct || pct <= 0) return null;
    const bg = pct >= 80 ? 'var(--cons-high)'
        : pct >= 60 ? 'var(--cons-mid)'
            : 'var(--cons-low)';
    const col = pct >= 80 ? 'var(--cons-high-txt)'
        : pct >= 60 ? 'var(--cons-mid-txt)'
            : 'var(--cons-low-txt)';
    return { bg, col, pct, odds };
}

interface CellProps {
    pct: number;
    odds: number | null | undefined;
    onClick?: () => void;
    isActive?: boolean;
    isInSlip?: boolean;
}

function Cell({ pct, odds, onClick, isActive = false, isInSlip = false }: CellProps) {
    const c = consCell(pct, odds);
    if (!c) return <td className="px-3 py-3 text-center">
        <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>—</span>
    </td>;
    const oddsDisplay = c.odds != null ? c.odds.toFixed(2) : '—';
    // Determine styling based on states
    const bgColor = isInSlip ? 'var(--loss-bg)' : (isActive ? 'var(--accent-glow)' : c.bg);
    const borderColor = isInSlip ? `1px solid var(--loss-border)` : (isActive ? `1px solid var(--border-accent)` : 'none');
    const textColor = isInSlip ? 'var(--loss)' : (isActive ? 'var(--accent)' : c.col);
    return (
        <td className="px-3 py-3 text-center" style={{ minWidth: 64 }}>
            <div
                className="rounded px-2 py-1 inline-flex flex-col items-center gap-1 leading-none cursor-pointer transition-opacity hover:opacity-80"
                style={{
                    background: bgColor,
                    border: borderColor
                }}
                onClick={onClick}
                role="button"
                tabIndex={0}
                aria-label={`Select ${c.pct || pct || 0}% at @${oddsDisplay}`}
            >
                <span className="font-mono font-bold text-sm" style={{ color: textColor }}>
                    {c.pct ? c.pct.toFixed(0) : '0'}%
                </span>
                {c.odds != null && c.odds > 1 && (
                    <span className="font-mono text-sm" style={{ color: textColor, opacity: isInSlip || isActive ? 1 : 0.8 }}>
                        @{oddsDisplay}
                    </span>
                )}
            </div>
        </td>
    );
}

interface Props {
    match: Match;
    index: number;
    onCellClick?: (leg: CandidateLeg) => void;
    activeMarkets?: Set<string>;
    inSlipMarkets?: Set<string>;
}

export default function MatchRow({ match, index, onCellClick, activeMarkets = new Set(), inSlipMarkets = new Set() }: Props) {
    const dt = match.datetime
        ? new Date(match.datetime).toLocaleString('en-GB', {
            day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
        }).replace(',', '')
        : '—';

    const matchName = `${match.home} - ${match.away}`;

    // Helper to build CandidateLeg (returns null if odds, consensus, result_url, datetime, or sources invalid)
    function buildLeg(market: string, marketType: string, consensus: number, odds: number | null | undefined): CandidateLeg | null {
        if (odds == null || odds <= 0) return null;
        if (consensus == null || consensus <= 0) return null;
        if (!match.result_url || match.result_url.trim() === '') return null;
        if (!match.datetime) return null; // datetime required
        if (match.sources == null) return null; // sources required
        return {
            match_name: matchName,
            datetime: match.datetime,
            market,
            market_type: marketType,
            consensus,
            odds,
            result_url: match.result_url,
            sources: match.sources,
            tier: 0,
            score: 0,
        };
    }

    // Map market display labels to their correct market_type enum values
    const marketTypeMap: Record<string, string> = {
        '1': 'result',
        'X': 'result',
        '2': 'result',
        'Over 2.5': 'over_under_25',
        'Under 2.5': 'over_under_25',
        'BTTS Yes': 'btts',
        'BTTS No': 'btts',
        'Over 0.5': 'over_under_05',
        'Under 0.5': 'over_under_05',
        'Over 1.5': 'over_under_15',
        'Under 1.5': 'over_under_15',
        'Over 3.5': 'over_under_35',
        'Under 3.5': 'over_under_35',
        'Over 4.5': 'over_under_45',
        'Under 4.5': 'over_under_45',
        '1X': 'double_chance',
        '12': 'double_chance',
        'X2': 'double_chance',
    };

    const hasResultUrl = match.result_url != null && match.result_url.trim() !== '';
    const rowStyle = {
        borderColor: 'var(--border)',
        opacity: hasResultUrl ? 1 : 0.25
    };

    // Create cells for the table row
    const cells = [
        <td key="index" className="px-4 py-3 font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
            {index}
        </td>,
        <td key="datetime" className="px-4 py-3 font-mono text-base" style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
            {dt}
        </td>,
        <td key="home" className="px-4 py-3">
            <span className="font-sans text-base" style={{ color: 'var(--text-primary)' }}>
                {match.home}
            </span>
        </td>,
        <td key="away" className="px-4 py-3">
            <span className="font-sans text-base" style={{ color: 'var(--text-primary)' }}>
                {match.away}
            </span>
        </td>,
        <td key="sources" className="px-4 py-3 text-center">
            <span className="font-mono text-base" style={{ color: 'var(--text-secondary)' }}>
                {match.sources}
            </span>
        </td>,
        <Cell
            key="home-cell"
            pct={match.cons_home}
            odds={match.odds_home}
            isActive={activeMarkets.has('1')}
            isInSlip={inSlipMarkets.has('1')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('1', marketTypeMap['1'], match.cons_home, match.odds_home);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="draw-cell"
            pct={match.cons_draw}
            odds={match.odds_draw}
            isActive={activeMarkets.has('X')}
            isInSlip={inSlipMarkets.has('X')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('X', marketTypeMap['X'], match.cons_draw, match.odds_draw);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="away-cell"
            pct={match.cons_away}
            odds={match.odds_away}
            isActive={activeMarkets.has('2')}
            isInSlip={inSlipMarkets.has('2')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('2', marketTypeMap['2'], match.cons_away, match.odds_away);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="over-cell"
            pct={match.cons_over_25}
            odds={match.odds_over_25}
            isActive={activeMarkets.has('Over 2.5')}
            isInSlip={inSlipMarkets.has('Over 2.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Over 2.5', marketTypeMap['Over 2.5'], match.cons_over_25, match.odds_over_25);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="under-cell"
            pct={match.cons_under_25}
            odds={match.odds_under_25}
            isActive={activeMarkets.has('Under 2.5')}
            isInSlip={inSlipMarkets.has('Under 2.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Under 2.5', marketTypeMap['Under 2.5'], match.cons_under_25, match.odds_under_25);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="btts-yes-cell"
            pct={match.cons_btts_yes}
            odds={match.odds_btts_yes}
            isActive={activeMarkets.has('BTTS Yes')}
            isInSlip={inSlipMarkets.has('BTTS Yes')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('BTTS Yes', marketTypeMap['BTTS Yes'], match.cons_btts_yes, match.odds_btts_yes);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="btts-no-cell"
            pct={match.cons_btts_no}
            odds={match.odds_btts_no}
            isActive={activeMarkets.has('BTTS No')}
            isInSlip={inSlipMarkets.has('BTTS No')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('BTTS No', marketTypeMap['BTTS No'], match.cons_btts_no, match.odds_btts_no);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="over-05-cell"
            pct={match.cons_over_05}
            odds={match.odds_over_05}
            isActive={activeMarkets.has('Over 0.5')}
            isInSlip={inSlipMarkets.has('Over 0.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Over 0.5', marketTypeMap['Over 0.5'], match.cons_over_05, match.odds_over_05);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="under-05-cell"
            pct={match.cons_under_05}
            odds={match.odds_under_05}
            isActive={activeMarkets.has('Under 0.5')}
            isInSlip={inSlipMarkets.has('Under 0.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Under 0.5', marketTypeMap['Under 0.5'], match.cons_under_05, match.odds_under_05);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="over-15-cell"
            pct={match.cons_over_15}
            odds={match.odds_over_15}
            isActive={activeMarkets.has('Over 1.5')}
            isInSlip={inSlipMarkets.has('Over 1.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Over 1.5', marketTypeMap['Over 1.5'], match.cons_over_15, match.odds_over_15);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="under-15-cell"
            pct={match.cons_under_15}
            odds={match.odds_under_15}
            isActive={activeMarkets.has('Under 1.5')}
            isInSlip={inSlipMarkets.has('Under 1.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Under 1.5', marketTypeMap['Under 1.5'], match.cons_under_15, match.odds_under_15);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="over-35-cell"
            pct={match.cons_over_35}
            odds={match.odds_over_35}
            isActive={activeMarkets.has('Over 3.5')}
            isInSlip={inSlipMarkets.has('Over 3.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Over 3.5', marketTypeMap['Over 3.5'], match.cons_over_35, match.odds_over_35);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="under-35-cell"
            pct={match.cons_under_35}
            odds={match.odds_under_35}
            isActive={activeMarkets.has('Under 3.5')}
            isInSlip={inSlipMarkets.has('Under 3.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Under 3.5', marketTypeMap['Under 3.5'], match.cons_under_35, match.odds_under_35);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="over-45-cell"
            pct={match.cons_over_45}
            odds={match.odds_over_45}
            isActive={activeMarkets.has('Over 4.5')}
            isInSlip={inSlipMarkets.has('Over 4.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Over 4.5', marketTypeMap['Over 4.5'], match.cons_over_45, match.odds_over_45);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="under-45-cell"
            pct={match.cons_under_45}
            odds={match.odds_under_45}
            isActive={activeMarkets.has('Under 4.5')}
            isInSlip={inSlipMarkets.has('Under 4.5')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('Under 4.5', marketTypeMap['Under 4.5'], match.cons_under_45, match.odds_under_45);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="dc-1x-cell"
            pct={match.cons_dc_1x}
            odds={match.odds_dc_1x}
            isActive={activeMarkets.has('1X')}
            isInSlip={inSlipMarkets.has('1X')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('1X', marketTypeMap['1X'], match.cons_dc_1x, match.odds_dc_1x);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="dc-12-cell"
            pct={match.cons_dc_12}
            odds={match.odds_dc_12}
            isActive={activeMarkets.has('12')}
            isInSlip={inSlipMarkets.has('12')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('12', marketTypeMap['12'], match.cons_dc_12, match.odds_dc_12);
                if (leg) onCellClick(leg);
            } : undefined}
        />,
        <Cell
            key="dc-x2-cell"
            pct={match.cons_dc_x2}
            odds={match.odds_dc_x2}
            isActive={activeMarkets.has('X2')}
            isInSlip={inSlipMarkets.has('X2')}
            onClick={onCellClick ? () => {
                const leg = buildLeg('X2', marketTypeMap['X2'], match.cons_dc_x2, match.odds_dc_x2);
                if (leg) onCellClick(leg);
            } : undefined}
        />
    ];

    return (
        <BaseDataRow
            isTableRow={true}
            cells={cells}
            className="border-b transition-colors duration-100 group"
            style={rowStyle}
            onMouseEnter={(e: React.MouseEvent<HTMLTableRowElement>) => { if (hasResultUrl) (e.currentTarget as HTMLElement).style.background = 'var(--bg-hover)'; }}
            onMouseLeave={(e: React.MouseEvent<HTMLTableRowElement>) => { if (hasResultUrl) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        />
    );
}
