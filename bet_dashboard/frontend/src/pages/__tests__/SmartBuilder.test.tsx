// SmartBuilder page (issue #65). ACTUAL behaviors pinned: 350ms debounced
// preview via fetchPreview; localStorage 'smart_builder_state' (cfg with
// dates STRIPPED); profile load via loadProfile with ?? defaults; save-name
// validation (manual-block + sanitize); Add to Slips leg validation;
// excluded cards (manual-only removal). REAL timers: fake timers broke MSW
// request delivery under isolate:false (D43 lesson).

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import SmartBuilder from '../SmartBuilder';
import { server } from '../../test/handlers';
import { makeCandidateLeg, makePreviewResult } from '../../test/factories';

// Order-robust shared stub (final-gate fix): SmartBuilder renders
// AnalyticsDashboard → recharts. Registering the IDENTICAL factory in every
// recharts-consuming file makes the run order-independent. See
// src/test/recharts-stub.tsx.
vi.mock('recharts', async () => (await import('../../test/recharts-stub')).rechartsStub);


const PREVIEW = makePreviewResult();
let previewCalls = 0;
let lastPreviewBody = '';


beforeEach(() => {
    localStorage.clear();
    previewCalls = 0;
    server.use(
        http.post('/api/builder/preview', async ({ request }) => {
            previewCalls += 1;
            lastPreviewBody = JSON.stringify(await request.json());
            return HttpResponse.json(PREVIEW);
        }),
        http.get('/api/profiles', () => HttpResponse.json({})),
        http.get('/api/builder/excluded/details', () => HttpResponse.json({ excluded: [] })),
        http.get('/api/builder/leagues', () => HttpResponse.json(['England', 'Spain'])),
        http.get('/api/config/sources', () => HttpResponse.json({ sources: ['forebet'] })),
        http.post('/api/slips', () => HttpResponse.json({ slip_id: 7, slip_status: 'Pending' })),
    );
});


async function renderAndHydrate() {
    render(<SmartBuilder filters={{ dateFrom: '', dateTo: '' }} refreshKey={0} />);
    // real timers: the 350ms debounce resolves inside waitFor's polling window
    await waitFor(() => expect(previewCalls).toBeGreaterThan(0), { timeout: 4000 });
}


