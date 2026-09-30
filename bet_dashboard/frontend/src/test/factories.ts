// Test data factories (issue #63, cycle 9). Every generator matches the
// corresponding interface in src/types/index.ts exactly — defaults are valid,
// overrides are explicit (data-factories knowledge fragment).

import type {
    Match, MatchesPage, SourcePrediction,
    BetLeg, BetSlip, SlipsPage, SlipStats,
    AnalyticsData, HistoryRecord, MarketAccuracy, PnlByMarket, OddsDistBucket,
    CorrelationRecord, ProfileScatterPoint, MarketBreakdown, LeagueBreakdown,
    RollingEdgePoint, DrawdownPoint, ReturnDistribution, TimePatternItem,
    ServiceInfo, ServicesData, Profile, ProfilesMap,
    CandidateLeg, PreviewResult, OddsHistory, OddsSnapshot, OddsMovementSummary,
} from '../types';

// ── primitives ──────────────────────────────────────────────────────────────

export function makeSourcePrediction(overrides: Partial<SourcePrediction> = {}): SourcePrediction {
    return { source: 'predictz', home: 2, away: 1, ...overrides };
}

// ── matches ────────────────────────────────────────────────────────────────

export function makeMatch(overrides: Partial<Match> = {}): Match {
    return {
        match_id: 'match_1_ab12cd34',
        datetime: '2026-09-25T15:00:00',
        home: 'Arsenal',
        away: 'Chelsea',
        sources: 4,
        cons_home: 75, cons_draw: 15, cons_away: 10,
        cons_over_25: 55, cons_under_25: 45,
        cons_btts_yes: 60, cons_btts_no: 40,
        cons_over_05: 90, cons_under_05: 10,
        cons_over_15: 70, cons_under_15: 30,
        cons_over_35: 30, cons_under_35: 70,
        cons_over_45: 15, cons_under_45: 85,
        cons_dc_1x: 80, cons_dc_12: 70, cons_dc_x2: 30,
        odds_home: 1.9, odds_draw: 3.4, odds_away: 4.2,
        odds_over_25: 1.8, odds_under_25: 2.0,
        odds_btts_yes: 1.9, odds_btts_no: 1.9,
        odds_over_05: 1.1, odds_under_05: 8.0,
        odds_over_15: 1.3, odds_under_15: 3.2,
        odds_over_35: 2.8, odds_under_35: 1.4,
        odds_over_45: 5.5, odds_under_45: 1.1,
        odds_dc_1x: 1.2, odds_dc_12: 1.3, odds_dc_x2: 1.5,
        result_url: 'https://example.com/match/1',
        league: 'England',
        ...overrides,
    };
}

export function makeMatchesPage(overrides: Partial<MatchesPage> = {}): MatchesPage {
    return {
        total: 1, page: 1, page_size: 20, total_pages: 1,
        matches: [makeMatch()],
        ...overrides,
    };
}

// ── slips ─────────────────────────────────────────────────────────────────

export function makeBetLeg(overrides: Partial<BetLeg> = {}): BetLeg {
    return {
        match_name: 'Arsenal vs Chelsea',
        datetime: '2026-09-25T15:00:00',
        market: 'Home',
        market_type: 'Result',
        odds: 1.9,
        status: 'Pending',
        result_url: 'https://example.com/match/1',
        league: 'England',
        predictions: [makeSourcePrediction()],
        final_score: null,
        ...overrides,
    };
}

export function makeSlip(overrides: Partial<BetSlip> = {}): BetSlip {
    return {
        slip_id: 1,
        date_generated: '2026-09-24',
        profile: 'low',
        total_odds: 1.9,
        units: 1.0,
        slip_status: 'Pending',
        legs: [makeBetLeg()],
        ...overrides,
    };
}

export function makeSlipStats(overrides: Partial<SlipStats> = {}): SlipStats {
    return {
        total_settled: 3, total_won_count: 2,
        win_rate: 66.67, implied_win_rate: 52.63, edge: 14.04,
        total_units_bet: 3.0, gross_return: 5.8, net_profit: 2.8,
        roi_percentage: 93.33, avg_odds: 1.9, avg_units: 1.0, units_std: 0.0,
        pending_count: 1, sharpe_ratio: 1.5, kelly_suggested_units: 2.0,
        edge_trend: 'stable', recent_edge_value: 14.0,
        biggest_win_units: 0.9, biggest_loss_units: -1.0,
        best_day_pnl: 0.9, worst_day_pnl: -1.0,
        current_streak: 1, longest_win_streak: 2, longest_loss_streak: 1,
        profit_factor: 2.9,
        ...overrides,
    };
}

