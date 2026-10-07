// Durable Playwright demo matches (committed, reuse + expand — not one-off).
// Reuses Vitest factories — no second Match type.
import { makeMatch, makeMatchesPage } from '../../src/test/factories';

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
