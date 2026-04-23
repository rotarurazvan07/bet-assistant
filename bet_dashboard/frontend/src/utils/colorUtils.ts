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
    // Only apply for live legs (the caller should ensure slip is pending/live)
    if (leg.status !== 'Live' || !liveScore) {
        return '';
    }

    // Parse live score: expected format "X - Y"
    const scoreMatch = liveScore.match(/(\d+)\s*-\s*(\d+)/);
    if (!scoreMatch) {
        // If we can't parse the score, fallback to odds heuristic
        return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
    }

    const homeScore = parseInt(scoreMatch[1], 10);
    const awayScore = parseInt(scoreMatch[2], 10);
    const market = leg.market.toLowerCase();
    const homeLeading = homeScore > awayScore;
    const awayLeading = awayScore > homeScore;
    const isTied = homeScore === awayScore;

    // 1X2 markets
    if (market.includes('1') || market.includes('home') || market.includes('1x2')) {
        // Home win bet (1)
        if (homeLeading) return 'var(--potential-win)';
        if (awayLeading) return 'var(--potential-loss)';
        // Tied: for 1X2, draw is also an option; treat as neutral or slight edge based on odds
        return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
    }
    if (market.includes('2') || market.includes('away')) {
        // Away win bet (2)
        if (awayLeading) return 'var(--potential-win)';
        if (homeLeading) return 'var(--potential-loss)';
        return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
    }
    if (market.includes('x') || market.includes('draw')) {
        // Draw bet (X)
        if (isTied) return 'var(--potential-win)';
        // Not tied means draw won't happen → likely loss
        return 'var(--potential-loss)';
    }

    // Over/Under markets
    if (market.includes('over') || market.includes('over ')) {
        // Extract the line from market like "Over 2.5"
        const overMatch = market.match(/over\s*([\d.]+)/i);
        if (overMatch) {
            const line = parseFloat(overMatch[1]);
            const totalScore = homeScore + awayScore;
            if (totalScore > line) return 'var(--potential-win)';
            if (totalScore < line) return 'var(--potential-loss)';
            // Equal: depends on if we are close, but likely loss if line not reached yet
            return 'var(--potential-loss)';
        }
        // Fallback for Over without line
        return homeLeading || awayLeading ? 'var(--potential-win)' : 'var(--potential-loss)';
    }
    if (market.includes('under') || market.includes('under ')) {
        const underMatch = market.match(/under\s*([\d.]+)/i);
        if (underMatch) {
            const line = parseFloat(underMatch[1]);
            const totalScore = homeScore + awayScore;
            if (totalScore < line) return 'var(--potential-win)';
            if (totalScore > line) return 'var(--potential-loss)';
            return 'var(--potential-loss)';
        }
        return homeLeading || awayLeading ? 'var(--potential-loss)' : 'var(--potential-win)';
    }

    // BTTS markets
    if (market.includes('btts') || market.includes('both teams')) {
        const bothScored = homeScore > 0 && awayScore > 0;
        if (market.includes('yes')) {
            return bothScored ? 'var(--potential-win)' : 'var(--potential-loss)';
        } else {
            // BTTS No
            return bothScored ? 'var(--potential-loss)' : 'var(--potential-win)';
        }
    }

    // Default heuristic based on odds
    return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
}
