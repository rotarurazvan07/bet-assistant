/**
 * Utility functions for color-related operations
 */

// Note: CandidateLeg type is not imported here to avoid circular dependencies.
// The function signature accepts an object with the expected shape.

/**
 * Get color based on consensus percentage
 * @param consensus - Consensus percentage
 * @returns CSS variable reference
 */
export function getConsensusColor(consensus: number): string {
    return consensus >= 80 ? 'var(--cons-high-txt)'
        : consensus >= 60 ? 'var(--cons-mid-txt)'
            : 'var(--cons-low-txt)';
}

/**
 * Get color based on status
 * @param status - Status string
 * @returns CSS variable reference
 */
export function getStatusColor(status: string): string {
    switch (status) {
        case 'Won': return 'var(--win)';
        case 'Lost': return 'var(--loss)';
        case 'Live': return 'var(--live)';
        case 'Pending': return 'var(--pending)';
        default: return 'var(--text-muted)';
    }
}

/**
 * Get status icon based on status
 * @param status - Status string
 * @returns Status icon character
 */
export function getStatusIcon(status: string): string {
    switch (status) {
        case 'Won': return '✓';
        case 'Lost': return '✗';
        case 'Live': return '●';
        default: return '◷';
    }
}

/**
 * Get status for BaseBadge component
 * @param status - Status string
 * @returns Badge status type
 */
export function getStatusBadge(status: string): 'success' | 'error' | 'warning' | 'default' | 'info' {
    switch (status) {
        case 'Won': return 'success';
        case 'Lost': return 'error';
        case 'Live': return 'info';
        case 'Pending': return 'warning';
        default: return 'default';
    }
}

/**
 * Get potential status color for live pending matches
 * Analyzes the current live score and bet market to indicate likely outcome
 * @param leg - Leg object with market, odds, and status properties (shaped like CandidateLeg)
 * @param liveScore - Live score string in format "X - Y" (home - away)
 * @returns CSS variable reference for potential win/loss, or empty string if not applicable
 */
export function getPotentialStatusColor(leg: { market: string; odds: number; status: string }, liveScore?: string): string {
    if (leg.status !== 'Live' || !liveScore) {
        return '';
    }

    const scoreMatch = liveScore.match(/(\d+)\s*[\-:]\s*(\d+)/);
    if (!scoreMatch) {
        return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
    }

    const homeScore = parseInt(scoreMatch[1], 10);
    const awayScore = parseInt(scoreMatch[2], 10);
    const market = leg.market.trim();
    const homeLeading = homeScore > awayScore;
    const awayLeading = awayScore > homeScore;
    const isTied = homeScore === awayScore;
    const total = homeScore + awayScore;

    // ── 1X2 ──
    if (market === '1') return homeLeading ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (market === 'X') return isTied    ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (market === '2') return awayLeading ? 'var(--potential-win)' : 'var(--potential-loss)';

    // ── BTTS ──
    if (market === 'BTTS Yes') {
        const bothScored = homeScore > 0 && awayScore > 0;
        return bothScored ? 'var(--potential-win)' : 'var(--potential-loss)';
    }
    if (market === 'BTTS No') {
        const bothScored = homeScore > 0 && awayScore > 0;
        return bothScored ? 'var(--potential-loss)' : 'var(--potential-win)';
    }

    // ── Over/Under ──
    const overMatch = market.match(/^Over ([\d.]+)$/);
    if (overMatch) {
        const line = parseFloat(overMatch[1]);
        return total > line ? 'var(--potential-win)' : 'var(--potential-loss)';
    }

    const underMatch = market.match(/^Under ([\d.]+)$/);
    if (underMatch) {
        const line = parseFloat(underMatch[1]);
        return total < line ? 'var(--potential-win)' : 'var(--potential-loss)';
    }

    // ── Double Chance ──
    if (market === '1X') return (homeLeading || isTied) ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (market === '12') return (homeLeading || awayLeading) ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (market === 'X2') return (awayLeading || isTied) ? 'var(--potential-win)' : 'var(--potential-loss)';

    // ── Default ──
    return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
}
