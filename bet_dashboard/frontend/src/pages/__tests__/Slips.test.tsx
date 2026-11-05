// Slips page. ACTUAL divergences: WebSocket wiring lives in
// App.tsx (page accepts liveData prop); delete has NO confirm dialog
// (direct handleDelete); sort is a dropdown (8 options incl. net_profit with
// Pending sent to +/-Infinity); filters persist to 'slips_filters_state'.

import { describe, it, expect, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Slips from '../Slips';
import { server } from '../../test/handlers';
import { makeBetLeg, makeSlip, makeSlipsPage } from '../../test/factories';
import type { LiveData } from '../../types';


const PAGE = makeSlipsPage();
let lastSlipsUrl = '';


beforeEach(() => {
    lastSlipsUrl = '';
    localStorage.clear();
    server.use(
        http.get('/api/slips', ({ request }) => {
            lastSlipsUrl = new URL(request.url).searchParams.toString();
            return HttpResponse.json(PAGE);
        }),
        http.post('/api/slips/validate', () => HttpResponse.json({ checked: 5, settled: 2, live: 1, live_data: [] })),
        http.post('/api/slips/generate', () => HttpResponse.json({ generated: 3 })),
        http.delete('/api/slips/:id', () => HttpResponse.json({ status: 'ok' })),
    );
});


function renderPage(overrides: { refreshKey?: number; liveData?: LiveData } = {}) {
    return render(
        <MemoryRouter>
            <Slips filters={{ dateFrom: '', dateTo: '' }} refreshKey={0} {...overrides} />
        </MemoryRouter>,
    );
}


describe('Slips page', () => {
    it('fetches slips and renders the actions and slip cards', async () => {
        renderPage();
        expect(screen.getByText('✓ Validate Results')).toBeInTheDocument();
        await screen.findByText('Arsenal vs Chelsea');
    });

    it('renders slip cards with status badges and legs', async () => {
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        // 'Pending' + 'low' appear in multiple badges — getAllByText
        expect(screen.getAllByText('Pending').length).toBeGreaterThan(0);
        expect(screen.getByText('2026-09-24')).toBeInTheDocument();
        expect(screen.getAllByText('low').length).toBeGreaterThan(0);
    });

    it('sends hide_settled + live_only params from toggles', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByRole('button', { name: 'Filters' }));
        expect(lastSlipsUrl).toContain('hide_settled=false');
        expect(lastSlipsUrl).toContain('live_only=false');
        await user.click(screen.getByText('Hide settled'));
        await waitFor(() => expect(lastSlipsUrl).toContain('hide_settled=true'));
    });

    it('sort dropdown defaults to net_profit_desc and persists to localStorage', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByRole('button', { name: 'Filters' }));
        const select = screen.getByRole('combobox') as HTMLSelectElement;
        expect(select.value).toBe('net_profit_desc');
        await user.selectOptions(select, 'odds_desc');
        await waitFor(() => expect(lastSlipsUrl).toContain('sort_by=odds_desc'));
        const saved = localStorage.getItem('slips_filters_state');
        expect(saved).not.toBeNull();
        expect(JSON.parse(saved as string).sortBy).toBe('odds_desc');
    });

    it('Validate Results posts and shows the checked/settled/live status', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByText('✓ Validate Results'));
        expect(await screen.findByText(/Checked 5/)).toBeInTheDocument();
        expect(screen.getByText(/Settled 2/)).toBeInTheDocument();
        expect(screen.getByText(/Live 1/)).toBeInTheDocument();
    });

    it('Generate Slips posts and shows the generated count', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByText('✦ Generate Slips'));
        expect(await screen.findByText(/Generated 3 slip/)).toBeInTheDocument();
    });

    it('delete (via card Delete button, NO confirm dialog - divergence) reloads', async () => {
        const user = userEvent.setup();
        let deletes = 0;
        server.use(
            http.delete('/api/slips/:id', () => {
                deletes += 1;
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByTitle('Delete slip'));
        await waitFor(() => expect(deletes).toBe(1));
    });

    it('empty state renders when no slips returned', async () => {
        server.use(
            http.get('/api/slips', () => HttpResponse.json(makeSlipsPage({ slips: [], profiles: [] }))),
        );
        renderPage();
        await screen.findByText('No slips yet', {}, { timeout: 3000 });
        expect(screen.getByRole('button', { name: 'Generate Slips' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Go to Build' })).toBeInTheDocument();
    });

    it('fetch failure falls back to empty data (no crash)', async () => {
        server.use(http.get('/api/slips', () => HttpResponse.error()));
        renderPage();
        await screen.findByText('No slips yet', {}, { timeout: 3000 });
    });

    it('refreshKey increment refetches slips', async () => {
        let fetches = 0;
        server.use(
            http.get('/api/slips', () => {
                fetches += 1;
                return HttpResponse.json(PAGE);
            }),
        );
        const { rerender } = renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        const before = fetches;
        rerender(
            <MemoryRouter>
                <Slips filters={{ dateFrom: '', dateTo: '' }} refreshKey={1} />
            </MemoryRouter>,
        );
        await waitFor(() => expect(fetches).toBeGreaterThan(before));
    });

    it('card click opens SlipDetailModal, close resets', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        // open modal via neutral footer area
        await user.click(screen.getByText('1u'));
        expect(await screen.findByText('Betting Slip')).toBeInTheDocument();
        // close via backdrop
        const backdrop = document.querySelector('[class*="backdrop-blur-sm"]') as HTMLElement;
        await user.click(backdrop);
        await waitFor(() => expect(screen.queryByText('Betting Slip')).not.toBeInTheDocument());
    });

    it('profile chips come from data.profiles and toggle refetch with param', async () => {
        const user = userEvent.setup();
        server.use(
            http.get('/api/slips', ({ request }) => {
                lastSlipsUrl = new URL(request.url).searchParams.toString();
                return HttpResponse.json(PAGE);
            }),
        );
        renderPage();
        await user.click(screen.getByRole('button', { name: 'Filters' }));
        await screen.findByText('SELECT PROFILES');
        for (const p of PAGE.profiles) {
            // profile text appears in chips AND slip badges — count matches
            expect(screen.getAllByText(p).length).toBeGreaterThan(0);
        }
        // deselect one profile via the chip container (chip text also appears
        // in slip profile badges — scope to the chip wrapper)
        const chip = Array.from(document.querySelectorAll('div'))
            .filter((d) => d.className.includes('cursor-pointer'))
            .find((d) => d.textContent === PAGE.profiles[0]);
        expect(chip).toBeDefined();
        await user.click(chip as HTMLElement);
        await waitFor(() => expect(lastSlipsUrl).toContain('profiles'));
    });

    it('loads the next 20 slips when the scroll sentinel intersects', async () => {
        const pageOne = Array.from({ length: 20 }, (_, index) =>
            makeSlip({
                slip_id: index + 1,
                legs: [makeBetLeg({ match_name: `Team ${index + 1} vs Opponent` })],
            }),
        );
        const pageTwo = makeSlipsPage({
            slips: [makeSlip({ slip_id: 21, legs: [makeBetLeg({ match_name: 'Team 21 vs Opponent' })] })],
            page: 2,
            page_size: 20,
            total: 21,
            total_pages: 2,
        });
        let observerCallback: IntersectionObserverCallback | undefined;
        const originalObserver = window.IntersectionObserver;
        window.IntersectionObserver = class {
            constructor(callback: IntersectionObserverCallback) { observerCallback = callback; }
            observe() {}
            disconnect() {}
            unobserve() {}
            takeRecords(): IntersectionObserverEntry[] { return []; }
        } as unknown as typeof IntersectionObserver;
        let requestedPage = '';
        server.use(http.get('/api/slips', ({ request }) => {
            requestedPage = new URL(request.url).searchParams.get('page') ?? '';
            return HttpResponse.json(requestedPage === '2' ? pageTwo : {
                ...pageTwo,
                slips: pageOne,
                page: 1,
            });
        }));
        try {
            renderPage();
            await screen.findByText('Team 1 vs Opponent');
            expect(screen.getByText('Team 20 vs Opponent')).toBeInTheDocument();
            expect(screen.queryByText('Team 21 vs Opponent')).not.toBeInTheDocument();
            await waitFor(() => expect(observerCallback).toBeDefined());
            act(() => observerCallback?.(
                [{ isIntersecting: true } as IntersectionObserverEntry],
                {} as IntersectionObserver,
            ));
            await screen.findByText('Team 21 vs Opponent');
            expect(requestedPage).toBe('2');
        } finally {
            window.IntersectionObserver = originalObserver;
        }
    });
});
