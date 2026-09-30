// MSW handlers covering the full backend REST surface (issue #63, cycle 9).
// Response shapes ground-truthed against src/types/index.ts and the backend
// router contracts (bet_dashboard/backend/routers/*, verified cycles 2-3).
// Paths are absolute (/api/...) because the axios client baseURL is '/api'.

import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import {
    makeMatchesPage, makeSlipsPage,
    makeAnalyticsData, makeServicesData, makeProfilesMap, makePreviewResult,
    makeOddsHistory, makeOddsMovementSummary,
} from './factories';

// Kept mutable so individual tests can override single handlers via
// server.use(http.get('/api/...', ...)) — resetHandlers() in setup.ts clears.
export const handlers = [
    // ── matches ────────────────────────────────────────────────────────
    http.get('/api/matches', () => HttpResponse.json(makeMatchesPage())),

    // ── builder ─────────────────────────────────────────────────────────
    http.post('/api/builder/preview', () => HttpResponse.json(makePreviewResult())),
    http.get('/api/builder/leagues', () => HttpResponse.json(['England', 'Spain', 'Italy'])),
    http.get('/api/builder/excluded', () => HttpResponse.json({ excluded: ['https://example.com/x'] })),
    http.get('/api/builder/excluded/details', () => HttpResponse.json({
        excluded: [{ url: 'https://example.com/x', match_name: 'A vs B', datetime: '2026-09-25T15:00:00', reason: 'manual' }],
    })),
    http.post('/api/builder/excluded', () => HttpResponse.json({ excluded: ['https://example.com/x'] })),
    http.post('/api/builder/excluded/remove', () => HttpResponse.json({ excluded: [] })),
    http.delete('/api/builder/excluded', () => HttpResponse.json({ ok: true })),

    // ── profiles ────────────────────────────────────────────────────────
    http.get('/api/profiles', () => HttpResponse.json({ profiles: makeProfilesMap() })),
    http.post('/api/profiles', () => HttpResponse.json({ ok: true })),
    http.delete('/api/profiles/:name', () => HttpResponse.json({ ok: true })),

    // ── slips ───────────────────────────────────────────────────────────
    http.get('/api/slips', () => HttpResponse.json(makeSlipsPage())),
    http.post('/api/slips', () => HttpResponse.json({ slip_id: 42 })),
    http.delete('/api/slips/:id', () => HttpResponse.json({ ok: true })),
    http.post('/api/slips/validate', () => HttpResponse.json({
        checked: 3, settled: 2, live: 1, errors: 0,
        live_data: [{ match_name: 'A vs B', score: '1:0', minute: "63'" }],
    })),
    http.post('/api/slips/generate', () => HttpResponse.json({ generated: 2, by_profile: { low: 1, medium: 1 } })),

    // ── analytics ───────────────────────────────────────────────────────
    http.get('/api/analytics', () => HttpResponse.json(makeAnalyticsData())),

    // ── services ────────────────────────────────────────────────────────
    http.get('/api/services', () => HttpResponse.json(makeServicesData())),
    http.post('/api/services/settings', () => HttpResponse.json({ ok: true })),
    http.post('/api/services/:name/toggle', ({ params }) => HttpResponse.json({
        name: String(params.name), enabled: true,
    })),

    // ── system (pull/status) ────────────────────────────────────────────
    http.post('/api/pull', () => HttpResponse.json({ status: 'ok', timestamp: '2026-09-24T12:00:00' })),
    http.get('/api/status', () => HttpResponse.json({ last_pull: '2026-09-24T12:00:00', matches_loaded: 120 })),
    http.get('/api/config/sources', () => HttpResponse.json({
        sources: ['scorepredictor', 'predictz', 'forebet', 'vitibet'],
    })),

    // ── odds-history ───────────────────────────────────────────────────
    http.get('/api/odds-history/:matchId', () => HttpResponse.json(makeOddsHistory(1))),
    http.get('/api/odds-history/:matchId/movement', () => HttpResponse.json(makeOddsMovementSummary())),
    http.get('/api/odds-history/movements/all', () => HttpResponse.json({
        '1': makeOddsMovementSummary(),
    })),
    http.get('/api/odds-history/movements/significant', () => HttpResponse.json({
        '1': { home: { direction: 'up', change_pct: 12.5, significant: true } },
    })),
];

export const server = setupServer(...handlers);
