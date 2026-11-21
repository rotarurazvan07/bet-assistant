// SmartBuilder page — profile-cards rework contract:
//    heading reads 'Profiles' (active profile shown by the card highlight)
//    first profile is selected by default (no 'manual' state)
//    config changes AUTO-SAVE to the active profile (no Save button)
//    deleting the active profile re-selects the first remaining one
//    Add-to-Slips modal: Units / Target Payout are mutually exclusive
//         with cross calculated previews, 0.1 steps, blocking behaviour
// Existing pins kept: 350ms debounce, localStorage payload, excluded cards,
// refreshKey, real timers.

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

function renderBuilder(refreshKey = 0) {
    return render(
        <MemoryRouter>
            <SmartBuilder refreshKey={refreshKey} />
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

    // ──/heading, active indicator, default selection ─────────────

    it('heading reads Profiles with no active-name indicator text', async () => {
        await renderAndHydrate();
        expect(screen.getByRole('heading', { name: 'Profiles' })).toBeInTheDocument();
        expect(screen.queryByText(/^Profiles: .* active$/)).not.toBeInTheDocument();
    });

    it('the first profile is selected by default (no manual state)', async () => {
        await renderAndHydrate();
        expect(screen.getByRole('button', { name: 'cautious' })).toHaveAttribute('aria-pressed', 'true');
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'false');
    });

    it('clicking a card loads its config into the builder', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = previewCalls;
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });
        expect(lastPreviewBody).toContain('"target_odds":8');
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('header no longer carries Reset excluded or Run Daily', async () => {
        await renderAndHydrate();
        expect(screen.queryByText('Reset excluded')).not.toBeInTheDocument();
        expect(screen.queryByText('Run Daily')).not.toBeInTheDocument();
    });

    // ──per-card delete re-selects the first remaining profile ────────

    it('deleting the ACTIVE profile re-selects the first remaining one', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        expect(screen.getByRole('button', { name: 'cautious' })).toHaveAttribute('aria-pressed', 'true')
        await user.click(screen.getByRole('button', { name: /Delete profile 'cautious'/ }));
        await waitFor(() => expect(deleted).toEqual(['cautious']), { timeout: 3000 });
        expect(await screen.findByText("Deleted 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'cautious' })).not.toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('X on a NON-active profile deletes it and keeps the active one', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await user.click(screen.getByRole('button', { name: /Delete profile 'cautious'/ }));
        await waitFor(() => expect(deleted).toEqual(['cautious']), { timeout: 3000 });
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
        expect(await screen.findByText("Deleted 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
    });

    // ──inline rename: POST(new full payload) + DELETE(old) ───────────

    it('renaming posts the full payload under the new name and deletes the old key', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'backup{Enter}');
        await waitFor(() => expect(deleted).toEqual(['bold']), { timeout: 3000 });
        const posted = savedPosts.find(p => p.name === 'backup');
        expect(posted).toBeDefined();
        expect(posted!.units).toBe(3); // preserved: bold's Services-owned stake
        expect(posted!.order).toBe(2); // preserved: ordering must survive the key move
        expect(await screen.findByText("Renamed 'bold' to 'backup'", {}, { timeout: 3000 })).toBeInTheDocument();
        await waitFor(() => expect(screen.queryByRole('button', { name: 'bold' })).not.toBeInTheDocument(), { timeout: 3000 });
        expect(screen.getByRole('button', { name: 'backup' })).toBeInTheDocument();
    });

    it('renaming to an existing name makes no request and reports the conflict', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const postsBefore = savedPosts.length;
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'cautious{Enter}');
        expect(await screen.findByText("Profile 'cautious' already exists")).toBeInTheDocument();
        await new Promise(r => setTimeout(r, 800));
        expect(savedPosts.length).toBe(postsBefore);
        expect(deleted).toEqual([]);
    });

    it('renaming to an empty/whitespace name makes no request', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const postsBefore = savedPosts.length;
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, '   {Enter}');
        expect(await screen.findByText('Profile name must contain letters or digits')).toBeInTheDocument();
        await new Promise(r => setTimeout(r, 800));
        expect(savedPosts.length).toBe(postsBefore);
        expect(deleted).toEqual([]);
    });

    it('Escape cancels rename mode without a request', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const postsBefore = savedPosts.length;
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'backup{Escape}');
        await waitFor(() => expect(screen.queryByLabelText("Profile name for 'bold'")).not.toBeInTheDocument());
        expect(screen.getByRole('button', { name: 'bold' })).toBeInTheDocument();
        expect(savedPosts.length).toBe(postsBefore);
        expect(deleted).toEqual([]);
    });

    it('renaming the ACTIVE profile keeps it selected under the new name', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        // 'cautious' is active by default (order 1)
        await user.click(screen.getByRole('button', { name: /Rename profile 'cautious'/ }));
        const input = await screen.findByLabelText("Profile name for 'cautious'");
        await user.clear(input);
        await user.type(input, 'daily{Enter}');
        await waitFor(() => expect(deleted).toEqual(['cautious']), { timeout: 3000 });
        const renamedCard = await screen.findByRole('button', { name: 'daily' }, { timeout: 3000 });
        expect(renamedCard).toHaveAttribute('aria-pressed', 'true');
        const stored = JSON.parse(localStorage.getItem('smart_builder_state')!);
        expect(stored.activeName).toBe('daily');
    });

    it('rename sanitizes like the backend: "My Profile!" becomes "myprofile"', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'My Profile!{Enter}');
        await waitFor(() => expect(deleted).toEqual(['bold']), { timeout: 3000 });
        expect(savedPosts.some(p => p.name === 'myprofile')).toBe(true);
        await waitFor(
            () => expect(screen.getByRole('button', { name: 'myprofile' })).toBeInTheDocument(),
            { timeout: 3000 },
        );
    });

    it('a duplicate rename reports the sanitized target when the draft differs', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const postsBefore = savedPosts.length;
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'Cautious!{Enter}');
        expect(await screen.findByText(/Profile 'cautious' already exists \(from 'Cautious!'\)/)).toBeInTheDocument();
        await new Promise(r => setTimeout(r, 600));
        expect(savedPosts.length).toBe(postsBefore);
        expect(deleted).toEqual([]);
    });

    it('a prototype-key draft is not treated as an existing profile', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'constructor{Enter}');
        // Blind Hunter #2: 'constructor' in profiles is true via the prototype
        // chain — the guard must be an own-property check.
        await waitFor(() => expect(deleted).toEqual(['bold']), { timeout: 3000 });
        expect(savedPosts.some(p => p.name === 'constructor')).toBe(true);
    });

    it('a failing old-key delete rolls back the new profile and resyncs the list', async () => {
        const user = userEvent.setup();
        // Blind Hunter #1 / Edge Hunter #1: POST succeeds but DELETE fails —
        // the catch path must delete the just-created profile and refetch.
        server.use(
            http.delete('/api/profiles/bold', () => HttpResponse.json({ detail: 'boom' }, { status: 500 })),
        );
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'renametarget{Enter}');
        expect(await screen.findByText(/Rename failed/)).toBeInTheDocument();
        // rollback POST'd 'renametarget' then deleted 'renametarget' again
        expect(deleted).toEqual(['renametarget']);
        expect(screen.getByRole('button', { name: 'bold' })).toBeInTheDocument();
    });

    it('a null resync response does not wipe the profile list', async () => {
        const user = userEvent.setup();
        // Blind Hunter #4: the resync fetch can resolve undefined — the list
        // must survive instead of collapsing to zero cards.
        // Registered after hydration so only the post-rename refetch is broken.
        await renderAndHydrate();
        server.use(
            http.get('/api/profiles', () => new HttpResponse(null, { status: 200 })),
        );
        await user.click(screen.getByRole('button', { name: /Rename profile 'bold'/ }));
        const input = await screen.findByLabelText("Profile name for 'bold'");
        await user.clear(input);
        await user.type(input, 'rolledback{Enter}');
        // The rename completes (POST+DELETE succeed) but the refetch returns
        // null; our guard keeps the current list instead of clearing it.
        // The list still shows at least one profile card (not empty).
        await waitFor(() => expect(deleted).toEqual(['bold']), { timeout: 3000 });
        expect(screen.getByRole('button', { name: 'cautious' })).toBeInTheDocument();
        // The old 'bold' card remains in the stale list; new name not shown.
        expect(screen.getByRole('button', { name: 'bold' })).toBeInTheDocument();
    });

    // ──auto-save replaces the Save button ────────────────────────────

    it('there is no Save button — config changes auto-save to the profile', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
        const before = savedPosts.length;
        const oddsInput = screen.getAllByDisplayValue('4')[0];
        await user.clear(oddsInput);
        await user.type(oddsInput, '6');
        await waitFor(() => expect(savedPosts.length).toBeGreaterThan(before), { timeout: 4000 });
        expect(savedPosts[savedPosts.length - 1].name).toBe('cautious');
        expect(await screen.findByText("Saved to 'cautious'", {}, { timeout: 3000 })).toBeInTheDocument();
    });

    it('switching a profile does not re-save the previous config', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = savedPosts.length;
        await user.click(screen.getByRole('button', { name: 'bold' }));
        await new Promise(r => setTimeout(r, 900));
        expect(savedPosts.length).toBe(before);
    });

    // ──: stake fields are Services-owned ──────────────────────────

    it('config auto-save payload omits units/target_payout (Services-owned)', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        const before = savedPosts.length;
        const oddsInput = screen.getAllByDisplayValue('4')[0];
        await user.clear(oddsInput);
        await user.type(oddsInput, '6');
        await waitFor(() => expect(savedPosts.length).toBeGreaterThan(before), { timeout: 4000 });
        const body = savedPosts[savedPosts.length - 1];
        expect(body.name).toBe('cautious');
        expect(body).not.toHaveProperty('units');
        expect(body).not.toHaveProperty('target_payout');
    });

    it('Add-to-Slips modal stake entry never persists to the profile', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const unitsInput = await screen.findByLabelText('Units');
        await user.clear(unitsInput);
        await user.type(unitsInput, '5');
        await user.click(screen.getByRole('button', { name: 'Add to Slips' }));
        await waitFor(() => expect(slipPosts).toBe(1), { timeout: 3000 });
        await new Promise(r => setTimeout(r, 900));
        expect(savedPosts.length).toBe(0);
    });

    it('mount hydrates cfg/units from disk when the persisted selection still exists', async () => {
        localStorage.setItem('smart_builder_state', JSON.stringify({
            cfg: { target_odds: 99 },
            activeName: 'bold',
            units: 9.9,
            targetPayout: 9.9,
        }));
        await renderAndHydrate();
        expect(screen.getByRole('button', { name: 'bold' })).toHaveAttribute('aria-pressed', 'true');
        const saved = JSON.parse(localStorage.getItem('smart_builder_state')!);
        expect(saved.units).toBe(3);
        expect(saved.targetPayout).toBe(0);
        expect(saved.cfg.target_odds).toBe(8);
    });

    it('mount survives a corrupt localStorage payload (defaults, no crash)', async () => {
        localStorage.setItem('smart_builder_state', '{not valid json');
        await renderAndHydrate();
        // No crash: the page renders profile cards and the writer effect
        // repairs storage into a valid payload with a selected profile.
        expect(screen.getByTestId('profile-cards')).toBeInTheDocument();
        const saved = JSON.parse(localStorage.getItem('smart_builder_state')!);
        expect(saved.cfg).toBeTruthy();
        expect(typeof saved.activeName).toBe('string');
        expect(saved.activeName.length).toBeGreaterThan(0);
    });

    // ── '+' creates new{N} from the current config ──────────────────────────

    it('+ saves the current cfg as new1 and selects it', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(screen.getByRole('button', { name: 'Create new profile' }));
        await waitFor(() => expect(savedPosts.some(p => p.name === 'new1')).toBe(true), { timeout: 3000 });
        const card = await screen.findByRole('button', { name: 'new1' }, { timeout: 3000 });
        expect(card).toHaveAttribute('aria-pressed', 'true');
        expect(await screen.findByText("Saved to 'new1'", {}, { timeout: 3000 })).toBeInTheDocument();
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

    // ──Add-to-Slips confirmation modal — mutual exclusivity ──────────

    it('+ Add to Slips opens the modal with BOTH inputs empty (no Off placeholder)', async () => {
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

    it('confirm POSTs the slip and closes the modal', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        await user.click(await screen.findByRole('button', { name: 'Add to Slips' }, { timeout: 3000 }));
        await waitFor(() => expect(slipPosts).toBe(1), { timeout: 3000 });
        expect(await screen.findByText(/Slip #7 added/, {}, { timeout: 3000 })).toBeInTheDocument();
        expect(screen.queryByRole('dialog', { name: 'Add to Slips' })).not.toBeInTheDocument();
    });

    it('Escape closes the modal without posting', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        expect(await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 })).toBeInTheDocument();
        await user.keyboard('{Escape}');
        await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Add to Slips' })).not.toBeInTheDocument());
        expect(slipPosts).toBe(0);
    });

    it('Cancel closes the modal without posting', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const dialog = await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 });
        await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
        await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Add to Slips' })).not.toBeInTheDocument());
        expect(slipPosts).toBe(0);
    });

    it('both inputs use 0.1 steps', async () => {
        const user = userEvent.setup();
        await renderAndHydrate();
        await user.click(await screen.findByText('+ Add to Slips', {}, { timeout: 4000 }));
        const dialog = await screen.findByRole('dialog', { name: 'Add to Slips' }, { timeout: 3000 });
        expect(within(dialog).getByLabelText('Units')).toHaveAttribute('step', '0.1');
        expect(within(dialog).getByLabelText('Target Payout')).toHaveAttribute('step', '0.1');
    });

    it('writing Target Payout disables Units and previews computed units', async () => {
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

    it('writing Units disables Target Payout and previews computed payout', async () => {
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

    it('local date range filters previews and refreshKey triggers a fresh preview', async () => {
        const user = userEvent.setup();
        const initial = renderBuilder();
        await waitFor(() => expect(previewCalls).toBeGreaterThan(0), { timeout: 4000 });
        const before = previewCalls;
        initial.rerender(
            <MemoryRouter>
                <SmartBuilder refreshKey={1} />
            </MemoryRouter>,
        );
        await waitFor(() => expect(previewCalls).toBeGreaterThan(before), { timeout: 4000 });

        await user.type(screen.getByLabelText('Date from'), '2026-09-25');
        await waitFor(() => expect(lastPreviewBody).toContain('2026-09-25'), { timeout: 3000 });
        expect(localStorage.getItem('bet-assistant-builder-date-range')).toContain('2026-09-25');
    });

    it('localStorage payload carries no removed keys (runDaily gone)', async () => {
        await renderAndHydrate();
        const parsed = JSON.parse(localStorage.getItem('smart_builder_state') as string);
        expect(parsed.runDaily).toBeUndefined();
    });
});
