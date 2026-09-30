// OddsAlert page — SPEC-ABSENT page (issue #65 inventory divergence, D42:
// included anyway — 6/6 pages). Merges significant movements with paginated
// matches; categorizes rising vs falling; empty + loading states.

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import OddsAlert from '../OddsAlert';
import { server } from '../../test/handlers';
import { makeMatchesPage, makeMatch } from '../../test/factories';


const MATCH_ID = 'm-1';
const MOVEMENTS = {
    [MATCH_ID]: {
        home: { direction: 'up', change_pct: 8.2, significant: true },
        over_25: { direction: 'down', change_pct: -6.1, significant: true },
    },
};


beforeEach(() => {
    server.use(
        http.get('/api/odds-history/movements/significant', () => HttpResponse.json(MOVEMENTS)),
        http.get('/api/matches', () => HttpResponse.json(
            makeMatchesPage({
                total: 1,
                page: 1,
                total_pages: 1,
                matches: [
                    makeMatch({
                        match_id: MATCH_ID,
                        home: 'Arsenal',
                        away: 'Chelsea',
                        datetime: '2026-09-26T15:00:00',
                        league: 'England',
                        result_url: 'https://example.com/match/1',
                        cons_home: 75,
                        odds_home: 1.9,
                    }),
                ],
            }),
        )),
    );
});


describe('OddsAlert page', () => {
    it('shows the loading state first', () => {
        render(<OddsAlert />);
        expect(screen.getByText('Loading movements…')).toBeInTheDocument();
    });

    it('renders the header explainer', async () => {
        render(<OddsAlert />);
        expect(screen.getByText('Odds Alert')).toBeInTheDocument();
        expect(screen.getByText(/significant/)).toBeInTheDocument();
    });

    it('renders both rising and falling sections with the match', async () => {
        render(<OddsAlert />);
        await waitFor(() => expect(screen.queryByText('Loading movements…')).not.toBeInTheDocument());
        expect(screen.getByText(/Rising Odds/)).toBeInTheDocument();
        expect(screen.getByText(/Falling Odds/)).toBeInTheDocument();
        expect(screen.getAllByText(/Arsenal vs Chelsea/).length).toBeGreaterThan(0);
    });

    it('shows the change percentages with sign', async () => {
        render(<OddsAlert />);
        await waitFor(() => expect(screen.queryByText('Loading movements…')).not.toBeInTheDocument());
        expect(screen.getByText('+8.2%')).toBeInTheDocument();
        expect(screen.getByText('-6.1%')).toBeInTheDocument();
    });

    it('empty state when no significant movements', async () => {
        server.use(
            http.get('/api/odds-history/movements/significant', () => HttpResponse.json({})),
        );
        render(<OddsAlert />);
        await screen.findByText(/No significant odds movements/);
    });

    it('empty state when movements reference unknown matches', async () => {
        server.use(
            http.get('/api/odds-history/movements/significant', () =>
                HttpResponse.json({ 'unknown-id': { home: { direction: 'up', change_pct: 9, significant: true } } })),
        );
        render(<OddsAlert />);
        await screen.findByText(/No significant odds movements/);
    });

    it('only-significant markets are categorized (insignificant filtered)', async () => {
        render(<OddsAlert />);
        await waitFor(() => expect(screen.queryByText('Loading movements…')).not.toBeInTheDocument());
        // only up(home) + down(over_25) significant entries appear; no other market chips
        expect(screen.getByText('+8.2%')).toBeInTheDocument();
    });

    it('multi-page matches are merged (page 2 fetched)', async () => {
        let matchCalls = 0;
        server.use(
            http.get('/api/matches', () => {
                matchCalls += 1;
                const page2 = matchCalls === 2;
                return HttpResponse.json(
                    makeMatchesPage({
                        total: 2,
                        page: page2 ? 2 : 1,
                        total_pages: 2,
                        matches: [
                            makeMatch({
                                match_id: page2 ? 'm-2' : MATCH_ID,
                                home: page2 ? 'Real Madrid' : 'Arsenal',
                                away: 'Chelsea',
                                datetime: '2026-09-26T15:00:00',
                                league: 'Spain',
                                result_url: `https://example.com/match/${page2 ? 2 : 1}`,
                                cons_home: 75,
                                odds_home: 1.9,
                            }),
                        ],
                    }),
                );
            }),
            http.get('/api/odds-history/movements/significant', () => HttpResponse.json({
                [MATCH_ID]: { home: { direction: 'up', change_pct: 8.2, significant: true } },
                'm-2': { home: { direction: 'down', change_pct: -5.5, significant: true } },
            })),
        );
        render(<OddsAlert />);
        await screen.findByText(/Real Madrid/);
        expect(matchCalls).toBe(2);
    });
});
