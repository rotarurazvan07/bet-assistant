// BettingTips page (issue #65). ACTUAL divergences: NO 'Add to Builder'
// button — market-cell clicks toggle legs into FloatingSlipBuilder directly;
// sources filter is an MUI Popover with checkboxes (not a plain multiselect);
// filters persist across 4 localStorage keys; handleAddSlip uses alert().

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import BettingTips from '../BettingTips';
import { server } from '../../test/handlers';
import { makeMatchesPage, makeMatch } from '../../test/factories';


const THE_MATCH = makeMatch({ match_id: 'm-1', home: 'Arsenal', away: 'Chelsea' });
const PAGE_ONE = makeMatchesPage({ total: 120, page: 1, total_pages: 3, matches: [THE_MATCH] });
let lastUrl = '';


beforeEach(() => {
    localStorage.clear();
    lastUrl = '';
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    server.use(
        http.get('/api/matches', ({ request }) => {
            lastUrl = request.url;
            return HttpResponse.json(PAGE_ONE);
        }),
        http.get('/api/odds-history/movements/all', () => HttpResponse.json({})),
        http.get('/api/slips', () => HttpResponse.json({ slips: [], stats: null, profiles: [] })),
        http.get('/api/config/sources', () => HttpResponse.json({ sources: ['forebet', 'predictz'] })),
        http.post('/api/slips', () => HttpResponse.json({ slip_id: 42, slip_status: 'Pending' })),
    );
});


function renderPage(filters = { dateFrom: '', dateTo: '' }, refreshKey = 0) {
    return render(<BettingTips filters={filters} refreshKey={refreshKey} />);
}


describe('BettingTips page', () => {
    it('renders title + match count + the match row', async () => {
        renderPage();
        expect(screen.getByText('Betting Tips')).toBeInTheDocument();
        await screen.findByText('Arsenal');
        expect(screen.getByText(/120 matches/)).toBeInTheDocument();
        expect(screen.getByText(/page 1 of 3/)).toBeInTheDocument();
    });

    it('fetch sends page/page_size and sort defaults (datetime asc)', async () => {
        renderPage();
        await screen.findByText('Arsenal');
        expect(lastUrl).toContain('page=1');
        expect(lastUrl).toContain('page_size=40');
        expect(lastUrl).toContain('sort_by=datetime');
        expect(lastUrl).toContain('sort_dir=asc');
    });

    it('empty state when total is 0', async () => {
        server.use(
            http.get('/api/matches', () => HttpResponse.json(makeMatchesPage({ total: 0, matches: [], total_pages: 1 }))),
        );
        renderPage();
        await screen.findByText(/No matches available/);
        expect(screen.getByText(/Pull Update/)).toBeInTheDocument();
    });

    it('search input sends the search param on next fetch', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        const search = screen.getByPlaceholderText('Filter by team...');
        await user.type(search, 'Ars');
        await waitFor(() => expect(lastUrl).toContain('search=Ars'));
    });

    it('min consensus slider sends min_consensus param', async () => {
        renderPage();
        await screen.findByText('Arsenal');
        // label is not associated with the control (div, not <label for>) —
        // query the consensus range directly: min=0 max=100 step=5
        const ranges = Array.from(document.querySelectorAll('input[type="range"]')) as HTMLInputElement[];
        const consSlider = ranges.find((r) => r.min === '0' && r.max === '100');
        expect(consSlider).toBeDefined();
        fireEvent.change(consSlider as HTMLInputElement, { target: { value: '50' } });
        await waitFor(() => expect(lastUrl).toContain('min_consensus=50'));
    });

    it('sorting: clicking a header toggles direction', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await user.click(screen.getByText('Date'));
        await waitFor(() => expect(lastUrl).toContain('sort_dir=desc'));
    });

    it('market cell click adds a leg to the FloatingSlipBuilder', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        const cell = screen.getByRole('button', { name: /Select 75% at @1\.90/ });
        await user.click(cell);
        // FloatingSlipBuilder (document.body portal) — EXPANDED panel header shows 'N legs selected'
        await waitFor(() => expect(screen.getByText('1 leg selected')).toBeInTheDocument());
    });

    it('clicking the same cell again toggles the leg off (dedupe by url+market)', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        const cell = screen.getByRole('button', { name: /Select 75% at @1\.90/ });
        await user.click(cell);
        await waitFor(() => expect(screen.getByText('1 leg selected')).toBeInTheDocument());
        await user.click(cell);
        await waitFor(() => expect(screen.getByText('0 legs selected')).toBeInTheDocument());
    });

    it('pagination click fetches the next page', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        const pageTwoBtn = Array.from(document.querySelectorAll('button')).find((b) => b.textContent === '2');
        expect(pageTwoBtn).toBeDefined();
        await user.click(pageTwoBtn as HTMLElement);
        await waitFor(() => expect(lastUrl).toContain('page=2'));
    });

    it('Add Slip (via floating builder) posts manual legs and clears them', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await user.click(screen.getByRole('button', { name: /Select 75% at @1\.90/ }));
        await waitFor(() => expect(screen.getByText('1 leg selected')).toBeInTheDocument());
        await user.click(screen.getByText('Add Slip'));
        await waitFor(() => expect(screen.getByText('0 legs selected')).toBeInTheDocument());
        expect(window.alert).not.toHaveBeenCalled();
    });

    it('pending legs persist to localStorage (betting_tips_state)', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await user.click(screen.getByRole('button', { name: /Select 75% at @1\.90/ }));
        await waitFor(() => {
            const saved = localStorage.getItem('betting_tips_state');
            expect(saved).not.toBeNull();
            expect(JSON.parse(saved as string).pendingLegs.length).toBe(1);
        });
    });

    it('refreshKey change refetches matches + slip selections', async () => {
        let matchFetches = 0;
        server.use(
            http.get('/api/matches', () => {
                matchFetches += 1;
                return HttpResponse.json(PAGE_ONE);
            }),
        );
        const { rerender } = renderPage({ dateFrom: '', dateTo: '' }, 0);
        await screen.findByText('Arsenal');
        const before = matchFetches;
        rerender(<BettingTips filters={{ dateFrom: '', dateTo: '' }} refreshKey={1} />);
        await waitFor(() => expect(matchFetches).toBeGreaterThan(before));
    });
});
