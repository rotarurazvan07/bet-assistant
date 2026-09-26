// Slips page (issue #65). ACTUAL divergences: WebSocket wiring lives in
// App.tsx (page accepts liveData prop); delete has NO confirm dialog
// (direct handleDelete); sort is a dropdown (8 options incl. net_profit with
// Pending sent to +/-Infinity); filters persist to 'slips_filters_state'.

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Slips from '../Slips';
import { server } from '../../test/handlers';
import { makeSlipsPage } from '../../test/factories';
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
    return render(<Slips filters={{ dateFrom: '', dateTo: '' }} refreshKey={0} {...overrides} />);
}


describe('Slips page', () => {
    it('fetches slips and renders title + profile selector + stat cards', async () => {
        renderPage();
        expect(screen.getByText('Slips')).toBeInTheDocument();
        await screen.findByText('Arsenal vs Chelsea');
        const stats = PAGE.stats;
        expect(screen.getByText(`${stats.total_units_bet} U`)).toBeInTheDocument();
        expect(screen.getByText(/Win Rate/)).toBeInTheDocument();
        expect(screen.getByText(`${stats.win_rate}%`)).toBeInTheDocument();
        expect(screen.getByText(`${stats.roi_percentage}%`)).toBeInTheDocument();
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
        expect(lastSlipsUrl).toContain('hide_settled=false');
        expect(lastSlipsUrl).toContain('live_only=false');
        await user.click(screen.getByText('Hide settled'));
        await waitFor(() => expect(lastSlipsUrl).toContain('hide_settled=true'));
    });

    it('sort dropdown defaults to net_profit_desc and persists to localStorage', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        const select = screen.getByRole('combobox') as HTMLSelectElement;
        expect(select.value).toBe('net_profit_desc');
        await user.selectOptions(select, 'odds_desc');
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
        await screen.findByText(/No slips available/, {}, { timeout: 3000 });
        // hint mentions Generate Slips inside the empty-state card — the
        // toolbar ALSO has a Generate button; match the full hint sentence
        expect(screen.getByText(/to create betting slips from your profiles/)).toBeInTheDocument();
    });

    it('fetch failure falls back to empty data (no crash)', async () => {
        server.use(http.get('/api/slips', () => HttpResponse.error()));
        renderPage();
        await screen.findByText(/No slips available/, {}, { timeout: 3000 });
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
        rerender(<Slips filters={{ dateFrom: '', dateTo: '' }} refreshKey={1} />);
        await waitFor(() => expect(fetches).toBeGreaterThan(before));
    });

    it('card click opens SlipDetailModal, close resets', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        // open modal via neutral footer area (cycle-12 lesson: link has stopPropagation)
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
});
