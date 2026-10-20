import type { components } from '../types/api.generated';

// Canonical unions generated from the backend OpenAPI schema (single source:
// bet_framework.marksets enums). Identity lives in Python; order lives here.
type MarketKey = components['schemas']['MarketKey'];
type MarketType = components['schemas']['MarketType'];

/**
 * Presentation order + label overrides ONLY. Identity (market keys, column
 * keys, market types) is owned by the canonical backend catalog and mirrored
 * here through generated types (src/types/api.generated.ts); this file is the
 * only place display order lives. Reordering columns cannot affect backend
 * behavior - bind strictly by key.
 */

export interface MarketColumn {
    market: MarketKey;     // Canonical market identity (generated union)
    label: string;         // Display label in table header
    consKey: string;       // Key for consensus value in Match object
    oddsKey: string;       // Key for odds value in Match object
    marketType: MarketType; // Canonical market type (generated union)
}

/**
 * Strip the 'odds_' prefix from an odds column key (movement payload keys).
 * The single location of this convention on the frontend - the backend side
 * lives in bet_framework.marks.keys.stripped_key.
 */
export function strippedKey(oddsKey: string): string {
    return oddsKey.startsWith('odds_') ? oddsKey.slice('odds_'.length) : oddsKey;
}

/**
 * Market columns in display order.
 * To reorder columns, simply reorder entries in this array.
 */
export const MARKET_COLUMNS: MarketColumn[] = [
    { market: '1', label: '1', consKey: 'cons_home', oddsKey: 'odds_home', marketType: 'result' },
    { market: 'X', label: 'X', consKey: 'cons_draw', oddsKey: 'odds_draw', marketType: 'result' },
    { market: '2', label: '2', consKey: 'cons_away', oddsKey: 'odds_away', marketType: 'result' },
    { market: 'Over 2.5', label: 'O2.5', consKey: 'cons_over_25', oddsKey: 'odds_over_25', marketType: 'over_under_25' },
    { market: 'Under 2.5', label: 'U2.5', consKey: 'cons_under_25', oddsKey: 'odds_under_25', marketType: 'over_under_25' },
    { market: 'BTTS Yes', label: 'BTTS Y', consKey: 'cons_btts_yes', oddsKey: 'odds_btts_yes', marketType: 'btts' },
    { market: 'BTTS No', label: 'BTTS N', consKey: 'cons_btts_no', oddsKey: 'odds_btts_no', marketType: 'btts' },
    { market: 'Over 0.5', label: 'O0.5', consKey: 'cons_over_05', oddsKey: 'odds_over_05', marketType: 'over_under_05' },
    { market: 'Under 0.5', label: 'U0.5', consKey: 'cons_under_05', oddsKey: 'odds_under_05', marketType: 'over_under_05' },
    { market: 'Over 1.5', label: 'O1.5', consKey: 'cons_over_15', oddsKey: 'odds_over_15', marketType: 'over_under_15' },
    { market: 'Under 1.5', label: 'U1.5', consKey: 'cons_under_15', oddsKey: 'odds_under_15', marketType: 'over_under_15' },
    { market: 'Over 3.5', label: 'O3.5', consKey: 'cons_over_35', oddsKey: 'odds_over_35', marketType: 'over_under_35' },
    { market: 'Under 3.5', label: 'U3.5', consKey: 'cons_under_35', oddsKey: 'odds_under_35', marketType: 'over_under_35' },
    { market: 'Over 4.5', label: 'O4.5', consKey: 'cons_over_45', oddsKey: 'odds_over_45', marketType: 'over_under_45' },
    { market: 'Under 4.5', label: 'U4.5', consKey: 'cons_under_45', oddsKey: 'odds_under_45', marketType: 'over_under_45' },
    { market: '1X', label: '1X', consKey: 'cons_dc_1x', oddsKey: 'odds_dc_1x', marketType: 'double_chance' },
    { market: '12', label: '12', consKey: 'cons_dc_12', oddsKey: 'odds_dc_12', marketType: 'double_chance' },
    { market: 'X2', label: 'X2', consKey: 'cons_dc_x2', oddsKey: 'odds_dc_x2', marketType: 'double_chance' },
];

/**
 * Table column definition for headers.
 */
export interface TableColumn {
    key: string;
    label: string;
    wide?: boolean;
}

/**
 * Fixed columns that appear before market columns.
 */
export const FIXED_COLUMNS: TableColumn[] = [
    { key: 'datetime', label: 'Date' },
    { key: 'home', label: 'Home', wide: true },
    { key: 'away', label: 'Away', wide: true },
    { key: 'sources', label: 'Sources' },
    { key: 'league', label: 'League', wide: true },
];

/**
 * Generate full column list for table headers.
 */
export function getTableColumns(): TableColumn[] {
    return [
        ...FIXED_COLUMNS,
        ...MARKET_COLUMNS.map(m => ({ key: m.consKey, label: m.label })),
    ];
}

/**
 * Set of all allowed market identifiers (for validation).
 */
export const ALLOWED_MARKETS = new Set(MARKET_COLUMNS.map(m => m.market));

/**
 * List of all market identifiers in order.
 */
export const ALL_MARKETS = MARKET_COLUMNS.map(m => m.market);