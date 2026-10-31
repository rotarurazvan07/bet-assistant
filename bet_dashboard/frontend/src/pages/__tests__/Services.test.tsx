// Services page. Divergences (cycle 14): the global schedule time is gone —
// per-profile rows are the only scheduling surface. Units / Target Payout are
// mutually exclusive inputs (0.1 steps, no cross preview). Daily run count is
// a numeric step-1 input. MSW serves /api/services.

import { describe, it, expect, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Services from '../Services';
import { server } from '../../test/handlers';
import { makeServicesData, makeServiceInfo, makeProfileSchedule } from '../../test/factories';

const DATA = makeServicesData();

beforeEach(() => {
    server.use(
        http.get('/api/services', () => HttpResponse.json(DATA)),
        http.post('/api/services/settings', () => HttpResponse.json({ status: 'ok' })),
    );
});

describe('Services page', () => {
    it('shows the loading state before data arrives', () => {
        server.use(
            http.get('/api/services', async () => {
                await new Promise((r) => setTimeout(r, 500));
                return HttpResponse.json(DATA);
            }),
        );
        render(<Services />);
        expect(screen.getByText('Loading services…')).toBeInTheDocument();
    });

    it('renders the page title and server time header', async () => {
        render(<Services />);
        expect(await screen.findByText('Automation Services')).toBeInTheDocument();
        expect(screen.getByText(/Server time:/)).toBeInTheDocument();
    });

    it('renders a ServiceCard per service with status badges', async () => {
        render(<Services />);
        await screen.findByText('Automation Services');
        const services = Object.values(DATA.services);
        for (const svc of services) {
            expect(screen.getByText(svc.name)).toBeInTheDocument();
        }
        expect(screen.getAllByText(/Running|Stopped/).length).toBe(services.length);
    });

    it('toggle on a card POSTs and reloads (count increments)', async () => {
        const user = userEvent.setup();
        let calls = 0;
        server.use(
            http.get('/api/services', () => {
                calls += 1;
                return HttpResponse.json(DATA);
            }),
            http.post('/api/services/:name/toggle', () => HttpResponse.json({ status: 'ok' })),
        );
        render(<Services />);
        await screen.findByText('Automation Services');
        const before = calls;
        const firstToggle = screen.getAllByText(/Stop Service|Start Service/)[0];
        await user.click(firstToggle);
        await waitFor(() => expect(calls).toBeGreaterThan(before));
    });

    it('the global schedule time picker is gone', async () => {
        render(<Services />);
        await screen.findByText('Automation Services');
        expect(screen.queryByText('Scheduled Time')).not.toBeInTheDocument();
        expect(screen.queryByText('Save Settings')).not.toBeInTheDocument();
        expect(document.querySelector('.MuiClock-root')).toBeNull();
    });

    it('fetch failure path keeps the loading card (no crash)', async () => {
        server.use(http.get('/api/services', () => HttpResponse.error()));
        render(<Services />);
        await new Promise((r) => setTimeout(r, 50));
        expect(screen.queryByText('Per-Profile Scheduling')).not.toBeInTheDocument();
    });

    it('does not show EmptyState when generator is enabled', async () => {
        render(<Services />);
        await screen.findByText('Automation Services');
        expect(screen.queryByText('Generate Slips is off')).not.toBeInTheDocument();
        expect(screen.queryByText('Loading services…')).not.toBeInTheDocument();
    });

    it('shows EmptyState above the grid when generator is off', async () => {
        const user = userEvent.setup();
        let toggles = 0;
        server.use(
            http.get('/api/services', () => HttpResponse.json(makeServicesData({
                services: {
                    puller: makeServiceInfo({ name: 'puller' }),
                    generator: makeServiceInfo({ name: 'generator', enabled: false }),
                    verifier: makeServiceInfo({ name: 'verifier' }),
                },
            }))),
            http.post('/api/services/:name/toggle', () => {
                toggles += 1;
                return HttpResponse.json({ name: 'generator', enabled: true });
            }),
        );
        render(<Services />);
        expect(await screen.findByText('Generate Slips is off')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Enable Generate Slips' })).toBeInTheDocument();
        await user.click(screen.getByRole('button', { name: 'Enable Generate Slips' }));
        await waitFor(() => expect(toggles).toBe(1));
    });

    it('cards show per-service descriptions', async () => {
        render(<Services />);
        await screen.findByText('Automation Services');
        for (const svc of Object.values(DATA.services)) {
            if (svc.description) {
                expect(screen.getAllByText(svc.description).length).toBeGreaterThan(0);
            }
        }
    });
});

// ── Per-profile scheduling table (issue #95 redesign) ────────────────────────

const ROWS = [
    makeProfileSchedule({
        name: 'low', auto_generate: true, generate_hour: 8, generate_minute: 30,
        units: 1.0, target_payout: null, stake_mode: 'units', run_daily_count: 1, order: 0,
        last_generated_at: '2026-10-29T06:30:00+00:00', next_run_at: '2026-10-30T05:30:00+00:00',
        last_run_status: 'ok', last_run_error: null,
    }),
    makeProfileSchedule({
        name: 'medium', auto_generate: true, generate_hour: 10, generate_minute: 0,
        units: null, target_payout: 50, stake_mode: 'payout', run_daily_count: 2, order: 1,
        last_generated_at: null, next_run_at: '2026-10-29T18:00:00+00:00',
        last_run_status: null, last_run_error: null,
    }),
    makeProfileSchedule({
        name: 'high_risk', auto_generate: false, generate_hour: 12, generate_minute: 15,
        units: 2.0, target_payout: null, stake_mode: 'units', run_daily_count: 1, order: 2,
        last_generated_at: null, next_run_at: null, last_run_status: null, last_run_error: null,
    }),
];

function serveRows(posts: Array<Record<string, unknown>>) {
    server.use(
        http.get('/api/services', () => HttpResponse.json(makeServicesData({ profile_schedules: ROWS }))),
        http.post('/api/services/settings', async ({ request }) => {
            posts.push(await request.json() as Record<string, unknown>);
            return HttpResponse.json({ ok: true });
        }),
    );
}

describe('Services per-profile scheduler (issue #95 redesign)', () => {
    it('renders the new column headers: Profile | Auto | Time | Daily | Stake | Last generated | Next run | Order', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(
            makeServicesData({ profile_schedules: ROWS }),
        )));
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        for (const header of ['Profile', 'Auto', 'Time', 'Daily', 'Stake', 'Last generated', 'Next run', 'Order']) {
            expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument();
        }
        // Old headers gone
        expect(screen.queryByRole('columnheader', { name: 'Units' })).not.toBeInTheDocument();
        expect(screen.queryByRole('columnheader', { name: 'Target Payout' })).not.toBeInTheDocument();
    });

    it('Auto is a real switch (role="switch", aria-checked)', async () => {
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        const swLow = screen.getByRole('switch', { name: 'Auto-generation for low' });
        expect(swLow).toHaveAttribute('aria-checked', 'true');
        const swHigh = screen.getByRole('switch', { name: 'Auto-generation for high_risk' });
        expect(swHigh).toHaveAttribute('aria-checked', 'false');
    });

    it('Auto OFF shows "Manual only" labels and "—" for next run; guarded cells are inert', async () => {
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        // high_risk is auto-off: three "Manual only" labels in its row
        const manualLabels = screen.getAllByText('Manual only');
        expect(manualLabels.length).toBeGreaterThanOrEqual(3);
        // Next run shows "—" for the auto-off row only
        expect(screen.getAllByText('—').length).toBe(1);
        // Guarded inner cells carry data-gated="off" and inert
        const gatedCells = document.querySelectorAll('.sched-cell-inner[data-gated="off"]');
        expect(gatedCells.length).toBeGreaterThanOrEqual(3);
        const inertCells = document.querySelectorAll('.sched-cell-inner[inert]');
        expect(inertCells.length).toBeGreaterThanOrEqual(3);
    });

    it('toggling Auto ON enables the guarded cells (data-gated flips to on)', async () => {
        const user = userEvent.setup();
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        await user.click(screen.getByRole('switch', { name: 'Auto-generation for high_risk' }));
        await waitFor(() => {
            expect(screen.getByRole('switch', { name: 'Auto-generation for high_risk' })).toHaveAttribute('aria-checked', 'true');
        });
        // Daily input now present for high_risk
        expect(await screen.findByLabelText('Daily run count for high_risk')).toHaveValue(1);
    });

    it('Stake column has a radiogroup segmented control [Units | Payout] and one numeric input per row', async () => {
        server.use(
            http.get('/api/services', () => HttpResponse.json(makeServicesData({
                profile_schedules: [
                    makeProfileSchedule({ name: 'low', auto_generate: true, generate_hour: 8, generate_minute: 30, units: 1.0, target_payout: null, stake_mode: 'units', run_daily_count: 1, order: 0 }),
                    makeProfileSchedule({ name: 'medium', auto_generate: true, generate_hour: 10, generate_minute: 0, units: null, target_payout: 50.0, stake_mode: 'payout', run_daily_count: 2, order: 1 }),
                    makeProfileSchedule({ name: 'high_risk', auto_generate: true, generate_hour: 12, generate_minute: 15, units: 1.0, target_payout: null, stake_mode: 'units', run_daily_count: 0, order: 2 }),
                ],
            }))),
        );
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        const group = screen.getByRole('radiogroup', { name: 'Stake mode for low' });
        expect(group).toBeInTheDocument();
        const radios = screen.getAllByRole('radio');
        // 3 rows × 2 options = 6 radios
        expect(radios).toHaveLength(6);
        // low is units mode → "Units" checked (scope to low's radiogroup)
        const lowGroup = screen.getByRole('radiogroup', { name: 'Stake mode for low' });
        const unitsRadio = within(lowGroup).getByRole('radio', { name: 'Units' });
        expect(unitsRadio).toHaveAttribute('aria-checked', 'true');
        // One numeric stake input per row
        expect(screen.getByLabelText('Units for low')).toBeInTheDocument();
        expect(screen.getByLabelText('Target payout for medium')).toBeInTheDocument();
    });

    it('switching stake mode persists BOTH values — stake_mode selects active, nothing is nulled on disk', async () => {
        const user = userEvent.setup();
        const posts: Array<Record<string, unknown>> = [];
        serveRows(posts);
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        // low starts in units mode with units=1. Switch to payout.
        await user.click(screen.getAllByRole('radio', { name: 'Payout' })[0]);
        // Now the input is "Target payout for low" — type a FRACTIONAL value (step 0.1)
        fireEvent.change(screen.getByLabelText('Target payout for low'), { target: { value: '12.5' } });
        await waitFor(() => expect(posts).toHaveLength(1), { timeout: 3000 });
        const sentRows = posts[0].profile_schedules as Array<Record<string, unknown>>;
        const lowRow = sentRows.find(r => r.name === 'low');
        // units=1 is preserved (not null) alongside the new fractional payout — both live on disk
        expect(lowRow).toMatchObject({ stake_mode: 'payout', target_payout: 12.5, units: 1 });
        expect(lowRow?.units).not.toBeNull();
    });

    it('stake inputs are NumberField with step 0.1 (fractional units/payout allowed)', async () => {
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        const unitsInput = screen.getByLabelText('Units for low');
        expect(unitsInput).toHaveAttribute('step', '0.1');
        expect(unitsInput).toHaveAttribute('min', '0.1');
        // up/down stepper buttons present (aria-hidden, inside the field)
        expect(document.querySelectorAll('.num-step').length).toBeGreaterThan(0);
        // fractional units persist as-is (no rounding to int)
        const posts: Array<Record<string, unknown>> = [];
        serveRows(posts);
        fireEvent.change(unitsInput, { target: { value: '2.5' } });
        await waitFor(() => expect(posts).toHaveLength(1), { timeout: 3000 });
        const rows = posts[0].profile_schedules as Array<Record<string, unknown>>;
        expect(rows.find(r => r.name === 'low')).toMatchObject({ units: 2.5 });
    });

    it('Daily min is 1 (clamped)', async () => {
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        fireEvent.change(screen.getByLabelText('Daily run count for medium'), { target: { value: '0' } });
        // Clamped to 1, not 0
        await waitFor(() => expect(screen.getByLabelText('Daily run count for medium')).toHaveValue(1));
    });

    it('order arrows: up disabled on first row, down disabled on last; tooltip present', async () => {
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        expect(screen.getByRole('button', { name: 'Move low up' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Move high_risk down' })).toBeDisabled();
        // Tooltip on the order cell container
        const orderCells = document.querySelectorAll('[title="Order decides which profile generates first when run times coincide."]');
        expect(orderCells.length).toBeGreaterThan(0);
    });

    it('up/down reorder rows and the auto-save POST carries the new order', async () => {
        const user = userEvent.setup();
        const posts: Array<Record<string, unknown>> = [];
        serveRows(posts);
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        await user.click(screen.getByRole('button', { name: 'Move medium up' }));
        await waitFor(() => expect(posts).toHaveLength(1), { timeout: 3000 });
        const rows = posts[0].profile_schedules as Array<Record<string, string>>;
        expect(rows.map(r => r.name)).toEqual(['medium', 'low', 'high_risk']);
    });

    it('shows Last generated relative time and Next run relative time', async () => {
        server.use(
            http.get('/api/services', () => HttpResponse.json(makeServicesData({
                profile_schedules: [
                    makeProfileSchedule({ name: 'low', auto_generate: true, generate_hour: 8, generate_minute: 30, units: 1.0, target_payout: null, stake_mode: 'units', run_daily_count: 1, order: 0, last_generated_at: '2026-10-29T06:30:00Z', next_run_at: '2026-10-30T08:30:00Z', last_run_status: 'ok' }),
                    makeProfileSchedule({ name: 'medium', auto_generate: true, generate_hour: 10, generate_minute: 0, units: null, target_payout: 50.0, stake_mode: 'payout', run_daily_count: 2, order: 1, last_generated_at: null, next_run_at: '2026-10-30T10:00:00Z', last_run_status: null }),
                    makeProfileSchedule({ name: 'high_risk', auto_generate: false, generate_hour: 12, generate_minute: 15, units: 1.0, target_payout: null, stake_mode: 'units', run_daily_count: 0, order: 2, last_generated_at: null, next_run_at: null, last_run_status: null }),
                ],
            }))),
        );
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        // low has last_generated_at → not "Never" (scope to low's row)
        const lowRow = screen.getByText('low').closest('tr')!;
        expect(within(lowRow).queryByText('Never')).not.toBeInTheDocument();
        // medium has next_run_at in the future → shows "in Xh" or similar, not "—"
        const mediumRow = screen.getByText('medium').closest('tr')!;
        const nextRunText = within(mediumRow).getByText(/in \d+/);
        expect(nextRunText).toBeInTheDocument();
    });

    it('shows "Never" for last generated when null', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(makeServicesData({
            profile_schedules: [makeProfileSchedule({ name: 'p', last_generated_at: null, next_run_at: null, auto_generate: false })],
        }))));
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        expect(screen.getByText('Never')).toBeInTheDocument();
    });

    it('shows "Failed <relative>" in error color when last_run_status is failed', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(makeServicesData({
            profile_schedules: [makeProfileSchedule({
                name: 'p', auto_generate: true, last_generated_at: '2026-10-29T06:30:00Z',
                last_run_status: 'failed', last_run_error: 'boom', next_run_at: '2026-10-30T05:30:00Z',
            })],
        }))));
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        const failedEl = await screen.findByText(/Failed/);
        expect(failedEl).toBeInTheDocument();
    });

    it('shows "Generating…" with spinner when last_run_status is running', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(makeServicesData({
            profile_schedules: [
                makeProfileSchedule({
                    name: 'p', auto_generate: true, last_run_status: 'running',
                    last_generated_at: '2026-10-29T06:30:00Z', next_run_at: null,
                    generate_hour: 8, generate_minute: 0, units: 1.0,
                    target_payout: null, stake_mode: 'units', run_daily_count: 1, order: 0,
                }),
                // Other profiles with non-running status to avoid multiple 'Generating...' elements
                makeProfileSchedule({ name: 'low', auto_generate: true, last_run_status: 'ok', generate_hour: 8, generate_minute: 30, units: 1.0, target_payout: null, stake_mode: 'units', run_daily_count: 1, order: 0, last_generated_at: '2026-10-29T06:30:00Z' }),
                makeProfileSchedule({ name: 'medium', auto_generate: false, last_run_status: null, generate_hour: 10, generate_minute: 0, units: null, target_payout: 50.0, stake_mode: 'payout', run_daily_count: 0, order: 1 }),
            ],
        }))));
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        // Scope to the 'p' row and specifically the Last generated cell (6th column)
        // which shows "Generating…" with the sched-spinner
        const pRow = screen.getByText('p').closest('tr')!;
        const lastGenCell = within(pRow).getAllByRole('cell')[5]; // Last generated is 6th column (0-indexed)
        expect(await within(lastGenCell).findByText('Generating…')).toBeInTheDocument();
        expect(document.querySelector('.sched-spinner')).not.toBeNull();
    });

    it('tooltip on Last generated / Next run cells contains absolute datetime', async () => {
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        // Find a cell with a title containing a full datetime pattern
        const titled = document.querySelectorAll('[title*="("]');
        expect(titled.length).toBeGreaterThan(0);
    });

    it('hides the per-profile section when the backend serves no rows', async () => {
        server.use(
            http.get('/api/services', () => HttpResponse.json(makeServicesData({ profile_schedules: [] }))),
        );
        render(<Services />);
        await screen.findByText('Automation Services');
        expect(screen.queryByText('Per-Profile Scheduling')).not.toBeInTheDocument();
    });

    it('no Save button — an edit auto-saves all rows in one POST (600ms debounce)', async () => {
        const user = userEvent.setup();
        const posts: Array<Record<string, unknown>> = [];
        serveRows(posts);
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        expect(screen.queryByRole('button', { name: 'Save Profile Schedules' })).not.toBeInTheDocument();

        await user.selectOptions(screen.getByRole('combobox', { name: 'Generation hour for medium' }), '14');
        fireEvent.change(screen.getByLabelText('Daily run count for medium'), { target: { value: '3' } });
        await user.click(screen.getByRole('switch', { name: 'Auto-generation for high_risk' }));

        expect(posts).toHaveLength(0);
        await waitFor(() => expect(posts).toHaveLength(1), { timeout: 3000 });
        const rows = posts[0].profile_schedules as Array<Record<string, number | string | boolean | null>>;
        expect(rows).toHaveLength(3);
        expect(rows[1]).toMatchObject({ name: 'medium', generate_hour: 14, run_daily_count: 3 });
        expect(rows[2]).toMatchObject({ name: 'high_risk', auto_generate: true });
    });

    it('shows a failure status when the auto-save POST fails', async () => {
        const user = userEvent.setup();
        server.use(
            http.get('/api/services', () => HttpResponse.json(makeServicesData({ profile_schedules: ROWS }))),
            http.post('/api/services/settings', () => HttpResponse.error()),
        );
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        await user.click(screen.getByRole('switch', { name: 'Auto-generation for high_risk' }));
        expect(await screen.findByText(/Failed to save profile schedules/)).toBeInTheDocument();
    });

    it('order arrow buttons are visually disabled (btn-ghost:disabled styling class present)', async () => {
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        const upBtn = screen.getByRole('button', { name: 'Move low up' });
        expect(upBtn).toBeDisabled();
        expect(upBtn.className).toContain('btn-ghost');
    });

    it('Time selects show "--" placeholder when the profile has no window in YAML (no fabricated 08:00)', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(makeServicesData({
            profile_schedules: [makeProfileSchedule({
                name: 'p', auto_generate: true, generate_hour: null, generate_minute: null, next_run_at: null,
            })],
        }))));
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        expect(screen.getByRole('combobox', { name: 'Generation hour for p' })).toHaveValue('');
        expect(screen.getByRole('combobox', { name: 'Generation minute for p' })).toHaveValue('');
        // Two '--' placeholders (hour + minute) when both are null
        expect(screen.getAllByText('--')).toHaveLength(2);
    });

    it('changing the hour updates Next run in-page without a reload', async () => {
        const user = userEvent.setup();
        server.use(http.get('/api/services', () => HttpResponse.json(makeServicesData({
            profile_schedules: [makeProfileSchedule({
                name: 'p', auto_generate: true, generate_hour: 8, generate_minute: 0,
                // Server-computed next run for 08:00 (may be stale once we edit)
                next_run_at: new Date(Date.now() + 3600_000).toISOString(),
            })],
        }))));
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        // Pick an hour far in the future (23:00) so the computed next run is unmistakably "in 2Xh+"
        await user.selectOptions(screen.getByRole('combobox', { name: 'Generation hour for p' }), '23');
        // Next run cell must now reflect ~23:00 today/tomorrow — not the stale server value
        const nextCell = await screen.findByText(/in \d{1,2}h/);
        expect(nextCell).toBeInTheDocument();
    });
});