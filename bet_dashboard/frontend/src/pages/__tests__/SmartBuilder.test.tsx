// SmartBuilder page — story 41-96 rework contract:
//   AC-1  all saved profiles render as cards; click loads into the builder
//   AC-2  each card has a top-corner X that DELETEs that profile (header
//         Delete button gone)
//   AC-3  trailing '+' creates new{N} copying the CURRENT cfg, saves via
//         POST /api/profiles and selects it
//   AC-4  Units / Target Payout live in the Add-to-Slips modal, NOT header
//   AC-5  '+ Add to Slips' OPENS the confirmation modal
//   AC-6  modal confirm POSTs /api/slips and closes
//   AC-7  Escape/Cancel/backdrop close the modal without posting
// Existing pins kept: 350ms debounce, localStorage payload, excluded cards,
// refreshKey, real timers (fake timers broke MSW delivery — D43 lesson).

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import SmartBuilder from '../SmartBuilder';
import { server } from '../../test/handlers';
import { makeCandidateLeg, makePreviewResult, makeProfile } from '../../test/factories';

// Order-robust shared stub (final-gate fix): SmartBuilder renders
// AnalyticsDashboard → recharts. Registering the IDENTICAL factory in every
// recharts-consuming file makes the run order-independent.
vi.mock('recharts', async () => (await import('../../test/recharts-stub')).rechartsStub);

// Distinct configs so tests can prove a card click actually LOADED a profile.
const PROFILES = {
    cautious: makeProfile({ target_odds: 4, target_legs: 4, units: 2 }),
    bold: makeProfile({ target_odds: 8, target_legs: 5, units: 3 }),
};

const PREVIEW = makePreviewResult();
let previewCalls = 0;
let lastPreviewBody = '';
let slipPosts = 0;
let deleted: string[] = [];
let profileMap: Record<string, ReturnType<typeof makeProfile>> = { ...PROFILES };

beforeEach(() => {
    localStorage.clear();
    previewCalls = 0;
    lastPreviewBody = '';
    slipPosts = 0;
    deleted = [];
    profileMap = { ...PROFILES };
    server.use(
        http.post('/api/builder/preview', async ({ request }) => {
            previewCalls += 1;
            lastPreviewBody = JSON.stringify(await request.json());
            return HttpResponse.json(PREVIEW);
        }),
        http.get('/api/profiles', () => HttpResponse.json({ profiles: { ...profileMap } })),
        http.post('/api/profiles', async ({ request }) => {
            const body = await request.json() as Record<string, unknown>;
            profileMap[String(body.name)] = body as unknown as ReturnType<typeof makeProfile>;
            return HttpResponse.json({ status: 'ok' });
        }),
        http.delete('/api/profiles/:name', ({ params }) => {
            deleted.push(String(params.name));
            delete profileMap[String(params.name)];
            return HttpResponse.json({ ok: true });
        }),
        http.get('/api/builder/excluded/details', () => HttpResponse.json({ excluded: [] })),
        http.get('/api/builder/leagues', () => HttpResponse.json(['England', 'Spain'])),
        http.get('/api/config/sources', () => HttpResponse.json({ sources: ['forebet'] })),
        http.post('/api/slips', () => {
            slipPosts += 1;
            return HttpResponse.json({ slip_id: 7, slip_status: 'Pending' });
        }),
    );
});

function renderBuilder(filters = { dateFrom: '', dateTo: '' }, refreshKey = 0) {
    return render(
        <MemoryRouter>
            <SmartBuilder filters={filters} refreshKey={refreshKey} />
        </MemoryRouter>,
    );
}

async function renderAndHydrate() {
    renderBuilder();
    await waitFor(() => expect(previewCalls).toBeGreaterThan(0), { timeout: 4000 });
}

