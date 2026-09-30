// data.ts tests (issue #67). Covers ALL 22 exported functions (the issue
// lists only 13 — divergence: spec missed the 7 excluded-URL functions,
// deleteProfile/deleteSlip/saveServiceSettings, and matches/oddsHistory
// modules entirely). Response shapes ground-truthed against src/types +
// cycle-2 backend router contracts.

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../../test/handlers';
import {
    makePreviewResult, makeProfilesMap, makeProfile,
    makeSlipsPage, makeAnalyticsData, makeServicesData,
} from '../../test/factories';
import type { ManualLegIn } from '../../types';
import {
    fetchPreview, fetchLeagues, fetchExcluded, fetchExcludedDetails,
    addExcluded, removeExcluded, clearExcluded,
    fetchProfiles, saveProfile, deleteProfile,
    fetchSlips, addSlip, deleteSlip, validateSlips, generateSlips,
    fetchAnalytics, fetchServices, saveServiceSettings, toggleService,
    pullDb, fetchStatus, fetchSourcesConfig,
} from '../data';


function manualLeg(overrides: Partial<ManualLegIn> = {}): ManualLegIn {
    return {
        match_name: 'Arsenal vs Chelsea',
        market: 'Home',
        market_type: 'Result',
        odds: 1.9,
        result_url: 'https://example.com/match/1',
        datetime: '2026-09-25T15:00:00',
        consensus: 75,
        sources: 4,
        ...overrides,
    };
}


describe('builder endpoints', () => {
    it('fetchPreview POSTs config verbatim and unwraps PreviewResult', async () => {
        let body: Record<string, unknown> | null = null;
        server.use(http.post('/api/builder/preview', async ({ request }) => {
            body = await request.json() as Record<string, unknown>;
            return HttpResponse.json(makePreviewResult({ total_odds: 6.84 }));
        }));
        const cfg = {
            target_odds: 6.0, target_legs: 3, max_legs_overflow: null,
            consensus_floor: 50.0, min_odds: 1.05,
            included_markets: null, included_leagues: null,
            tolerance_factor: null, stop_threshold: null,
            min_legs_fill_ratio: 0.7, quality_vs_balance: 0.5, consensus_vs_sources: 0.5,
            date_from: null, date_to: null, excluded_sources: null,
            consensus_shrinkage_k: null, min_source_edge: null,
            max_single_leg_odds: null, tol_lower: null, tol_upper: null,
            balance_decay: 'gaussian', min_pick_quality: null,
            odds_movement_weight: null, odds_movement_strength_min: null,
        } as Parameters<typeof fetchPreview>[0];
        const result = await fetchPreview(cfg);
        expect(body).not.toBeNull();
        expect((body as unknown as Record<string, unknown>).target_odds).toBe(6.0);
        expect(result.total_odds).toBe(6.84);
        expect(result.legs[0].match_name).toBe('Arsenal vs Chelsea');
    });

    it('fetchLeagues returns string array', async () => {
        server.use(http.get('/api/builder/leagues', () => HttpResponse.json(['England', 'Spain'])));
        const leagues = await fetchLeagues();
        expect(leagues).toEqual(['England', 'Spain']);
    });

    it('fetchExcluded unwraps {excluded} wrapper', async () => {
        server.use(http.get('/api/builder/excluded', () => HttpResponse.json({ excluded: ['https://x/1'] })));
        const urls = await fetchExcluded();
        expect(urls).toEqual(['https://x/1']);
    });

    it('fetchExcludedDetails unwraps excluded match details', async () => {
        server.use(http.get('/api/builder/excluded/details', () => HttpResponse.json({
            excluded: [{ url: 'https://x/1', match_name: 'A vs B', datetime: '2026-09-25T15:00:00', reason: 'manual' }],
        })));
        const details = await fetchExcludedDetails();
        expect(details[0].match_name).toBe('A vs B');
        expect(details[0].reason).toBe('manual');
    });

    it('addExcluded POSTs {url} and unwraps result', async () => {
        let body: Record<string, unknown> | null = null;
        server.use(http.post('/api/builder/excluded', async ({ request }) => {
            body = await request.json() as Record<string, unknown>;
            return HttpResponse.json({ excluded: ['https://x/1', 'https://x/2'] });
        }));
        const urls = await addExcluded('https://x/2');
        expect(body).toEqual({ url: 'https://x/2' });
        expect(urls).toHaveLength(2);
    });

    it('removeExcluded POSTs {url} to /remove', async () => {
        let body: Record<string, unknown> | null = null;
        server.use(http.post('/api/builder/excluded/remove', async ({ request }) => {
            body = await request.json() as Record<string, unknown>;
            return HttpResponse.json({ excluded: [] });
        }));
        const urls = await removeExcluded('https://x/1');
        expect(body).toEqual({ url: 'https://x/1' });
        expect(urls).toEqual([]);
    });

    it('clearExcluded issues DELETE without body', async () => {
        let method = '';
        server.use(http.delete('/api/builder/excluded', ({ request }) => {
            method = request.method;
            return HttpResponse.json({ ok: true });
        }));
        await clearExcluded();
        expect(method).toBe('DELETE');
    });
});


