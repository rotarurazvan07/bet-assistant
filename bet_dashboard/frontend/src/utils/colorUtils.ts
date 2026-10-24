/**
 * Utility functions for color-related operations
 */

// Note: CandidateLeg type is not imported here to avoid circular dependencies.
// The function signature accepts an object with the expected shape.
import { MARKET_COLUMNS } from '../config/marketConfig';

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
    if (leg.status !== 'Live' || !liveScore) return '';
    const m = liveScore.match(/(\d+)\s*[-:]\s*(\d+)/);
    if (!m) return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
    const hs = parseInt(m[1], 10);
    const as = parseInt(m[2], 10);
    const total = hs + as;
    const homeLead = hs > as;
    const awayLead = as > hs;
    const tied = hs === as;
    const key = leg.market.trim();
    const col = MARKET_COLUMNS.find((c) => c.market === key);
    if (!col) return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
    // line from the key suffix: 'over_25' -> 2, 'under_05' -> 0 (tenths)
    const suffix = col.market.slice(-2);
    const tenths = parseInt(suffix, 10);
    if (col.market.indexOf('over_') === 0 && !isNaN(tenths)) {
        return total > tenths / 10 ? 'var(--potential-win)' : 'var(--potential-loss)';
    }
    if (col.market.indexOf('under_') === 0 && !isNaN(tenths)) {
        return total < tenths / 10 ? 'var(--potential-win)' : 'var(--potential-loss)';
    }
    if (col.market.indexOf('_yes') === col.market.length - 4 || col.market.indexOf('_no') === col.market.length - 3) {
        const both = hs > 0 && as > 0;
        const isYes = col.market.slice(-4) === '_yes';
        return both === isYes ? 'var(--potential-win)' : 'var(--potential-loss)';
    }
    if (col.market.slice(-3) === '_1x') return homeLead || tied ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (col.market.slice(-3) === '_12') return homeLead || awayLead ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (col.market.slice(-3) === '_x2') return awayLead || tied ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (col.market === 'home') return homeLead ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (col.market === 'draw') return tied ? 'var(--potential-win)' : 'var(--potential-loss)';
    if (col.market === 'away') return awayLead ? 'var(--potential-win)' : 'var(--potential-loss)';
    return leg.odds > 2.0 ? 'var(--potential-win)' : 'var(--potential-loss)';
}