describe('SmartBuilder page', () => {
    it('mounts and fires the debounced preview after 350ms', async () => {
        await renderAndHydrate();
        expect(screen.getByText('Live Preview — updates with every config change')).toBeInTheDocument();
    });

    it('renders profile sidebar + builder panel + preview grid', async () => {
        await renderAndHydrate();
        expect(screen.getByText('Profiles')).toBeInTheDocument();
        expect(screen.getByText('Bet Shape')).toBeInTheDocument();
        expect(screen.getByText('+ Add to Slips')).toBeInTheDocument();
        expect(screen.getByText('Reset excluded')).toBeInTheDocument();
    });

    it('config change triggers a NEW debounced preview (count increments)', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = previewCalls;
        const oddsInput = screen.getAllByDisplayValue('3')[0];
        await user.clear(oddsInput);
        await user.type(oddsInput, '5');
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });
    });

    it('config persists to localStorage with dates stripped', async () => {
        await renderAndHydrate();
        const saved = localStorage.getItem('smart_builder_state');
        expect(saved).not.toBeNull();
        const parsed = JSON.parse(saved as string);
        expect(parsed.cfg.target_odds).toBe(3);
        expect(parsed.cfg.date_from).toBeNull();
        expect(parsed.cfg.date_to).toBeNull();
        expect(parsed.activeName).toBe('manual');
        expect(parsed.units).toBe(1);
    });

    it('profile buttons render from fetchProfiles and load on click', async () => {
        server.use(
            http.get('/api/profiles', () => HttpResponse.json({ profiles: { cautious: { target_odds: 4, units: 2, target_legs: 4 } } })),
        );
        const user = userEvent.setup();
        await renderAndHydrate();
        const chip = await screen.findByText('cautious');
        await user.click(chip);
        const input = screen.getByPlaceholderText('profile name') as HTMLInputElement;
        await waitFor(() => expect(input.value).toBe('cautious'), { timeout: 3000 });
        await waitFor(() => expect(lastPreviewBody).toContain('"target_odds":4'), { timeout: 3000 });
    });

    it('save with empty/manual name is blocked with status', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByText('Save'));
        expect(screen.getByText('Enter a profile name first.')).toBeInTheDocument();
    });

    it('save with valid name POSTs and confirms', async () => {
        const user = userEvent.setup();
        let saved = 0;
        server.use(
            http.post('/api/profiles', () => {
                saved += 1;
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        await renderAndHydrate();
        const nameInput = screen.getByPlaceholderText('profile name');
        await user.clear(nameInput);
        await user.type(nameInput, 'My Profile!');
        await user.click(screen.getByText('Save'));
        expect(await screen.findByText(/Profile 'myprofile' saved/, {}, { timeout: 3000 })).toBeInTheDocument();
        expect(saved).toBe(1);
    });

    it('Add to Slips with empty preview shows No legs status', async () => {
        const user = userEvent.setup();
        server.use(
            http.post('/api/builder/preview', async () => {
                previewCalls += 1;
                return HttpResponse.json({ legs: [], total_odds: 1, pending_urls: [] });
            }),
        );
        render(<SmartBuilder filters={{ dateFrom: '', dateTo: '' }} refreshKey={0} />);
        await waitFor(() => expect(previewCalls).toBeGreaterThan(0), { timeout: 4000 });
        await user.click(screen.getByText('+ Add to Slips'));
        expect(screen.getByText('No legs in preview.')).toBeInTheDocument();
    });

    it('Add to Slips with valid legs POSTs and confirms with slip id', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByText('+ Add to Slips'));
        expect(await screen.findByText(/Slip #7 added/, {}, { timeout: 3000 })).toBeInTheDocument();
    });

    it('excluded matches cards render from fetchExcludedDetails', async () => {
        server.use(
            http.get('/api/builder/excluded/details', () => HttpResponse.json({
                excluded: [
                    { match_name: 'Bad Match', datetime: '2026-09-26T12:00', reason: 'Manually excluded', url: 'https://example.com/x' },
                    { match_name: 'In Slip Match', datetime: null, reason: 'In pending slip', url: 'https://example.com/y' },
                ],
            })),
        );
        await renderAndHydrate();
        expect(await screen.findByText('Excluded Matches (2)', {}, { timeout: 3000 })).toBeInTheDocument();
        expect(screen.getByText('Bad Match')).toBeInTheDocument();
        expect(screen.getByText('In Slip Match')).toBeInTheDocument();
    });

    it('excluded card remove (manual only) calls removeExcluded and refetches', async () => {
        const user = userEvent.setup();
        let removes = 0;
        server.use(
            http.get('/api/builder/excluded/details', () => HttpResponse.json({
                excluded: [{ match_name: 'Bad Match', datetime: null, reason: 'Manually excluded', url: 'https://example.com/x' }],
            })),
            http.post('/api/builder/excluded/remove', () => {
                removes += 1;
                return HttpResponse.json({ excluded: [] });
            }),
        );
        await renderAndHydrate();
        const removeBtn = await screen.findByTitle('Remove from manual exclusions', {}, { timeout: 3000 });
        await user.click(removeBtn);
        await waitFor(() => expect(removes).toBe(1), { timeout: 3000 });
    });

    it('refreshKey increment triggers a fresh preview', async () => {
        const initial = render(<SmartBuilder filters={{ dateFrom: '', dateTo: '' }} refreshKey={0} />);
        await waitFor(() => expect(previewCalls).toBeGreaterThan(0), { timeout: 4000 });
        const before = previewCalls;
        initial.rerender(<SmartBuilder filters={{ dateFrom: '2026-09-25', dateTo: '' }} refreshKey={1} />);
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });
        await waitFor(() => expect(lastPreviewBody).toContain('2026-09-25'), { timeout: 3000 });
    });

    it('target payout auto-calculates units from preview odds', async () => {
        const user = userEvent.setup();
        server.use(
            http.post('/api/builder/preview', async () => {
                previewCalls += 1;
                return HttpResponse.json({ legs: [makeCandidateLeg()], total_odds: 2.5, pending_urls: [] });
            }),
        );
        await renderAndHydrate();
        const payoutInput = screen.getByPlaceholderText('Off');
        await user.clear(payoutInput);
        await user.type(payoutInput, '25');
        // 25 / 2.5 = 10 units
        await waitFor(() => {
            const unitsInput = screen.getByDisplayValue('10') as HTMLInputElement;
            expect(unitsInput).toBeInTheDocument();
        }, { timeout: 3000 });
    });
});