export function makeSlipsPage(overrides: Partial<SlipsPage> = {}): SlipsPage {
    return {
        slips: [makeSlip()],
        stats: makeSlipStats(),
        profiles: ['low', 'medium', 'high_risk'],
        ...overrides,
    };
}

// ── analytics ─────────────────────────────────────────────────────────────

export function makeAnalyticsData(overrides: Partial<AnalyticsData> = {}): AnalyticsData {
    return {
        history: [makeHistoryRecord()],
        market_accuracy: [makeMarketAccuracy()],
        pnl_by_market: [makePnlByMarket()],
        odds_distribution: [makeOddsDistBucket()],
        correlation: [makeCorrelationRecord()],
        profile_scatter: [makeProfileScatterPoint()],
        stats: makeSlipStats(),
        profiles: ['low', 'medium'],
        market_breakdown: [makeMarketBreakdown()],
        league_breakdown: [makeLeagueBreakdown()],
        rolling_edge: [makeRollingEdgePoint()],
        drawdown: [makeDrawdownPoint()],
        return_distribution: makeReturnDistribution(),
        time_patterns: {
            day_of_week: [makeTimePatternItem()],
            hour: [makeTimePatternItem()],
        },
        ...overrides,
    };
}

export function makeHistoryRecord(overrides: Partial<HistoryRecord> = {}): HistoryRecord {
    return {
        date: '2026-09-24', slips_count: 1, units_bet: 1.0,
        net_profit: 0.9, cumulative_profit: 0.9, cumulative_bet: 1.0,
        roi_percentage: 90.0, win_rate: 100.0, ...overrides,
    };
}

export function makeMarketAccuracy(overrides: Partial<MarketAccuracy> = {}): MarketAccuracy {
    return { market: 'Home', won: 2, lost: 1, total: 3, accuracy: 66.67, ...overrides };
}

export function makePnlByMarket(overrides: Partial<PnlByMarket> = {}): PnlByMarket {
    return { market: 'Home', won: 2, lost: 1, net_profit: 0.9, ...overrides };
}

export function makeOddsDistBucket(overrides: Partial<OddsDistBucket> = {}): OddsDistBucket {
    return {
        range: '1.5-2.0', count: 3, wins: 2, losses: 1,
        win_rate: 66.67, implied_win_rate: 52.63, avg_odds: 1.9, edge: 14.04,
        ...overrides,
    };
}

export function makeCorrelationRecord(overrides: Partial<CorrelationRecord> = {}): CorrelationRecord {
    return { legs_count: 1, total_odds: 1.9, units: 1.0, status: 'Won', profit: 0.9, ...overrides };
}

export function makeProfileScatterPoint(overrides: Partial<ProfileScatterPoint> = {}): ProfileScatterPoint {
    return {
        profile: 'low', avg_odds: 1.9, win_rate: 66.67,
        net_profit: 2.8, volume: 3, break_even_win_rate: 52.63, ...overrides,
    };
}

export function makeMarketBreakdown(overrides: Partial<MarketBreakdown> = {}): MarketBreakdown {
    return {
        market: 'Home', legs: 3, won: 2, lost: 1,
        win_rate: 66.67, implied_win_rate: 52.63, edge: 14.04,
        avg_odds: 1.9, net_profit: 0.9, ...overrides,
    };
}

export function makeLeagueBreakdown(overrides: Partial<LeagueBreakdown> = {}): LeagueBreakdown {
    return {
        league: 'England', legs: 3, won: 2, lost: 1,
        win_rate: 66.67, implied_win_rate: 52.63, edge: 14.04,
        avg_odds: 1.9, net_profit: 0.9, ...overrides,
    };
}

export function makeRollingEdgePoint(overrides: Partial<RollingEdgePoint> = {}): RollingEdgePoint {
    return {
        date: '2026-09-24', rolling_edge: 14.04, rolling_win_rate: 66.67,
        rolling_implied: 52.63, sample_size: 3, ...overrides,
    };
}

export function makeDrawdownPoint(overrides: Partial<DrawdownPoint> = {}): DrawdownPoint {
    return {
        date: '2026-09-24', drawdown: 0.0, peak: 0.9, cumulative_profit: 0.9, ...overrides,
    };
}

