// oddsHistory.ts tests (issue #67, pruned for #105: snapshot endpoint removed).
// Pins path templating and response unwrapping for the 3 movement functions.

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../test/handlers';
import { makeOddsMovementSummary } from '../../test/factories';
import {
    getMatchMovement, getAllMovements, getSignificantMovements,
} from '../oddsHistory';


describe('oddsHistory', () => {
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
        server.use(http.get('/api/odds-history/movements/all', () => HttpResponse.json({}, { status: 503 })));
        await expect(getAllMovements()).rejects.toMatchObject({ response: { status: 503 } });
    });

    it('network error rejects with axios error', async () => {
        server.use(http.get('/api/odds-history/movements/all', () => Response.error()));
        await expect(getAllMovements()).rejects.toMatchObject({ isAxiosError: true });
    });
});