describe('SmartBuilder page', () => {
    it('mounts and fires the debounced preview after 350ms', async () => {
        await renderAndHydrate();
        expect(screen.getByText('Live Preview — updates with every config change')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Build' })).toBeInTheDocument();
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

    // ── AC-1: profile cards replace the combobox ────────────────────────────

    it('AC-1: renders every saved profile as a card (no combobox)', async () => {
        await renderAndHydrate();
        expect(screen.getByRole('button', { name: 'cautious' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'bold' })).toBeInTheDocument();
        expect(screen.queryByPlaceholderText('profile name')).not.toBeInTheDocument();
    });

    it('AC-1: clicking a card loads its config into the builder', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = previewCalls;
        await user.click(screen.getByRole('button', { name: 'cautious' }));
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });
        expect(lastPreviewBody).toContain('"target_odds":4');
    });

    it('AC-1/7.3: header no longer carries Reset excluded or Run Daily', async () => {
        await renderAndHydrate();
        expect(screen.queryByText('Reset excluded')).not.toBeInTheDocument();
        expect(screen.queryByText('Run Daily')).not.toBeInTheDocument();
    });

    // ── AC-2: per-card X delete ─────────────────────────────────────────────

    it('AC-2: X DELETEs that profile and falls back to manual when it was active', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'cautious' }));
        await user.click(screen.getByRole('button', { name: /Delete profile 'cautious'/ }));
        await waitFor(() => expect(deleted).toEqual(['cautious']), { timeout: 3000 });
        expect(await screen.findByText("Deleted 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'cautious' })).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'bold' })).toBeInTheDocument();
    });

    it('AC-2: X on a NON-active profile deletes it and keeps the active one', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await user.click(screen.getByRole('button', { name: /Delete profile 'cautious'/ }));
        await waitFor(() => expect(deleted).toEqual(['cautious']), { timeout: 3000 });
        // bold survived and stayed selected (aria-pressed marker)
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
        expect(await screen.findByText("Deleted 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
    });

    it('AC-2: header Delete button is gone (X is the only delete path)', async () => {
        await renderAndHydrate();
        expect(screen.queryByRole('button', { name: 'Delete', exact: true })).not.toBeInTheDocument();
    });

    // ── AC-3: '+' creates new{N} from the current config ────────────────────

    it('AC-3: + saves the current cfg as new1 and selects it', async () => {
        const user = userEvent.setup();
        let savedBody: Record<string, unknown> = {};
        server.use(
            http.post('/api/profiles', async ({ request }) => {
                savedBody = await request.json() as Record<string, unknown>;
                profileMap['new1'] = savedBody as unknown as ReturnType<typeof makeProfile>;
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: '+' }));
        await waitFor(() => expect(savedBody.name).toBe('new1'), { timeout: 3000 });
        // current cfg copied (default target_odds 3, units 1)
        expect(savedBody.target_odds).toBe(3);
        expect(savedBody.units).toBe(1);
        expect(await screen.findByText(/Profile 'new1' saved/, {}, { timeout: 3000 })).toBeInTheDocument();
        // selected: new card exists and is pressed
        const card = await screen.findByRole('button', { name: 'new1' }, { timeout: 3000 });
        expect(card).toHaveAttribute('aria-pressed', 'true');
    });

    it('AC-3: rapid double-click on + never creates a duplicate name', async () => {
        // Two clicks with the in-flight guard may still both save (that is
        // legitimate: new1 then new2) — the invariant is that no name is
        // written twice. Without the guard both clicks read the same stale
        // profiles map and both POST 'new1'.
        const user = userEvent.setup();
        const savedNames: string[] = [];
        server.use(
            http.post('/api/profiles', async ({ request }) => {
                const body = await request.json() as Record<string, unknown>;
                savedNames.push(String(body.name));
                profileMap[String(body.name)] = body as unknown as ReturnType<typeof makeProfile>;
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        await renderAndHydrate();
        await user.dblClick(screen.getByRole('button', { name: '+' }));
        await waitFor(() => expect(savedNames.length).toBeGreaterThan(0), { timeout: 3000 });
        // any names that did land must be unique
        expect(new Set(savedNames).size).toBe(savedNames.length);
        expect(savedNames.some(n => n !== 'new1' && n !== 'new2')).toBe(false);
    });

    it('AC-3: + picks new2 when new1 already exists', async () => {
        const user = userEvent.setup();
        profileMap = { ...PROFILES, new1: makeProfile({ target_odds: 2 }) };
        let savedName = '';
        server.use(
            http.post('/api/profiles', async ({ request }) => {
                const body = await request.json() as Record<string, unknown>;
                savedName = String(body.name);
                profileMap[savedName] = body as unknown as ReturnType<typeof makeProfile>;
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: '+' }));
        await waitFor(() => expect(savedName).toBe('new2'), { timeout: 3000 });
        expect(await screen.findByText(/Profile 'new2' saved/, {}, { timeout: 3000 })).toBeInTheDocument();
    });

    // ── AC-4: sizing moved out of the header into the modal ────────────────

    it('AC-4: Units/Target Payout are NOT in the top header', async () => {
        await renderAndHydrate();
        // Header labels existed above the preview before this story; the
        // modal renders them (asserted separately) — here they must be absent
        // while no modal is open.
        expect(screen.queryByText('Units')).not.toBeInTheDocument();
        expect(screen.queryByText('Target Payout')).not.toBeInTheDocument();
    });

    it('Save still POSTs the active profile', async () => {
        const user = userEvent.setup();
        let saved = 0;
        server.use(
            http.post('/api/profiles', async ({ request }) => {
                const body = await request.json() as Record<string, unknown>;
                saved += 1;
                profileMap[String(body.name)] = body as unknown as ReturnType<typeof makeProfile>;
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await user.click(screen.getByRole('button', { name: 'Save', exact: true }));
        expect(await screen.findByText(/Profile 'bold' saved/, {}, { timeout: 3000 })).toBeInTheDocument();
        expect(saved).toBe(1);
    });

    // ── AC-5/6/7: Add to Slips confirmation modal ──────────────────────────

    it('AC-5: + Add to Slips opens the confirmation modal with Units + Target Payout', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const dialog = await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 });
        expect(within(dialog).getByText('Units')).toBeInTheDocument();
        expect(within(dialog).getByText('Target Payout')).toBeInTheDocument();
        expect(within(dialog).getByRole('button', { name: 'Add to Slips' })).toBeInTheDocument();
    });

    it('AC-6: confirm POSTs the slip and closes the modal', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        await user.click(await screen.findByRole('button', { name: 'Add to Slips' }, { timeout: 3000 }));
        await waitFor(() => expect(slipPosts).toBe(1), { timeout: 3000 });
        expect(await screen.findByText(/Slip #7 added/, {}, { timeout: 3000 })).toBeInTheDocument();
        expect(screen.queryByRole('dialog', { name: 'Add to Slips' })).not.toBeInTheDocument();
    });

    it('AC-7: Escape closes the modal without posting', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        expect(await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 })).toBeInTheDocument();
        await user.keyboard('{Escape}');
        await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Add to Slips' })).not.toBeInTheDocument());
        expect(slipPosts).toBe(0);
    });

    it('AC-7: Cancel closes the modal without posting', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const dialog = await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 });
        await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
        await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Add to Slips' })).not.toBeInTheDocument());
        expect(slipPosts).toBe(0);
    });

    it('AC-5: Target Payout in the modal computes units from total odds', async () => {
        const user = userEvent.setup();
        server.use(
            http.post('/api/builder/preview', async () => {
                previewCalls += 1;
                return HttpResponse.json({ legs: [makeCandidateLeg()], total_odds: 2.5, pending_urls: [] });
            }),
        );
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const dialog = await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 });
        const payoutInput = within(dialog).getByPlaceholderText('Off');
        await user.clear(payoutInput);
        await user.type(payoutInput, '25');
        // 25 / 2.5 = 10 units — the modal shows the computed readout
        await waitFor(() => {
            expect(within(dialog).getByText('→ 10u')).toBeInTheDocument();
        }, { timeout: 3000 });
    });

    it('empty preview hides + Add to Slips entirely', async () => {
        server.use(
            http.post('/api/builder/preview', async () => {
                previewCalls += 1;
                return HttpResponse.json({ legs: [], total_odds: 1, pending_urls: [] });
            }),
        );
        renderBuilder();
        await waitFor(() => expect(previewCalls).toBeGreaterThan(0), { timeout: 4000 });
        expect(screen.getByText('No preview yet')).toBeInTheDocument();
        expect(screen.queryByText('+ Add to Slips')).not.toBeInTheDocument();
    });

    // ── kept pins: excluded cards ───────────────────────────────────────────

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
        const initial = renderBuilder();
        await waitFor(() => expect(previewCalls).toBeGreaterThan(0), { timeout: 4000 });
        const before = previewCalls;
        initial.rerender(
            <MemoryRouter>
                <SmartBuilder filters={{ dateFrom: '2026-09-25', dateTo: '' }} refreshKey={1} />
            </MemoryRouter>,
        );
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });
        await waitFor(() => expect(lastPreviewBody).toContain('2026-09-25'), { timeout: 3000 });
    });

    it('localStorage payload carries no removed keys (runDaily gone)', async () => {
        await renderAndHydrate();
        const parsed = JSON.parse(localStorage.getItem('smart_builder_state') as string);
        expect(parsed.runDaily).toBeUndefined();
    });
});