export function makeReturnDistribution(overrides: Partial<ReturnDistribution> = {}): ReturnDistribution {
    return {
        bins: [{ range: '0-1', range_end: '1', count: 2, is_positive: true }],
        mean: 0.9, median: 0.9, ...overrides,
    };
}

export function makeTimePatternItem(overrides: Partial<TimePatternItem> = {}): TimePatternItem {
    return { key: 'Monday', total: 3, won: 2, win_rate: 66.67, ...overrides };
}

// ── services ───────────────────────────────────────────────────────────────

export function makeServiceInfo(overrides: Partial<ServiceInfo> = {}): ServiceInfo {
    return {
        name: 'puller', description: 'DB pull service',
        enabled: true, alive: true,
        hour: null, minute: null, interval_seconds: 300,
        next_run: '2026-09-24T12:05:00', last_time_generated: null,
        ...overrides,
    };
}

export function makeServicesData(overrides: Partial<ServicesData> = {}): ServicesData {
    return {
        services: {
            puller: makeServiceInfo({ name: 'puller' }),
            generator: makeServiceInfo({ name: 'generator', interval_seconds: 300 }),
            verifier: makeServiceInfo({ name: 'verifier', interval_seconds: 60 }),
        },
        generate_hour: 9, generate_minute: 0,
        server_time: '2026-09-24T12:00:00',
        ...overrides,
    };
}

// ── profiles ──────────────────────────────────────────────────────────────

export function makeProfile(overrides: Partial<Profile> = {}): Profile {
    return {
        target_odds: 2.0, target_legs: 3,
        max_legs_overflow: null,
        consensus_floor: 50.0, min_odds: 1.05,
        included_markets: null, included_leagues: null, excluded_sources: null,
        tolerance_factor: null, stop_threshold: null,
        min_legs_fill_ratio: 0.7, quality_vs_balance: 0.5, consensus_vs_sources: 0.5,
        units: 1.0, target_payout: null, run_daily_count: 0,
        date_from: null, date_to: null, excluded_urls: null,
        consensus_shrinkage_k: null, min_source_edge: null,
        max_single_leg_odds: null, tol_lower: null, tol_upper: null,
        balance_decay: 'gaussian', min_pick_quality: null,
        odds_movement_weight: null, odds_movement_strength_min: null,
        ...overrides,
    };
}

export function makeProfilesMap(overrides: Partial<ProfilesMap> = {}): ProfilesMap {
    return {
        low: makeProfile({ consensus_floor: 50.0 }),
        medium: makeProfile({ consensus_floor: 60.0 }),
        high_risk: makeProfile({ consensus_floor: 40.0 }),
        ...overrides,
    };
}

// ── builder preview ───────────────────────────────────────────────────────

export function makeCandidateLeg(overrides: Partial<CandidateLeg> = {}): CandidateLeg {
    return {
        match_name: 'Arsenal vs Chelsea',
        datetime: '2026-09-25T15:00:00',
        market: 'Home', market_type: 'Result',
        consensus: 75.0, odds: 1.9,
        result_url: 'https://example.com/match/1',
        league: 'England', sources: 4, tier: 1, score: 0.83,
        quality: 0.8, odds_movement_direction: null, odds_movement_strength: 0.0,
        predictions: [makeSourcePrediction()],
        ...overrides,
    };
}

export function makePreviewResult(overrides: Partial<PreviewResult> = {}): PreviewResult {
    return {
        legs: [makeCandidateLeg()],
        total_odds: 1.9,
        pending_urls: [],
        ...overrides,
    };
}

// ── odds history ──────────────────────────────────────────────────────────

export function makeOddsSnapshot(overrides: Partial<OddsSnapshot> = {}): OddsSnapshot {
    return {
        timestamp: '2026-09-24T12:00:00',
        odds: { home: 1.9, draw: 3.4, away: 4.2 },
        ...overrides,
    };
}

export function makeOddsHistory(matchId = 1, overrides: Partial<OddsHistory> = {}): OddsHistory {
    return {
        match_id: matchId,
        match_name: 'Arsenal vs Chelsea',
        datetime: '2026-09-25T15:00:00',
        snapshots: [makeOddsSnapshot()],
        movement: { home: 'up', draw: 'stable', away: 'down' },
        ...overrides,
    };
}

export function makeOddsMovementSummary(overrides: OddsMovementSummary = {}): OddsMovementSummary {
    return { home: 'up', draw: 'stable', away: 'down', ...overrides };
}
