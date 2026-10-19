// Canonical demo rows for BOTH tracks: installDemoApi (local) and
// setup/seed_e2e.py (CI e2e DB). Expand here first, then teach both tracks.
// Reuses Vitest factories — no second Match type.
import { makeCandidateLeg, makeMatch, makeMatchesPage, makePreviewResult, makeProfile, makeSlip, makeSlipsPage, makeSourcePrediction } from '../../src/test/factories';
import type { ProfileSchedule } from '../../src/types';

export const DEMO_MATCHES = [
    makeMatch({
        home: 'Arsenal',
        away: 'Chelsea',
        cons_home: 75,
        odds_home: 1.9,
        result_url: 'https://example.com/match/1',
    }),
    makeMatch({
        match_id: 'match_2_ef56gh78',
        datetime: '2026-10-07T18:00:00',
        home: 'Liverpool',
        away: 'Man City',
        sources: 5,
        cons_home: 42,
        cons_draw: 28,
        cons_away: 30,
        odds_home: 2.4,
        odds_draw: 3.2,
        odds_away: 2.9,
        result_url: 'https://example.com/match/2',
        league: 'England',
    }),
    makeMatch({
        match_id: 'match_3_ij90kl12',
        datetime: '2026-10-08T20:45:00',
        home: 'Barcelona',
        away: 'Real Madrid',
        sources: 6,
        cons_home: 38,
        cons_draw: 26,
        cons_away: 36,
        odds_home: 2.7,
        odds_draw: 3.3,
        odds_away: 2.5,
        result_url: 'https://example.com/match/3',
        league: 'Spain',
    }),
];

export const DEMO_MATCHES_PAGE = makeMatchesPage({
    total: DEMO_MATCHES.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
    matches: DEMO_MATCHES,
});

export const DEMO_SLIPS = [
    makeSlip({
        slip_id: 1,
        profile: 'low',
        date_generated: '2026-10-07',
    }),
];

export const DEMO_SLIPS_PAGE = makeSlipsPage({
    slips: DEMO_SLIPS,
    profiles: ['low'],
});

export const DEMO_PROFILES = {
    low: makeProfile(),
    medium: makeProfile({ consensus_floor: 60.0 }),
    high_risk: makeProfile({ consensus_floor: 40.0 }),
};

export const DEMO_PROFILE_SCHEDULES: ProfileSchedule[] = [
    { name: 'low', auto_generate: true, generate_hour: 8, generate_minute: 30, units: 1.0, target_payout: null, run_daily_count: 1, order: 0 },
    { name: 'medium', auto_generate: true, generate_hour: 10, generate_minute: 0, units: null, target_payout: 50.0, run_daily_count: 2, order: 1 },
    { name: 'high_risk', auto_generate: false, generate_hour: 12, generate_minute: 15, units: null, target_payout: null, run_daily_count: 0, order: 2 },
];

// Smart Builder live-preview legs for the demo API. Matches share identity with
// DEMO_MATCHES (same match_ids/dates/result_urls) so exclude/clear flows in the
// e2e specs behave against a consistent dataset.
export const DEMO_PREVIEW_LEGS = [
    makeCandidateLeg({
        match_name: 'Arsenal vs Chelsea',
        datetime: '2026-10-07T15:00:00',
        market: 'Home',
        market_type: 'Result',
        consensus: 75.0,
        odds: 1.9,
        result_url: 'https://example.com/match/1',
        league: 'England',
        sources: 4,
        predictions: [
            makeSourcePrediction({ source: 'forebet', home: 78, draw: 12, away: 10 }),
            makeSourcePrediction({ source: 'xgscore', home: 61, draw: 21, away: 18 }),
            makeSourcePrediction({ source: 'windrawwin', home: 74, draw: 14, away: 12 }),
            makeSourcePrediction({ source: 'predictz', home: 69, draw: 18, away: 13 }),
        ],
    }),
    makeCandidateLeg({
        match_name: 'Liverpool vs Man City',
        datetime: '2026-10-07T18:00:00',
        market: 'Over 2.5',
        market_type: 'Goals',
        consensus: 58.0,
        odds: 1.85,
        result_url: 'https://example.com/match/2',
        league: 'England',
        sources: 5,
        score: 0.61,
        quality: 0.72,
        odds_movement_direction: 'dropping',
        odds_movement_strength: 0.09,
        predictions: [
            makeSourcePrediction({ source: 'forebet', home: 44, draw: 27, away: 29 }),
            makeSourcePrediction({ source: 'soccervista', home: 40, draw: 25, away: 35 }),
            makeSourcePrediction({ source: 'betclan', home: 46, draw: 24, away: 30 }),
        ],
    }),
    makeCandidateLeg({
        match_name: 'Barcelona vs Real Madrid',
        datetime: '2026-10-08T20:45:00',
        market: 'BTTS Yes',
        market_type: 'BTTS',
        consensus: 66.0,
        odds: 1.72,
        result_url: 'https://example.com/match/3',
        league: 'Spain',
        sources: 6,
        tier: 2,
        score: 0.55,
        quality: 0.65,
        predictions: [
            makeSourcePrediction({ source: 'xgscore', home: 40, draw: 26, away: 34 }),
            makeSourcePrediction({ source: 'predictz', home: 36, draw: 28, away: 36 }),
            makeSourcePrediction({ source: 'footballpredictions', home: 43, draw: 24, away: 33 }),
        ],
    }),
];

export const DEMO_PREVIEW = makePreviewResult({
    legs: DEMO_PREVIEW_LEGS,
    total_odds: 1.9 * 1.85 * 1.72,
    pending_urls: [],
});
