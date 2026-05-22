import type { Match, CandidateLeg, OddsMovementSummary, OddsMovementDirection } from '../types';
import { BaseDataRow } from './ui/BaseDataRow';
import { MARKET_COLUMNS } from '../config/marketConfig';
import { OddsMovementIndicator } from './OddsMovementIndicator';

/**
 * MarketRow Component
 *
 * Renders a table row for a match with market cells showing consensus percentages,
 * odds, and optional odds movement indicators.
 *
 * The odds movement indicator is displayed when there is significant odds movement
 * (up or down) for a particular market. The mapping between market display names
 * and the movement keys in OddsMovementSummary is generated dynamically from
 * MARKET_COLUMNS configuration to ensure consistency and avoid hardcoding.
 *
 * Movement key generation: oddsKey (e.g., 'odds_over_25') -> remove 'odds_' prefix -> 'over_25'
 */

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
    movement?: OddsMovementDirection;
}

function Cell({ pct, odds, onClick, isActive = false, isInSlip = false, movement }: CellProps) {
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
                    <span className="font-mono text-sm inline-flex items-center gap-0.5" style={{ color: textColor, opacity: isInSlip || isActive ? 1 : 0.8 }}>
                        @{oddsDisplay}
                        <OddsMovementIndicator direction={movement} size="sm" />
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
    movement?: OddsMovementSummary;
    visibleColumns?: Set<string>;
}

export default function MatchRow({ match, index, onCellClick, activeMarkets = new Set(), inSlipMarkets = new Set(), movement, visibleColumns }: Props) {
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
        if (!match.datetime) return null;
        if (match.sources == null) return null;
        return {
            match_name: matchName,
            datetime: match.datetime,
            market,
            market_type: marketType,
            consensus,
            odds,
            result_url: match.result_url,
            sources: match.sources,
            league: match.league,
            tier: 0,
            score: 0,
        };
    }

    const hasResultUrl = match.result_url != null && match.result_url.trim() !== '';
    const rowStyle = {
        borderColor: 'var(--border)',
        opacity: hasResultUrl ? 1 : 0.25
    };

    // Access match properties dynamically using type assertion
    const matchData = match as unknown as Record<string, unknown>;

    // Create fixed cells
    const fixedCells = [
        <td key="index" className="px-4 py-3 font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
            {index}
        </td>,
        <td key="datetime" className="px-4 py-3 font-mono text-base" style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
            {dt}
        </td>,
            <td key="home" className="px-4 py-3 sticky-col" style={{ left: 0, minWidth: 140, maxWidth: 180 }}>
            <span className="font-sans text-base" style={{ color: 'var(--text-primary)' }}>
                {match.home}
            </span>
        </td>,
            <td key="away" className="px-4 py-3 sticky-col" style={{ left: 140, minWidth: 140, maxWidth: 180 }}>
            <span className="font-sans text-base" style={{ color: 'var(--text-primary)' }}>
                {match.away}
            </span>
        </td>,
        <td key="sources" className="px-4 py-3 text-center">
            <span className="font-mono text-base" style={{ color: 'var(--text-secondary)' }}>
                {match.sources}
            </span>
        </td>,
        <td key="league" className="px-4 py-3">
            <span className="font-sans text-sm" style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                {match.league ?? '—'}
            </span>
        </td>,
    ];

    /**
     * Dynamically generate market-to-movement-key mapping from MARKET_COLUMNS.
     *
     * This ensures:
     * 1. All configured markets have corresponding movement keys
     * 2. No hardcoded mappings that can become stale
     * 3. Automatic inclusion of new markets when MARKET_COLUMNS is updated
     *
     * Transformation: oddsKey (e.g., 'odds_over_25') -> strip 'odds_' -> 'over_25'
     * This matches the key names in OddsMovementSummary interface.
     */
    const marketToMovementKey: Record<string, keyof OddsMovementSummary> = {};
    MARKET_COLUMNS.forEach(col => {
      const movementKey = col.oddsKey.replace('odds_', '') as keyof OddsMovementSummary;
      marketToMovementKey[col.market] = movementKey;
    });

    // Create market cells dynamically from config (filtered by visibility)
    const marketCells = MARKET_COLUMNS.filter(col => !visibleColumns || visibleColumns.has(col.market)).map(col => {
        const consensus = matchData[col.consKey] as number;
        const odds = matchData[col.oddsKey] as number | null | undefined;
        const movementKey = marketToMovementKey[col.market];
        const cellMovement = movement && movementKey ? movement[movementKey] : undefined;

        return (
            <Cell
                key={col.market}
                pct={consensus}
                odds={odds}
                isActive={activeMarkets.has(col.market)}
                isInSlip={inSlipMarkets.has(col.market)}
                movement={cellMovement}
                onClick={onCellClick ? () => {
                    const leg = buildLeg(col.market, col.marketType, consensus, odds);
                    if (leg) onCellClick(leg);
                } : undefined}
            />
        );
    });

    const cells = [...fixedCells, ...marketCells];

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