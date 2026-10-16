// Canonical demo rows for BOTH tracks: installDemoApi (local) and
// setup/seed_e2e.py (CI e2e DB). Expand here first, then teach both tracks.
// Reuses Vitest factories — no second Match type.
import type { MarketMovementDetail, OddsMovementSummary } from '../../src/types';
import { makeMatch, makeMatchesPage, makeProfile, makeSlip, makeSlipsPage } from '../../src/test/factories';

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

// Odds movement (pp-sourced contract, issue #105): demo data mirrors the
// real read path so /api/odds-history/movements/* have rows to serve.
// Same pp values are seeded by setup/seed_e2e.py — keep both in sync.
export const DEMO_MOVEMENTS: Record<string, OddsMovementSummary> = {
    match_1_ab12cd34: { home: 'down', draw: 'stable', away: 'up' },
    match_2_ef56gh78: { home: 'up', draw: 'stable', away: 'down' },
    match_3_ij90kl12: { home: null, draw: 'stable', away: null },
};

// Strength details for /movements/significant (Odds Alert page). Markets with
// significant: true are surfaced; the rest stay in the payload like the API.
export const DEMO_MOVEMENT_STRENGTHS: Record<string, Record<string, MarketMovementDetail>> = {
    match_1_ab12cd34: {
        home: { direction: 'down', change_pct: -6.4, significant: true },
        draw: { direction: 'stable', change_pct: 0.0, significant: false },
        away: { direction: 'up', change_pct: 3.2, significant: false },
    },
    match_2_ef56gh78: {
        home: { direction: 'up', change_pct: 8.3, significant: true },
        draw: { direction: 'stable', change_pct: 0.0, significant: false },
        away: { direction: 'down', change_pct: -2.1, significant: false },
    },
};

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

export const DEMO_PROFILES = { low: makeProfile() };
