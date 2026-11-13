export const MIN_SAMPLE_SIZE = 10;
export const INTERSECTION_MIN_SAMPLE_SIZE = 5;

export type TrustLevel = 'high' | 'medium' | 'low';

/** Classify a numeric trust score into a badge level (thresholds: high > 0.6, low < 0.3). */
export function trustLevel(score: number): TrustLevel {
    if (score > 0.6) return 'high';
    if (score < 0.3) return 'low';
    return 'medium';
}

/** Sort source rows by trust score (numeric), with source name as tiebreaker. */
export function sortByTrust<T extends { trust_score?: number; source: string }>(rows: T[], dir: 'asc' | 'desc' = 'desc'): T[] {
    return [...rows].sort((a, b) => {
        const diff = (b.trust_score ?? 0) - (a.trust_score ?? 0);
        if (diff !== 0) return dir === 'desc' ? diff : -diff;
        return a.source.localeCompare(b.source);
    });
}

export interface RankableItem {
    name: string;
    edge: number;
    legs: number;
    [key: string]: unknown;
}

export interface TopWorstResult<T extends RankableItem = RankableItem> {
    top: T[];
    worst: T[];
}

/**
 * Filter items that meet the minimum-legs threshold for single-dimension intelligence.
 */
export function filterEligibleItems<T extends { legs: number }>(items: T[], minLegs = MIN_SAMPLE_SIZE): T[] {
    return items.filter(item => typeof item.legs === 'number' && item.legs >= minLegs);
}

/**
 * Pure function to rank eligible items into non-overlapping Top N and Worst N by edge.
 * Top has priority: take up to N best items by edge.
 * Worst takes up to N items from the remaining eligible items (the ones with the lowest edge).
 *
 * Guarantees:
 * 1. Top and Worst NEVER intersect.
 * 2. If fewer than 2*n items exist, Worst gets fewer items (or 0).
 * 3. If items is empty, both are empty.
 */
export function rankTopWorst<T extends RankableItem>(items: T[], n = 3): TopWorstResult<T> {
    if (!items || items.length === 0 || n <= 0) {
        return { top: [], worst: [] };
    }

    // Sort descending by edge. For ties, sort alphabetically by name for deterministic ordering.
    const sorted = [...items].sort((a, b) => {
        if (b.edge !== a.edge) {
            return b.edge - a.edge;
        }
        return a.name.localeCompare(b.name);
    });

    const topCount = Math.min(n, sorted.length);
    const top = sorted.slice(0, topCount);

    const remaining = sorted.slice(topCount);
    if (remaining.length === 0) {
        return { top, worst: [] };
    }

    // Take up to n items with the lowest edge from remaining
    // (i.e. the tail of the sorted list)
    const worstCount = Math.min(n, remaining.length);
    // Take from the end of sorted list (lowest edges)
    const worstSlice = sorted.slice(sorted.length - worstCount);
    // Sort worst by lowest edge first
    const worst = [...worstSlice].sort((a, b) => {
        if (a.edge !== b.edge) {
            return a.edge - b.edge;
        }
        return a.name.localeCompare(b.name);
    });

    return { top, worst };
}
