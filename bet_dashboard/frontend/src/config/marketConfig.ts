import type { components } from '../types/api.generated';

// Canonical unions generated from the backend OpenAPI schema (single source:
// bet_framework.markets enums). Identity lives in Python; order lives here.
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
 * lives in bet_framework.markets.keys.stripped_key.
 */
export function strippedKey(oddsKey: string): string {
    return oddsKey.startsWith('odds_') ? oddsKey.slice('odds_'.length) : oddsKey;
}

/**
 * Market columns in display/PRESENTATION order only - this array is the one
 * place column order lives. To reorder columns, reorder entries here; it can
 * never affect backend behavior (keys are bound by identity, not position).
 */
export const MARKET_COLUMNS: MarketColumn[] = [
    // Identity = canonical MarketKey values (DB/Odds field spellings, U1 -
    // ); label = presentation text. Bind by market, never position.
    { market: 'home', label: '1', consKey: 'cons_home', oddsKey: 'odds_home', marketType: 'result' },
    { market: 'draw', label: 'X', consKey: 'cons_draw', oddsKey: 'odds_draw', marketType: 'result' },
    { market: 'away', label: '2', consKey: 'cons_away', oddsKey: 'odds_away', marketType: 'result' },
    { market: 'over_25', label: 'O2.5', consKey: 'cons_over_25', oddsKey: 'odds_over_25', marketType: 'over_under_25' },
    { market: 'under_25', label: 'U2.5', consKey: 'cons_under_25', oddsKey: 'odds_under_25', marketType: 'over_under_25' },
    { market: 'btts_yes', label: 'BTTS Y', consKey: 'cons_btts_yes', oddsKey: 'odds_btts_yes', marketType: 'btts' },
    { market: 'btts_no', label: 'BTTS N', consKey: 'cons_btts_no', oddsKey: 'odds_btts_no', marketType: 'btts' },
    { market: 'over_05', label: 'O0.5', consKey: 'cons_over_05', oddsKey: 'odds_over_05', marketType: 'over_under_05' },
    { market: 'under_05', label: 'U0.5', consKey: 'cons_under_05', oddsKey: 'odds_under_05', marketType: 'over_under_05' },
    { market: 'over_15', label: 'O1.5', consKey: 'cons_over_15', oddsKey: 'odds_over_15', marketType: 'over_under_15' },
    { market: 'under_15', label: 'U1.5', consKey: 'cons_under_15', oddsKey: 'odds_under_15', marketType: 'over_under_15' },
    { market: 'over_35', label: 'O3.5', consKey: 'cons_over_35', oddsKey: 'odds_over_35', marketType: 'over_under_35' },
    { market: 'under_35', label: 'U3.5', consKey: 'cons_under_35', oddsKey: 'odds_under_35', marketType: 'over_under_35' },
    { market: 'over_45', label: 'O4.5', consKey: 'cons_over_45', oddsKey: 'odds_over_45', marketType: 'over_under_45' },
    { market: 'under_45', label: 'U4.5', consKey: 'cons_under_45', oddsKey: 'odds_under_45', marketType: 'over_under_45' },
    { market: 'dc_1x', label: '1X', consKey: 'cons_dc_1x', oddsKey: 'odds_dc_1x', marketType: 'double_chance' },
    { market: 'dc_12', label: '12', consKey: 'cons_dc_12', oddsKey: 'odds_dc_12', marketType: 'double_chance' },
    { market: 'dc_x2', label: 'X2', consKey: 'cons_dc_x2', oddsKey: 'odds_dc_x2', marketType: 'double_chance' },
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

// Canonical key -> display label lookup (U1: wire payloads carry DB field
// spellings like 'home'; presentation must still show human labels like '1').
const LABEL_BY_KEY: Record<string, string> = Object.fromEntries(
    MARKET_COLUMNS.map((col) => [col.market, col.label]),
);

/** Display label for a canonical market key; falls back to the raw key. */
export function marketLabel(key: string): string {
    return LABEL_BY_KEY[key] ?? key;
}
