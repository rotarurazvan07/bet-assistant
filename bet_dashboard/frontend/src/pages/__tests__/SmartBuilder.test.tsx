// SmartBuilder page — profile-cards rework contract:
//   AC-1  heading reads 'Profiles' (active profile shown by the card highlight)
//   AC-2  first profile is selected by default (no 'manual' state)
//   AC-3  config changes AUTO-SAVE to the active profile (no Save button)
//   AC-4  deleting the active profile re-selects the first remaining one
//   AC-5  Add-to-Slips modal: Units / Target Payout are mutually exclusive
//         with cross calculated previews, 0.1 steps, blocking behaviour
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

// Order-robust shared stub: registering the IDENTICAL factory in every
// recharts-consuming file makes the run order-independent.
vi.mock('recharts', async () => (await import('../../test/recharts-stub')).rechartsStub);

// Distinct configs so tests can prove a card click actually LOADED a profile.
const PROFILES = {
    cautious: { ...makeProfile({ target_odds: 4, target_legs: 4, units: 2 }), order: 1 },
    bold: { ...makeProfile({ target_odds: 8, target_legs: 5, units: 3 }), order: 2 },
};

const PREVIEW = makePreviewResult();
let previewCalls = 0;
let lastPreviewBody = '';
let slipPosts = 0;
let deleted: string[] = [];
let savedPosts: Array<Record<string, unknown>> = [];
let profileMap: Record<string, ReturnType<typeof makeProfile>> = { ...PROFILES };

