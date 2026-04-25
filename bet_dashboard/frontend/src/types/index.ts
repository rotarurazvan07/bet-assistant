// ── Match ─────────────────────────────────────────────────────────────────────

export interface Match {
    match_id: string;
    datetime: string | null;
    home: string;
    away: string;
    sources: number;
    cons_home: number; cons_draw: number; cons_away: number;
    cons_over: number; cons_under: number;
    cons_btts_yes: number; cons_btts_no: number;
    odds_home: number; odds_draw: number; odds_away: number;
    odds_over: number; odds_under: number;
    odds_btts_yes: number; odds_btts_no: number;
    result_url: string | null;
}

export interface MatchesPage {
    total: number; page: number; page_size: number; total_pages: number;
    matches: Match[];
}

// ── Builder ───────────────────────────────────────────────────────────────────

export const ALL_MARKETS = ['1', 'X', '2', 'Over 2.5', 'Under 2.5', 'BTTS Yes', 'BTTS No'];

export interface BuilderConfig {
    target_odds: number;
    target_legs: number;
    max_legs_overflow: number | null;
    consensus_floor: number;
    min_odds: number;
    included_markets: string[] | null;
    tolerance_factor: number | null;
    stop_threshold: number | null;
    min_legs_fill_ratio: number;
    quality_vs_balance: number;   // 0-1
    consensus_vs_sources: number; // 0-1
    date_from: string | null;
    date_to: string | null;
    // Advanced
    consensus_shrinkage_k: number | null;
    min_source_edge: number | null;
    max_single_leg_odds: number | null;
    tol_lower: number | null;
    tol_upper: number | null;
    balance_decay: 'linear' | 'gaussian';
    min_pick_quality: number | null;
}

export interface CandidateLeg {
    match_name: string;
    datetime: string | null;
    market: string;
    market_type: string;
    consensus: number;
    odds: number;
    result_url: string | null;
    sources: number;
    tier: number;
    score: number;
}

export interface PreviewResult {
    legs: CandidateLeg[];
    total_odds: number;
    pending_urls: string[];
}

// ── Profiles ──────────────────────────────────────────────────────────────────

export interface Profile {
    target_odds: number; target_legs: number;
    max_legs_overflow: number | null;
    consensus_floor: number; min_odds: number;
    included_markets: string[] | null;
    tolerance_factor: number | null; stop_threshold: number | null;
    min_legs_fill_ratio: number; quality_vs_balance: number; consensus_vs_sources: number;
    units: number;
    target_payout?: number | null;
    run_daily_count: number;
    date_from?: null; date_to?: null; excluded_urls?: null;
    // Advanced
    consensus_shrinkage_k: number | null;
    min_source_edge: number | null;
    max_single_leg_odds: number | null;
    tol_lower: number | null;
    tol_upper: number | null;
    balance_decay: 'linear' | 'gaussian';
    min_pick_quality: number | null;
}

export type ProfilesMap = Record<string, Profile>;

// ── Slips ─────────────────────────────────────────────────────────────────────

export interface ManualLegIn {
    match_name: string;
    market: string;
    market_type: string;
    odds: number;
    result_url: string;
    datetime: string;  // ISO format datetime, required
    consensus: number;  // 0-100 percentage
    sources: number;  // number of sources
}

export interface BetLeg {
    match_name: string; datetime: string | null;
    market: string; market_type: string | null;
    odds: number; status: string; result_url: string | null;
}

export interface BetSlip {
    slip_id: number; date_generated: string; profile: string;
    total_odds: number; units: number; slip_status: string; legs: BetLeg[];
    net_profit?: number;  // Optional: calculated on backend for settled slips, or client-side
}

export interface SlipsPage {
    slips: BetSlip[];
    stats: SlipStats;
    profiles: string[];
}

export interface SlipStats {
    total_settled: number; total_won_count: number;
    win_rate: number; implied_win_rate: number; edge: number;
    total_units_bet: number; gross_return: number;
    net_profit: number; roi_percentage: number;
    avg_odds: number; avg_units: number; units_std: number;
    pending_count: number; sharpe_ratio: number | null;
}

export type LiveData = Record<string, { score: string; minute: string }>;

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface HistoryRecord {
    date: string; slips_count: number; units_bet: number;
    net_profit: number; cumulative_profit: number; cumulative_bet: number;
    roi_percentage: number; win_rate: number;
}

export interface MarketAccuracy {
    market: string; won: number; lost: number; total: number; accuracy: number;
}

export interface PnlByMarket {
    market: string; won: number; lost: number; net_profit: number;
}

export interface OddsDistBucket {
    range: string; count: number; wins: number; losses: number;
    win_rate: number; implied_win_rate: number; avg_odds: number; edge: number;
}

export interface CorrelationRecord {
    legs_count: number; total_odds: number; units: number;
    status: string; profit: number;
}

export interface ProfileScatterPoint {
    profile: string; avg_odds: number; win_rate: number;
    net_profit: number; volume: number; break_even_win_rate: number;
}

export interface MarketBreakdown {
    market: string; legs: number; won: number; lost: number;
    win_rate: number; implied_win_rate: number; edge: number;
    avg_odds: number; net_profit: number;
}

export interface RollingEdgePoint {
    date: string; rolling_edge: number; rolling_win_rate: number;
    rolling_implied: number; sample_size: number;
}

export interface DrawdownPoint {
    date: string; drawdown: number; peak: number; cumulative_profit: number;
}

export interface ReturnDistBin {
    range: string; range_end: string; count: number; is_positive: boolean;
}

export interface ReturnDistribution {
    bins: ReturnDistBin[]; mean: number; median: number;
}

export interface TimePatternItem {
    key: string; total: number; won: number; win_rate: number;
}

export interface AnalyticsData {
    history: HistoryRecord[];
    market_accuracy: MarketAccuracy[];
    pnl_by_market: PnlByMarket[];
    odds_distribution: OddsDistBucket[];
    correlation: CorrelationRecord[];
    profile_scatter: ProfileScatterPoint[];
    stats: SlipStats;
    profiles: string[];
    market_breakdown: MarketBreakdown[];
    rolling_edge: RollingEdgePoint[];
    drawdown: DrawdownPoint[];
    return_distribution: ReturnDistribution | null;
    time_patterns: { day_of_week: TimePatternItem[]; hour: TimePatternItem[] } | null;
}

// ── Services ──────────────────────────────────────────────────────────────────

export interface ServiceInfo {
    name: string; description: string;
    enabled: boolean; alive: boolean;
    hour: number | null; interval_seconds: number | null;
    next_run: string | null;
}

export interface ServicesData {
    services: Record<string, ServiceInfo>;
    pull_hour: number; generate_hour: number; server_time: string;
}

// ── WebSocket events ──────────────────────────────────────────────────────────

export type WsEventName =
    | 'matches_updated'
    | 'slips_updated'
    | 'service_toggled'
    | 'pong';

export interface WsEvent {
    event: WsEventName;
    timestamp?: string;
    name?: string;
    enabled?: boolean;
    live_data?: Record<string, { score: string; minute: string }>;
}
