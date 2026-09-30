// oddsHistory.ts tests (issue #67). Pins path templating and response
// unwrapping for the 4 odds-history functions.

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../test/handlers';
import { makeOddsHistory, makeOddsMovementSummary } from '../../test/factories';
import {
    getMatchOddsHistory, getMatchMovement, getAllMovements, getSignificantMovements,
} from '../oddsHistory';


describe('oddsHistory', () => {
    it('getMatchOddsHistory templates matchId into path', async () => {
        let captured = '';
        server.use(http.get('/api/odds-history/:matchId', ({ params }) => {
            captured = String(params.matchId);
            return HttpResponse.json(makeOddsHistory(9, { match_name: 'X vs Y' }));
        }));
        const hist = await getMatchOddsHistory(9);
        expect(captured).toBe('9');
        expect(hist.match_id).toBe(9);
        expect(hist.match_name).toBe('X vs Y');
        expect(hist.snapshots[0].odds.home).toBe(1.9);
    });

    it('getMatchMovement hits /movement suffix', async () => {
        let captured = '';
        server.use(http.get('/api/odds-history/:matchId/movement', ({ params }) => {
            captured = String(params.matchId);
            return HttpResponse.json(makeOddsMovementSummary({ home: 'down' }));
        }));
        const mv = await getMatchMovement(3);
        expect(captured).toBe('3');
        expect(mv.home).toBe('down');
    });

    it('getAllMovements returns keyed map', async () => {
        server.use(http.get('/api/odds-history/movements/all', () => HttpResponse.json({ '12': makeOddsMovementSummary() })));
        const all = await getAllMovements();
        expect(all['12'].home).toBe('up');
    });

    it('getSignificantMovements returns detail map', async () => {
        server.use(http.get('/api/odds-history/movements/significant', () => HttpResponse.json({
            '5': { home: { direction: 'up', change_pct: 9.5, significant: true } },
        })));
        const sig = await getSignificantMovements();
        expect(sig['5'].home.significant).toBe(true);
        expect(sig['5'].home.change_pct).toBe(9.5);
    });

    it('5xx rejects raw', async () => {
        server.use(http.get('/api/odds-history/:matchId', () => HttpResponse.json({}, { status: 503 })));
        await expect(getMatchOddsHistory(1)).rejects.toMatchObject({ response: { status: 503 } });
    });

    it('network error rejects with axios error', async () => {
        server.use(http.get('/api/odds-history/:matchId', () => Response.error()));
        await expect(getMatchOddsHistory(1)).rejects.toMatchObject({ isAxiosError: true });
    });
});
