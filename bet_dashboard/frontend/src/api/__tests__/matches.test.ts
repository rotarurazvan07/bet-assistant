// matches.ts tests (issue #67). Pins param serialization: excluded_sources
// comma-joined (probed: axios emits arrays as repeated key[] params, so the
// client-side join() is load-bearing), nulls omitted, booleans verbatim.

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../test/handlers';
import { makeMatchesPage } from '../../test/factories';
import { fetchMatches } from '../matches';


describe('fetchMatches', () => {
    it('sends page params and unwraps MatchesPage', async () => {
        let captured: string | null = null;
        server.use(http.get('/api/matches', ({ request }) => {
            captured = request.url;
            return HttpResponse.json(makeMatchesPage({ total: 7, total_pages: 1 }));
        }));
        const page = await fetchMatches({ page: 2, page_size: 50 });
        expect(page.total).toBe(7);
        expect(captured).not.toBeNull();
        const url = new URL(captured as unknown as string);
        expect(url.searchParams.get('page')).toBe('2');
        expect(url.searchParams.get('page_size')).toBe('50');
    });

    it('joins excluded_sources with commas', async () => {
        let query = '';
        server.use(http.get('/api/matches', ({ request }) => {
            query = new URL(request.url).search;
            return HttpResponse.json(makeMatchesPage());
        }));
        await fetchMatches({ page: 1, page_size: 20, excluded_sources: ['alpha', 'beta'] });
        expect(query).toContain('excluded_sources=alpha,beta'); // jsdom URLSearchParams emits raw commas (probe-verified)
    });

    it('omits empty excluded_sources array entirely', async () => {
        let query = '';
        server.use(http.get('/api/matches', ({ request }) => {
            query = new URL(request.url).search;
            return HttpResponse.json(makeMatchesPage());
        }));
        await fetchMatches({ page: 1, page_size: 20, excluded_sources: [] });
        expect(query).not.toContain('excluded_sources');
    });

    it('omits null filters from query string', async () => {
        let query = '';
        server.use(http.get('/api/matches', ({ request }) => {
            query = new URL(request.url).search;
            return HttpResponse.json(makeMatchesPage());
        }));
        await fetchMatches({ page: 1, page_size: 20, min_consensus: null, min_odds: null });
        expect(query).not.toContain('min_consensus');
        expect(query).not.toContain('min_odds');
    });

    it('serializes booleans verbatim', async () => {
        let query = '';
        server.use(http.get('/api/matches', ({ request }) => {
            query = new URL(request.url).search;
            return HttpResponse.json(makeMatchesPage());
        }));
        await fetchMatches({ page: 1, page_size: 20, only_significant_movement: true });
        expect(query).toContain('only_significant_movement=true');
    });

    it('4xx rejects with axios error', async () => {
        server.use(http.get('/api/matches', () => HttpResponse.json({}, { status: 422 })));
        await expect(fetchMatches({ page: 1, page_size: 20 })).rejects.toMatchObject({
            response: { status: 422 },
        });
    });
});