describe('profiles endpoints', () => {
    it('fetchProfiles unwraps {profiles} wrapper into map', async () => {
        server.use(http.get('/api/profiles', () => HttpResponse.json({ profiles: makeProfilesMap() })));
        const map = await fetchProfiles();
        expect(map.low.consensus_floor).toBe(50.0);
        expect(map.high_risk.consensus_floor).toBe(40.0);
        expect(Object.keys(map)).toHaveLength(3);
    });

    it('saveProfile POSTs full profile with name', async () => {
        let body: Record<string, unknown> | null = null;
        server.use(http.post('/api/profiles', async ({ request }) => {
            body = await request.json() as Record<string, unknown>;
            return HttpResponse.json({ ok: true });
        }));
        const p = { ...makeProfile({ consensus_floor: 65.0 }), name: 'aggressive' };
        await saveProfile(p);
        expect(body).not.toBeNull();
        expect((body as unknown as Record<string, unknown>).name).toBe('aggressive');
        expect((body as unknown as Record<string, unknown>).consensus_floor).toBe(65.0);
    });

    it('deleteProfile templated DELETE', async () => {
        let captured = '';
        server.use(http.delete('/api/profiles/:name', ({ params }) => {
            captured = String(params.name);
            return HttpResponse.json({ ok: true });
        }));
        await deleteProfile('aggressive');
        expect(captured).toBe('aggressive');
    });

    it('fetchProfiles 404 rejects with axios error', async () => {
        server.use(http.get('/api/profiles', () => HttpResponse.json({}, { status: 404 })));
        await expect(fetchProfiles()).rejects.toMatchObject({ response: { status: 404 } });
    });
});

describe('slips endpoints', () => {
    it('fetchSlips sends all filter params and unwraps SlipsPage', async () => {
        let query = '';
        server.use(http.get('/api/slips', ({ request }) => {
            query = new URL(request.url).search;
            return HttpResponse.json(makeSlipsPage());
        }));
        const page = await fetchSlips({ profiles: ['low'], date_from: '2026-09-01', date_to: '2026-09-30', hide_settled: true, live_only: false });
        expect(query).toContain('profiles%5B%5D=low');
        expect(query).toContain('date_from=2026-09-01');
        expect(query).toContain('hide_settled=true');
        expect(query).toContain('live_only=false'); // axios serializes false booleans (only nulls/empty arrays omitted)
        expect(page.slips[0].slip_id).toBe(1);
        expect(page.stats.win_rate).toBe(66.67);
    });

    it('addSlip POSTs profile/legs/units and returns slip_id', async () => {
        let body: Record<string, unknown> | null = null;
        server.use(http.post('/api/slips', async ({ request }) => {
            body = await request.json() as Record<string, unknown>;
            return HttpResponse.json({ slip_id: 42 });
        }));
        const id = await addSlip('low', [manualLeg()], 2.5);
        expect(id).toBe(42);
        expect((body as unknown as Record<string, unknown>).profile).toBe('low');
        expect((body as unknown as Record<string, unknown>).units).toBe(2.5);
        expect(((body as unknown as Record<string, unknown>).legs as ManualLegIn[])[0].market).toBe('Home');
    });

    it('deleteSlip templated DELETE', async () => {
        let captured = '';
        server.use(http.delete('/api/slips/:id', ({ params }) => {
            captured = String(params.id);
            return HttpResponse.json({ ok: true });
        }));
        await deleteSlip(7);
        expect(captured).toBe('7');
    });

    it('validateSlips returns counts and live_data', async () => {
        server.use(http.post('/api/slips/validate', () => HttpResponse.json({
            checked: 5, settled: 3, live: 1, errors: 1,
            live_data: [{ match_name: 'X vs Y', score: '2:0', minute: "71'" }],
        })));
        const result = await validateSlips();
        expect(result.checked).toBe(5);
        expect(result.live_data[0].minute).toBe("71'");
    });

    it('generateSlips returns generated + by_profile', async () => {
        server.use(http.post('/api/slips/generate', () => HttpResponse.json({ generated: 3, by_profile: { low: 2, medium: 1 } })));
        const result = await generateSlips();
        expect(result.generated).toBe(3);
        expect(result.by_profile.low).toBe(2);
    });

    it('fetchSlips 500 rejects raw (divergence pin: no toast interceptor)', async () => {
        server.use(http.get('/api/slips', () => HttpResponse.json({}, { status: 500 })));
        await expect(fetchSlips({})).rejects.toMatchObject({ response: { status: 500 } });
    });
});


