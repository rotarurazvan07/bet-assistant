import type { Match, CandidateLeg } from '../types';

// Consensus cell coloring
function consCell(pct: number, odds: number | null | undefined) {
    if (pct <= 0) return null;
    const bg = pct >= 80 ? 'var(--cons-high)'
        : pct >= 60 ? 'var(--cons-mid)'
            : 'var(--cons-low)';
    const col = pct >= 80 ? 'var(--cons-high-txt)'
        : pct >= 60 ? 'var(--cons-mid-txt)'
            : 'var(--cons-low-txt)';
    return { bg, col, pct, odds };
}

function Cell({ pct, odds, onClick }: { pct: number; odds: number | null | undefined; onClick?: () => void }) {
    const c = consCell(pct, odds);
    if (!c) return <td className="px-2 py-2 text-center">
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>
    </td>;
    const oddsDisplay = c.odds != null ? c.odds.toFixed(2) : '—';
    return (
        <td className="px-1 py-1.5 text-center" style={{ minWidth: 52 }}>
            <div
                className="rounded px-1 py-0.5 inline-flex flex-col items-center gap-px leading-none cursor-pointer transition-opacity hover:opacity-80"
                style={{ background: c.bg }}
                onClick={onClick}
                role="button"
                tabIndex={0}
                aria-label={`Select ${pct}% at @${oddsDisplay}`}
            >
                <span className="font-mono font-bold text-[11px]" style={{ color: c.col }}>
                    {c.pct.toFixed(0)}%
                </span>
                {c.odds != null && c.odds > 1 && (
                    <span className="font-mono text-[10px]" style={{ color: c.col, opacity: .8 }}>
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
}

export default function MatchRow({ match, index, onCellClick }: Props) {
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
        'Over 2.5': 'over_under_2.5',
        'Under 2.5': 'over_under_2.5',
        'BTTS Yes': 'btts',
        'BTTS No': 'btts',
    };

    const hasResultUrl = match.result_url != null && match.result_url.trim() !== '';
    const rowStyle = { borderColor: 'var(--border)', opacity: hasResultUrl ? 1 : 0.25 };

    return (
        <tr className="border-b transition-colors duration-100 group"
            style={rowStyle}
            onMouseEnter={e => { if (hasResultUrl) e.currentTarget.style.background = 'var(--bg-hover)'; }}
            onMouseLeave={e => { if (hasResultUrl) e.currentTarget.style.background = 'transparent'; }}>

            <td className="px-3 py-2 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
                {index}
            </td>
            <td className="px-3 py-2 font-mono text-[11px]" style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                {dt}
            </td>
            <td className="px-3 py-2">
                <span className="font-sans text-[13px]" style={{ color: 'var(--text-primary)' }}>
                    {match.home}
                </span>
            </td>
            <td className="px-3 py-2">
                <span className="font-sans text-[13px]" style={{ color: 'var(--text-primary)' }}>
                    {match.away}
                </span>
            </td>
            <td className="px-3 py-2 text-center">
                <span className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    {match.sources}
                </span>
            </td>

            <Cell
                pct={match.cons_home}
                odds={match.odds_home}
                onClick={onCellClick ? () => {
                    const leg = buildLeg('1', marketTypeMap['1'], match.cons_home, match.odds_home);
                    if (leg) onCellClick(leg);
                } : undefined}
            />
            <Cell
                pct={match.cons_draw}
                odds={match.odds_draw}
                onClick={onCellClick ? () => {
                    const leg = buildLeg('X', marketTypeMap['X'], match.cons_draw, match.odds_draw);
                    if (leg) onCellClick(leg);
                } : undefined}
            />
            <Cell
                pct={match.cons_away}
                odds={match.odds_away}
                onClick={onCellClick ? () => {
                    const leg = buildLeg('2', marketTypeMap['2'], match.cons_away, match.odds_away);
                    if (leg) onCellClick(leg);
                } : undefined}
            />
            <Cell
                pct={match.cons_over}
                odds={match.odds_over}
                onClick={onCellClick ? () => {
                    const leg = buildLeg('Over 2.5', marketTypeMap['Over 2.5'], match.cons_over, match.odds_over);
                    if (leg) onCellClick(leg);
                } : undefined}
            />
            <Cell
                pct={match.cons_under}
                odds={match.odds_under}
                onClick={onCellClick ? () => {
                    const leg = buildLeg('Under 2.5', marketTypeMap['Under 2.5'], match.cons_under, match.odds_under);
                    if (leg) onCellClick(leg);
                } : undefined}
            />
            <Cell
                pct={match.cons_btts_yes}
                odds={match.odds_btts_yes}
                onClick={onCellClick ? () => {
                    const leg = buildLeg('BTTS Yes', marketTypeMap['BTTS Yes'], match.cons_btts_yes, match.odds_btts_yes);
                    if (leg) onCellClick(leg);
                } : undefined}
            />
            <Cell
                pct={match.cons_btts_no}
                odds={match.odds_btts_no}
                onClick={onCellClick ? () => {
                    const leg = buildLeg('BTTS No', marketTypeMap['BTTS No'], match.cons_btts_no, match.odds_btts_no);
                    if (leg) onCellClick(leg);
                } : undefined}
            />

        </tr>
    );
}
