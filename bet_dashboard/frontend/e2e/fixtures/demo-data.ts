// Canonical demo rows for BOTH tracks: installDemoApi (local) and
// setup/seed_e2e.py (CI e2e DB). Expand here first, then teach both tracks.
// Reuses Vitest factories — no second Match type.
import { makeMatch, makeMatchesPage, makeProfile, makeProfilesMap, makeSlip, makeSlipsPage, makeServicesData, makeProfileSchedule } from '../../src/test/factories';

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

export const DEMO_PROFILES = makeProfilesMap({
    low: makeProfile({ units: 2.0 }),
});

// Per-profile auto-generation rows served by GET /api/services (Workstream B Part D).
// Mirrors the YAML rows seeded into the CI e2e stack by setup/seed_e2e.py.
export const DEMO_SERVICES = makeServicesData({
    generate_hour: 9,
    generate_minute: 0,
    profiles_schedule: {
        low: makeProfileSchedule({ enabled: true, hour: 9, minute: 30, units: 2.5, target_payout: 100, next_run: 'Today 09:30 (in 2h 30m)' }),
        medium: makeProfileSchedule({ enabled: false, hour: 12, minute: 0, units: 1, target_payout: null, next_run: 'Disabled' }),
        high_risk: makeProfileSchedule({ enabled: false, hour: 21, minute: 0, units: 0.5, target_payout: null, next_run: 'Disabled' }),
    },
});