describe('analytics endpoint', () => {
    it('fetchAnalytics sends date/profile filters and returns full AnalyticsData', async () => {
        let query = '';
        server.use(http.get('/api/analytics', ({ request }) => {
            query = new URL(request.url).search;
            return HttpResponse.json(makeAnalyticsData());
        }));
        const data = await fetchAnalytics({ profiles: ['low'], date_from: '2026-09-01' });
        expect(query).toContain('profiles%5B%5D=low');
        expect(query).toContain('date_from=2026-09-01');
        expect(data.history[0].cumulative_profit).toBe(0.9);
        expect(data.market_accuracy[0].market).toBe('Home');
        expect(data.stats.edge).toBe(14.04);
        expect(data.time_patterns?.day_of_week[0].key).toBe('Monday');
    });

    it('fetchAnalytics network error rejects with axios error', async () => {
        server.use(http.get('/api/analytics', () => Response.error()));
        await expect(fetchAnalytics({})).rejects.toMatchObject({ isAxiosError: true });
    });
});


describe('services endpoints', () => {
    it('fetchServices returns services map + generate time', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(makeServicesData({ generate_hour: 8 }))));
        const data = await fetchServices();
        expect(data.generate_hour).toBe(8);
        expect(data.services.verifier.interval_seconds).toBe(60);
        expect(data.services.puller.enabled).toBe(true);
    });

    it('saveServiceSettings POSTs hour/minute', async () => {
        let body: Record<string, unknown> | null = null;
        server.use(http.post('/api/services/settings', async ({ request }) => {
            body = await request.json() as Record<string, unknown>;
            return HttpResponse.json({ ok: true });
        }));
        await saveServiceSettings(10, 30);
        expect(body).toEqual({ generate_hour: 10, generate_minute: 30 });
    });

    it('toggleService templated POST returns name/enabled', async () => {
        let captured = '';
        server.use(http.post('/api/services/:name/toggle', ({ params }) => {
            captured = String(params.name);
            return HttpResponse.json({ name: String(params.name), enabled: false });
        }));
        const result = await toggleService('generator');
        expect(captured).toBe('generator');
        expect(result.enabled).toBe(false);
    });
});


describe('system endpoints', () => {
    it('pullDb POSTs empty body and returns status/timestamp', async () => {
        server.use(http.post('/api/pull', () => HttpResponse.json({ status: 'ok', timestamp: '2026-09-24T15:00:00' })));
        const result = await pullDb();
        expect(result.status).toBe('ok');
        expect(result.timestamp).toBe('2026-09-24T15:00:00');
    });

    it('fetchStatus returns last_pull + matches_loaded', async () => {
        server.use(http.get('/api/status', () => HttpResponse.json({ last_pull: '2026-09-24T15:30:00', matches_loaded: 250 })));
        const status = await fetchStatus();
        expect(status.matches_loaded).toBe(250);
    });

    it('fetchSourcesConfig returns sources list', async () => {
        server.use(http.get('/api/config/sources', () => HttpResponse.json({ sources: ['forebet', 'predictz'] })));
        const cfg = await fetchSourcesConfig();
        expect(cfg.sources).toContain('forebet');
    });

    it('pullDb 502 rejects with axios error', async () => {
        server.use(http.post('/api/pull', () => HttpResponse.json({}, { status: 502 })));
        await expect(pullDb()).rejects.toMatchObject({ response: { status: 502 } });
    });
});