beforeEach(() => {
    localStorage.clear();
    previewCalls = 0;
    lastPreviewBody = '';
    slipPosts = 0;
    deleted = [];
    savedPosts = [];
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
            savedPosts.push(body);
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
        expect(screen.getByRole('heading', { name: 'Profiles' })).toBeInTheDocument();
    });

    it('uses saved profile order instead of relying on response object order', async () => {
        profileMap = { bold: PROFILES.bold, cautious: PROFILES.cautious };
        await renderAndHydrate();
        expect(screen.getByRole('button', { name: 'cautious' })).toHaveAttribute('aria-pressed', 'true');
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'false');
    });

    it('reports a failed profile fetch instead of hiding it as an empty profile list', async () => {
        server.use(
            http.get('/api/profiles', () => HttpResponse.json({ detail: 'settings unavailable' }, { status: 500 })),
        );
        await renderAndHydrate();
        expect(await screen.findByText(/Profiles could not be loaded/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'cautious' })).not.toBeInTheDocument();
    });

    it('config change triggers a NEW debounced preview (count increments)', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = previewCalls;
        const oddsInput = screen.getAllByDisplayValue('4')[0];
        await user.clear(oddsInput);
        await user.type(oddsInput, '5');
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });
    });

    it('config persists to localStorage with dates stripped', async () => {
        await renderAndHydrate();
        const saved = localStorage.getItem('smart_builder_state');
        expect(saved).not.toBeNull();
        const parsed = JSON.parse(saved as string);
        expect(parsed.cfg.target_odds).toBe(4);
        expect(parsed.cfg.date_from).toBeNull();
        expect(parsed.cfg.date_to).toBeNull();
        // first profile auto-selected, no 'manual'
        expect(parsed.activeName).toBe('cautious');
        expect(parsed.units).toBe(2);
    });

    // ── AC-1/AC-2: heading, active indicator, default selection ─────────────

    it('AC-1: heading reads Profiles with no active-name indicator text', async () => {
        await renderAndHydrate();
        expect(screen.getByRole('heading', { name: 'Profiles' })).toBeInTheDocument();
        expect(screen.queryByText(/^Profiles: .* active$/)).not.toBeInTheDocument();
    });

    it('AC-2: the first profile is selected by default (no manual state)', async () => {
        await renderAndHydrate();
        expect(screen.getByRole('button', { name: 'cautious' })).toHaveAttribute('aria-pressed', 'true');
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'false');
    });

    it('AC-1: clicking a card loads its config into the builder', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = previewCalls;
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });
        expect(lastPreviewBody).toContain('"target_odds":8');
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('AC-1: header no longer carries Reset excluded or Run Daily', async () => {
        await renderAndHydrate();
        expect(screen.queryByText('Reset excluded')).not.toBeInTheDocument();
        expect(screen.queryByText('Run Daily')).not.toBeInTheDocument();
    });

    // ── AC-4: per-card delete re-selects the first remaining profile ────────

    it('AC-4: deleting the ACTIVE profile re-selects the first remaining one', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        expect(screen.getByRole('button', { name: 'cautious' })).toHaveAttribute('aria-pressed', 'true')
        await user.click(screen.getByRole('button', { name: /Delete profile 'cautious'/ }));
        await waitFor(() => expect(deleted).toEqual(['cautious']), { timeout: 3000 });
        expect(await screen.findByText("Deleted 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'cautious' })).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('AC-4: X on a NON-active profile deletes it and keeps the active one', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await user.click(screen.getByRole('button', { name: /Delete profile 'cautious'/ }));
        await waitFor(() => expect(deleted).toEqual(['cautious']), { timeout: 3000 });
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
        expect(await screen.findByText("Deleted 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
    });

    // ── AC-3: auto-save replaces the Save button ────────────────────────────

    it('AC-3: there is no Save button — config changes auto-save to the profile', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
        const before = savedPosts.length;
        const oddsInput = screen.getAllByDisplayValue('4')[0];
        await user.clear(oddsInput);
        await user.type(oddsInput, '6');
        await waitFor(() => expect(savedPosts.length).toBeGreaterThan(before), { timeout: 4000 });
        expect(savedPosts[savedPosts.length - 1].name).toBe('cautious');
        expect(await screen.findByText("✓ Saved to 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
    });

    it('AC-3: switching a profile does not re-save the previous config', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = savedPosts.length;
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await new Promise(r => setTimeout(r, 900));
        expect(savedPosts.length).toBe(before);
    });

    // ── '+' creates new{N} from the current config ──────────────────────────

    it('+ saves the current cfg as new1 and selects it', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'Create new profile' }));
        await waitFor(() => expect(savedPosts.some(p => p.name === 'new1')).toBe(true), { timeout: 3000 });
        const card = await screen.findByRole('button', { name: 'new1' }, { timeout: 3000 });
        expect(card).toHaveAttribute('aria-pressed', 'true');
        expect(await screen.findByText("✓ Saved to 'new1'", {}, { timeout: 3000 })).toBeInTheDocument();
    });

    it('rapid double-click on + never creates a duplicate name', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.dblClick(screen.getByRole('button', { name: 'Create new profile' }));
        await waitFor(() => expect(savedPosts.length).toBeGreaterThan(0), { timeout: 3000 });
        const names = savedPosts.map(p => String(p.name));
        expect(new Set(names).size).toBe(names.length);
        expect(names.every(n => n === 'new1' || n === 'new2')).toBe(true);
    });

    it('+ picks new2 when new1 already exists', async () => {
        const user = userEvent.setup();
        profileMap = { ...PROFILES, new1: makeProfile({ target_odds: 2 }) };
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'Create new profile' }));
        await waitFor(() => expect(savedPosts.some(p => p.name === 'new2')).toBe(true), { timeout: 3000 });
    });

    // ── AC-5: Add-to-Slips confirmation modal — mutual exclusivity ──────────

    it('AC-5: + Add to Slips opens the modal with BOTH inputs empty (no Off placeholder)', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const dialog = await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 });
        expect(within(dialog).getByText('Target Payout')).toBeInTheDocument();
        expect(within(dialog).getByRole('button', { name: 'Add to Slips' })).toBeInTheDocument();
        expect((within(dialog).getByLabelText('Units') as HTMLInputElement).value).toBe('');
        expect((within(dialog).getByLabelText('Target Payout') as HTMLInputElement).value).toBe('');
        expect(within(dialog).getByLabelText('Units')).not.toBeDisabled();
        expect(within(dialog).getByLabelText('Target Payout')).not.toBeDisabled();
        expect(within(dialog).getByLabelText('Target Payout')).not.toHaveAttribute('placeholder');
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

    it('AC-5: both inputs use 0.1 steps', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const dialog = await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 });
        expect(within(dialog).getByLabelText('Units')).toHaveAttribute('step', '0.1');
        expect(within(dialog).getByLabelText('Target Payout')).toHaveAttribute('step', '0.1');
    });

    it('AC-5: writing Target Payout disables Units and previews computed units', async () => {
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
        const payoutInput = within(dialog).getByLabelText('Target Payout');
        await user.clear(payoutInput);
        await user.type(payoutInput, '25');
        // 25 / 2.5 = 10 units — computed into the now-disabled Units input
        await waitFor(() => {
            const unitsInput = within(dialog).getByLabelText('Units') as HTMLInputElement;
            expect(unitsInput.disabled).toBe(true);
            expect(Number(unitsInput.value)).toBe(10);
        }, { timeout: 3000 });
    });

    it('AC-5: writing Units disables Target Payout and previews computed payout', async () => {
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
        const unitsInput = within(dialog).getByLabelText('Units');
        await user.clear(unitsInput);
        await user.type(unitsInput, '4');
        // 4 × 2.5 = 10 payout — computed into the now-disabled Target Payout input
        await waitFor(() => {
            const payoutInput = within(dialog).getByLabelText('Target Payout') as HTMLInputElement;
            expect(payoutInput.disabled).toBe(true);
            expect(Number(payoutInput.value)).toBe(10);
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
