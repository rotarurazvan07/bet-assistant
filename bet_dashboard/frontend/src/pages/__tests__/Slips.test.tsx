// Slips page. ACTUAL divergences: WebSocket wiring lives in
// App.tsx (page accepts liveData prop); delete has NO confirm dialog
// (direct handleDelete); sort is a dropdown (8 options incl. net_profit with
// Pending sent to +/-Infinity); filters persist to 'slips_filters_state'.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Slips from '../Slips';
import { server } from '../../test/handlers';
import { makeBetLeg, makeSlip, makeSlipsPage } from '../../test/factories';
import type { LiveData, ValidationCompletion, ValidationProgress } from '../../types';


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


function renderPage(overrides: {
    refreshKey?: number;
    liveData?: LiveData;
    validationProgress?: ValidationProgress;
    validationCompletion?: ValidationCompletion;
} = {}) {
    return render(
        <MemoryRouter>
            <Slips refreshKey={0} {...overrides} />
        </MemoryRouter>,
    );
}


describe('Slips page', () => {
    it('fetches slips and renders the actions and slip cards', async () => {
        renderPage();
        expect(screen.getByRole('button', { name: 'Validate Results' })).toHaveTextContent('Validate results');
        expect(screen.getByRole('button', { name: 'Generate Slips' })).toBeInTheDocument();
        await screen.findByText('Arsenal vs Chelsea');
    });

    it('date range in Track filters is sent to slips API and saved locally', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByRole('button', { name: 'Filters' }));
        await user.type(screen.getByLabelText('Date from'), '2026-09-01');

        await waitFor(() => expect(lastSlipsUrl).toContain('date_from=2026-09-01'));
        expect(localStorage.getItem('bet-assistant-track-date-range')).toContain('2026-09-01');
    });

    it('renders slip cards with status badges and legs', async () => {
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        // 'Pending' + 'low' appear in multiple badges — getAllByText
        expect(screen.getAllByText('Pending').length).toBeGreaterThan(0);
        expect(screen.getByText('2026-09-24')).toBeInTheDocument();
        expect(screen.getAllByText('low').length).toBeGreaterThan(0);
    });

    it('shows either the calendar or slip grid, not both', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');

        await user.click(screen.getByRole('button', { name: 'Calendar view' }));
        expect(await screen.findByRole('region', { name: 'Daily profit calendar' })).toBeInTheDocument();
        expect(screen.queryByText('Arsenal vs Chelsea')).not.toBeInTheDocument();

        await user.click(screen.getByRole('button', { name: 'Grid view' }));
        await screen.findByText('Arsenal vs Chelsea');
        expect(screen.queryByRole('region', { name: 'Daily profit calendar' })).not.toBeInTheDocument();
    });

    it('only shows slip-specific filters in grid mode', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByRole('button', { name: 'Calendar view' }));
        await user.click(screen.getByRole('button', { name: 'Filters' }));

        expect(screen.getByText('SELECT PROFILES')).toBeInTheDocument();
        expect(screen.queryByLabelText('Date from')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('Date to')).not.toBeInTheDocument();
        expect(screen.queryByText('Hide settled')).not.toBeInTheDocument();
        expect(screen.queryByText('Live only')).not.toBeInTheDocument();
        expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
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

    it('validates results and shows a concise completion notice', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByRole('button', { name: 'Validate Results' }));
        const validationRow = screen.getByRole('button', { name: 'Validate Results' }).parentElement;
        expect(await within(validationRow as HTMLElement).findByRole('status'))
            .toHaveTextContent('Results checked · 5 match(es) · 2 settled');
        expect(screen.queryByText(/Live 1/)).not.toBeInTheDocument();
    });

    it('shows live validation progress beside the action and can cancel', async () => {
        const user = userEvent.setup();
        let jobId = '';
        let finishValidation!: () => void;
        let cancelRequested = false;
        server.use(
            http.post('/api/slips/validate', async ({ request }) => {
                const body = await request.json() as { job_id: string };
                jobId = body.job_id;
                await new Promise<void>(resolve => { finishValidation = resolve; });
                return HttpResponse.json({
                    checked: 5, settled: 0, live: 0, errors: 0, live_data: [], cancelled: true,
                });
            }),
            http.post('/api/slips/validate/:jobId/cancel', () => {
                cancelRequested = true;
                return HttpResponse.json({ cancelled: true });
            }),
        );
        const { rerender } = renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        await user.click(screen.getByRole('button', { name: 'Validate Results' }));
        await waitFor(() => expect(jobId).not.toBe(''));

        rerender(
            <MemoryRouter>
                <Slips
                    refreshKey={0}
                    validationProgress={{
                        job_id: jobId,
                        checked: 2,
                        total: 5,
                        current_match: 'Arsenal vs Chelsea',
                    }}
                />
            </MemoryRouter>,
        );
        const progressButton = screen.getByRole('button', { name: 'Cancel slip validation' });
        expect(progressButton).toHaveTextContent('Stop checking');
        expect(screen.getByText('Checking Arsenal vs Chelsea')).toBeInTheDocument();
        expect(screen.getByText('2/5')).toBeInTheDocument();
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '2');

        await user.click(progressButton);
        await waitFor(() => expect(cancelRequested).toBe(true));
        expect(screen.getByText('Stopping…')).toBeInTheDocument();
        finishValidation();
        expect(await screen.findByRole('status')).toHaveTextContent('Validation stopped.');
    });

    it('shows verifier progress without a manual validation request', async () => {
        renderPage({
            validationProgress: {
                job_id: 'verifier-job',
                checked: 1,
                total: 3,
                current_match: 'Arsenal vs Chelsea',
            },
        });

        const button = screen.getByRole('button', { name: 'Validate Results' });
        expect(button).toBeDisabled();
        expect(button).toHaveTextContent('Checking results…');
        expect(screen.getByText('Checking Arsenal vs Chelsea')).toBeInTheDocument();
        expect(screen.getByText('1/3')).toBeInTheDocument();
    });

    it('Generate Slips posts and shows the generated count', async () => {
        const user = userEvent.setup();
        renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        const generateButton = screen.getByRole('button', { name: 'Generate Slips' });
        await user.click(generateButton);
        const generateStatus = await within(generateButton.parentElement as HTMLElement).findByRole('status');
        expect(generateStatus).toHaveTextContent('Generated 3 slip(s)');
    });

    it('fades out validation completion notices after five seconds', async () => {
        const { rerender } = renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        vi.useFakeTimers();
        try {
            rerender(
                <MemoryRouter>
                    <Slips
                        refreshKey={0}
                        validationCompletion={{
                            job_id: 'verifier-job',
                            checked: 1,
                            settled: 0,
                            live: 0,
                            errors: 0,
                        }}
                    />
                </MemoryRouter>,
            );
            expect(screen.getByRole('status')).toHaveTextContent('Results checked · 1 match(es)');
            act(() => vi.advanceTimersByTime(5100));
            expect(screen.queryByRole('status')).not.toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
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
        expect(screen.getAllByRole('button', { name: 'Generate Slips' })).toHaveLength(2);
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
                <Slips refreshKey={1} />
            </MemoryRouter>,
        );
        await waitFor(() => expect(fetches).toBeGreaterThan(before));
    });

    it('does not refetch the grid when validation progress changes', async () => {
        let fetches = 0;
        server.use(
            http.get('/api/slips', () => {
                fetches += 1;
                return HttpResponse.json(PAGE);
            }),
        );
        const { rerender } = renderPage();
        await screen.findByText('Arsenal vs Chelsea');
        expect(fetches).toBe(1);

        rerender(
            <MemoryRouter>
                <Slips
                    refreshKey={0}
                    validationProgress={{
                        job_id: 'verifier-job',
                        checked: 1,
                        total: 3,
                        current_match: 'Arsenal vs Chelsea',
                    }}
                />
            </MemoryRouter>,
        );
        await waitFor(() => expect(screen.getByText('1/3')).toBeInTheDocument());
        expect(fetches).toBe(1);
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
