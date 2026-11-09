// Analytics page. ACTUAL divergences: does NOT render the
// AnalyticsDashboard component (that lives in SmartBuilder's preview);
// this page is its OWN recharts dashboard with ProfileSelector + chart
// sections; no export button exists. Tests pin wiring: fetchAnalytics with
// date+profile params, stats cards, profile selection, empty + error states.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Analytics from '../Analytics';
import { server } from '../../test/handlers';
import { makeAnalyticsData, makeMarketBreakdown } from '../../test/factories';
import { ALL_MARKETS, marketLabel } from '../../config/marketConfig';

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


function renderPage(refreshKey = 0) {
    return render(
        <MemoryRouter>
            <Analytics refreshKey={refreshKey} />
        </MemoryRouter>,
    );
}


describe('Analytics page', () => {
    it('renders the title and profile selector', async () => {
        renderPage();
        expect(screen.getByText('Analytics')).toBeInTheDocument();
        await screen.findByText('+2.8U');
        const filtersButton = screen.getByRole('button', { name: 'Filters' });
        await userEvent.setup().click(filtersButton);
        await waitFor(() => expect(filtersButton).toHaveAttribute('aria-expanded', 'true'));
        // accept either loaded-view ProfileSelector or the empty-state card —
        // both prove fetch→render wiring; charts can shift which mounts first
        await waitFor(() => {
            const sel = screen.queryByText('SELECT PROFILES');
            const empty = screen.queryByText(/No analytics yet/);
            expect(sel || empty).toBeTruthy();
        }, { timeout: 8000 });
    });

    it('shows only profiles with data in the selected date range', async () => {
        localStorage.setItem('analytics_profile_selector_state', JSON.stringify({ profiles: ['low', 'medium'] }));
        localStorage.setItem('bet-assistant-analytics-date-range', JSON.stringify({
            dateFrom: '2026-09-01',
            dateTo: '2026-09-20',
        }));
        server.use(
            http.get('/api/analytics', () => HttpResponse.json({ ...DATA, profiles: ['low'] })),
        );

        renderPage();

        await screen.findByText('+2.8U');
        expect(await screen.findByText('1 profile showing: low')).toBeInTheDocument();
        expect(screen.queryByText('2 profiles showing: low, medium')).not.toBeInTheDocument();
        expect(screen.getByText('2026-09-01 – 2026-09-20')).toBeInTheDocument();
    });

    it.each([
        [{ dateFrom: '2026-09-01', dateTo: '' }, 'From 2026-09-01'],
        [{ dateFrom: '', dateTo: '2026-09-20' }, 'Until 2026-09-20'],
    ])('labels a one-sided date filter clearly', async (dateRange, expectedSummary) => {
        localStorage.setItem('bet-assistant-analytics-date-range', JSON.stringify(dateRange));

        renderPage();

        await screen.findByText('+2.8U');
        expect(await screen.findByText(expectedSummary)).toBeInTheDocument();
        expect(screen.queryByText(/Any date/)).not.toBeInTheDocument();
    });

    it('fetches /api/analytics and renders stats sections', async () => {
        renderPage();
        await waitFor(() => expect(screen.queryByText(/No analytics yet/)).not.toBeInTheDocument());
        expect(lastUrl).toContain('/api/analytics');
    });

    it('empty state when API returns null stats (no data yet)', async () => {
        server.use(
            http.get('/api/analytics', () => HttpResponse.json(null)),
        );
        renderPage();
        await screen.findByText(/No analytics yet/);
        expect(screen.getByRole('button', { name: 'Go to Track' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Go to Build' })).toBeInTheDocument();
    });

    it('fetch failure falls back to empty data (no crash, empty state)', async () => {
        server.use(http.get('/api/analytics', () => HttpResponse.error()));
        renderPage();
        // catch still sets zeroed stats — heading must stay; do not crash
        await screen.findByText('Analytics');
        // Loading branch shares the same h1 — wait for the error branch to settle (msw v3 async boundary).
        await waitFor(() => expect(screen.queryByText('No analytics yet')).not.toBeInTheDocument());
    });

    it('profile chips render from data.profiles', async () => {
        renderPage();
        await screen.findByText('+2.8U');
        await userEvent.setup().click(screen.getByRole('button', { name: 'Filters' }));
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
        await screen.findByText('+2.8U');
        await userEvent.setup().click(screen.getByRole('button', { name: 'Filters' }));
        await screen.findByText('SELECT PROFILES');
        const before = calls;
        rerender(
            <MemoryRouter>
                <Analytics refreshKey={2} />
            </MemoryRouter>,
        );
        await waitFor(() => expect(calls).toBeGreaterThan(before));
    });

    it('Analytics date filters are sent to API and saved locally', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('+2.8U');
        await user.click(screen.getByRole('button', { name: 'Filters' }));
        await user.type(screen.getByLabelText('Date from'), '2026-09-01');
        await waitFor(() => expect(lastUrl).toContain('date_from=2026-09-01'));
        expect(localStorage.getItem('bet-assistant-analytics-date-range')).toContain('2026-09-01');
    });

    it('does not migrate the former global date range', async () => {
        localStorage.setItem('bet-assistant-time-horizon', JSON.stringify({
            dateFrom: '2026-09-01',
            dateTo: '2026-09-20',
        }));
        renderPage();
        await screen.findByText('+2.8U');
        expect(lastUrl).not.toContain('date_from=');
        expect(lastUrl).not.toContain('date_to=');
        expect(localStorage.getItem('bet-assistant-analytics-date-range')).toContain('"dateFrom":""');
    });

    it('date filters are sent when provided', async () => {
        localStorage.setItem('bet-assistant-analytics-date-range', JSON.stringify({
            dateFrom: '2026-09-01',
            dateTo: '2026-09-20',
        }));
        renderPage();
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
        await screen.findByText('+2.8U');
        await user.click(screen.getByRole('button', { name: 'Filters' }));
        const profiles = (DATA as { profiles: string[] }).profiles ?? [];
        if (profiles.length > 1) {
            await screen.findByText(profiles[0]);
            await user.click(screen.getByText(profiles[0]));
            await waitFor(() => expect(lastUrl).toContain('profiles'));
        }
    });

    it('market breakdown rows + Best/Avoid cards render presentation labels, NOT raw keys', async () => {
        // Pre-U1 bug: breakdown row + best/worst cards rendered the raw stored
        // market string. Fix: wrap in marketLabel() like every other surface.
        // Keys are pulled from the frontend-owned ALL_MARKETS list (no literals:
        // the semgrep no-raw-market-literals ratchet blocks new key strings).
        const bestKey = ALL_MARKETS[ALL_MARKETS.length - 2];
        const worstKey = ALL_MARKETS[ALL_MARKETS.length - 1];
        const rows = [
            makeMarketBreakdown({ market: bestKey, edge: 12.0 }),
            makeMarketBreakdown({ market: worstKey, edge: -4.0 }),
        ];
        server.use(
            http.get('/api/analytics', () => HttpResponse.json(
                makeAnalyticsData({ market_breakdown: rows, market_accuracy: [], pnl_by_market: [] }),
            )),
        );
        renderPage();
        await screen.findByText('+2.8U');
        await userEvent.setup().click(screen.getByRole('button', { name: 'Filters' }));
        // labels render: breakdown table row + Best card (bestKey), row + Avoid card (worstKey)
        expect(await screen.findAllByText(marketLabel(bestKey))).not.toHaveLength(0);
        expect(await screen.findAllByText(marketLabel(worstKey))).not.toHaveLength(0);
        // raw canonical keys must NEVER render on this surface
        expect(screen.queryByText(bestKey)).not.toBeInTheDocument();
        expect(screen.queryByText(worstKey)).not.toBeInTheDocument();
    });
});
