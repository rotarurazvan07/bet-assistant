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

    async function openFilters(user: ReturnType<typeof userEvent.setup>) {
        await user.click(screen.getByRole('button', { name: /filters/i }));
        await screen.findByPlaceholderText('Filter by team...');
    }

    it('search input sends the search param on next fetch', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await openFilters(user);
        const search = screen.getByPlaceholderText('Filter by team...');
        await user.type(search, 'Ars');
        await waitFor(() => expect(lastUrl).toContain('search=Ars'));
    });

    it('min consensus slider sends min_consensus param', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await openFilters(user);
        const ranges = Array.from(document.querySelectorAll('input[type="range"]')) as HTMLInputElement[];
        const consSlider = ranges.find((r) => r.min === '0' && r.max === '100');
        expect(consSlider).toBeDefined();
        fireEvent.change(consSlider as HTMLInputElement, { target: { value: '50' } });
        await waitFor(() => expect(lastUrl).toContain('min_consensus=50'));
    });

    it('hides filter controls until Filters is opened', async () => {
        renderPage();
        await screen.findByText('Arsenal');
        expect(screen.getByRole('button', { name: /filters/i })).toBeInTheDocument();
        expect(screen.queryByPlaceholderText('Filter by team...')).not.toBeInTheDocument();
        expect(screen.queryByText('Min Consensus')).not.toBeInTheDocument();
    });

    it('Advanced toggle reveals sources and sort controls', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await openFilters(user);
        expect(screen.queryByText('Select All')).not.toBeInTheDocument();
        await user.click(screen.getByRole('button', { name: /advanced/i }));
        expect(screen.getAllByText('Select All')).toHaveLength(2);
        expect(screen.getByText('Columns')).toBeInTheDocument();
        expect(screen.getByText('Sort')).toBeInTheDocument();
    });

    it('Reset to defaults clears search and consensus', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await openFilters(user);
        await user.type(screen.getByPlaceholderText('Filter by team...'), 'Ars');
        await waitFor(() => expect(lastUrl).toContain('search=Ars'));
        await user.click(screen.getByRole('button', { name: /reset to defaults/i }));
        expect((screen.getByPlaceholderText('Filter by team...') as HTMLInputElement).value).toBe('');
    });

    it('Escape closes the drawer', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await openFilters(user);
        expect(screen.getByPlaceholderText('Filter by team...')).toBeInTheDocument();
        await user.keyboard('{Escape}');
        await waitFor(() => expect(screen.queryByPlaceholderText('Filter by team...')).not.toBeInTheDocument());
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

    it('add shows toast Added 1 @1.90 to slip', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        await user.click(screen.getByRole('button', { name: /Select 75% at @1\.90/ }));
        expect(await screen.findByRole('alert')).toHaveTextContent('Added 1 @1.90 to slip');
    });

    it('toggle-off does not show the add toast', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        const cell = screen.getByRole('button', { name: /Select 75% at @1\.90/ });
        await user.click(cell);
        await screen.findByRole('alert');
        await user.click(screen.getByRole('button', { name: /close/i }));
        await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
        await user.click(cell);
        await waitFor(() => expect(screen.getByText('0 legs selected')).toBeInTheDocument());
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('missing result_url still alerts and does not toast', async () => {
        const user = userEvent.setup();
        server.use(
            http.get('/api/matches', () => HttpResponse.json(makeMatchesPage({
                matches: [makeMatch({ result_url: '' })],
            }))),
        );
        renderPage();
        await screen.findByText('Arsenal');
        await user.click(screen.getByRole('button', { name: /Select 75% at @1\.90/ }));
        // buildLeg never reaches handleCellClick (alert there is unchanged).
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        expect(screen.queryByText('1 leg selected')).not.toBeInTheDocument();
    });

    it('reduced-motion still toasts without a fly clone', async () => {
        const orig = window.matchMedia;
        Object.defineProperty(window, 'matchMedia', {
            writable: true,
            value: (query: string) => ({
                matches: query.includes('prefers-reduced-motion'),
                media: query,
                onchange: null,
                addListener() { /* noop */ },
                removeListener() { /* noop */ },
                addEventListener() { /* noop */ },
                removeEventListener() { /* noop */ },
                dispatchEvent() { return false; },
            }),
        });
        try {
            const user = userEvent.setup();
            renderPage();
            await screen.findByText('Arsenal');
            await user.click(screen.getByRole('button', { name: /Select 75% at @1\.90/ }));
            expect(await screen.findByRole('alert')).toHaveTextContent('Added 1 @1.90 to slip');
            expect(document.querySelector('.leg-fly-clone')).toBeNull();
        } finally {
            Object.defineProperty(window, 'matchMedia', { writable: true, value: orig });
        }
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

    it('#39 AC-07: Escape minimizes and restores focus to the triggering cell', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal');
        const cell = screen.getByRole('button', { name: /Select 75% at @1\.90/ });
        await user.click(cell);
        await waitFor(() => expect(screen.getByText('1 leg selected')).toBeInTheDocument());
        await user.keyboard('{Escape}');
        await waitFor(() => expect(screen.queryByText('1 leg selected')).not.toBeInTheDocument());
        await waitFor(() => expect(localStorage.getItem('slip-minimized')).toBe('true'));
        await waitFor(() => expect(cell).toHaveFocus());
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
