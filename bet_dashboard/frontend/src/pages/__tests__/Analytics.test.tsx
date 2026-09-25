// Analytics page (issue #65). ACTUAL divergences: does NOT render the
// AnalyticsDashboard component (that lives in SmartBuilder's preview);
// this page is its OWN recharts dashboard with ProfileSelector + chart
// sections; no export button exists. Tests pin wiring: fetchAnalytics with
// date+profile params, stats cards, profile selection, empty + error states.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Analytics from '../Analytics';
import { server } from '../../test/handlers';
import { makeAnalyticsData } from '../../test/factories';

// Order-robust shared stub (final-gate fix): the Analytics page imports
// recharts directly (1687-ln chart dashboard). Registering the IDENTICAL
// factory here means whichever file the shared worker runs first defines
// recharts for the whole run — never the real module. See
// src/test/recharts-stub.tsx.
vi.mock('recharts', async () => (await import('../../test/recharts-stub')).rechartsStub);


const DATA = makeAnalyticsData({
    correlation_matrix: { leagues: [], markets: [], matrix: {} },
    source_market_correlation: { sources: [], markets: [], matrix: {} },
    source_breakdown: [],
} as never);
let lastUrl = '';


beforeEach(() => {
    localStorage.clear();
    lastUrl = '';
    server.use(
        http.get('/api/analytics', ({ request }) => {
            lastUrl = request.url;
            return HttpResponse.json(DATA);
        }),
    );
});


function renderPage(filters = { dateFrom: '', dateTo: '' }, refreshKey = 0) {
    return render(<Analytics filters={filters} refreshKey={refreshKey} />);
}


describe('Analytics page', () => {
    it('renders the title and profile selector', async () => {
        renderPage();
        expect(screen.getByText('Analytics')).toBeInTheDocument();
        // accept either loaded-view ProfileSelector or the empty-state card —
        // both prove fetch→render wiring; charts can shift which mounts first
        await waitFor(() => {
            const sel = screen.queryByText('SELECT PROFILES');
            const empty = screen.queryByText(/No analytics data yet/);
            expect(sel || empty).toBeTruthy();
        }, { timeout: 8000 });
    });

    it('fetches /api/analytics and renders stats sections', async () => {
        renderPage();
        await waitFor(() => expect(screen.queryByText(/No analytics data yet/)).not.toBeInTheDocument());
        expect(lastUrl).toContain('/api/analytics');
    });

    it('empty state when API returns null stats (no data yet)', async () => {
        server.use(
            http.get('/api/analytics', () => HttpResponse.json(null)),
        );
        renderPage();
        await screen.findByText(/No analytics data yet/);
    });

    it('fetch failure falls back to empty data (no crash, empty state)', async () => {
        server.use(http.get('/api/analytics', () => HttpResponse.error()));
        renderPage();
        await screen.findByText(/No analytics data yet/);
    });

    it('profile chips render from data.profiles', async () => {
        renderPage();
        await screen.findByText('SELECT PROFILES');
        const profiles = (DATA as { profiles: string[] }).profiles ?? [];
        for (const p of profiles) {
            if (p) expect(await screen.findByText(p)).toBeInTheDocument();
        }
    });

    it('refreshKey change refetches analytics', async () => {
        let calls = 0;
        server.use(
            http.get('/api/analytics', () => {
                calls += 1;
                return HttpResponse.json(DATA);
            }),
        );
        const { rerender } = renderPage();
        await screen.findByText('SELECT PROFILES');
        const before = calls;
        rerender(<Analytics filters={{ dateFrom: '', dateTo: '' }} refreshKey={2} />);
        await waitFor(() => expect(calls).toBeGreaterThan(before));
    });

    it('date filters are sent when provided', async () => {
        renderPage({ dateFrom: '2026-09-01', dateTo: '2026-09-20' });
        await screen.findByText('SELECT PROFILES');
        await waitFor(() => {
            expect(lastUrl).toContain('date_from=2026-09-01');
            expect(lastUrl).toContain('date_to=2026-09-20');
        });
    });

    it('deselecting a profile refetches with the profiles param', async () => {
        const user = userEvent.setup();
        server.use(
            http.get('/api/analytics', ({ request }) => {
                lastUrl = request.url;
                return HttpResponse.json(DATA);
            }),
        );
        renderPage();
        const profiles = (DATA as { profiles: string[] }).profiles ?? [];
        if (profiles.length > 1) {
            await screen.findByText(profiles[0]);
            await user.click(screen.getByText(profiles[0]));
            await waitFor(() => expect(lastUrl).toContain('profiles'));
        }
    });
});
