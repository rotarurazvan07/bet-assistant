// Services page. Divergences (cycle 14): the global schedule time is gone —
// per-profile rows are the only scheduling surface. Units / Target Payout are
// mutually exclusive inputs (0.1 steps, no cross preview). Daily run count is
// a numeric step-1 input. MSW serves /api/services.

import { describe, it, expect, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Services from '../Services';
import { server } from '../../test/handlers';
import { makeServicesData, makeServiceInfo } from '../../test/factories';

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

// ── Per-profile scheduling table ────────────────────────────────────────────

const ROWS = [
    { name: 'low', auto_generate: true, generate_hour: 8, generate_minute: 30, units: 1.0, target_payout: null, run_daily_count: 1, order: 0 },
    { name: 'medium', auto_generate: true, generate_hour: 10, generate_minute: 0, units: null, target_payout: 50, run_daily_count: 2, order: 1 },
    { name: 'high_risk', auto_generate: false, generate_hour: 12, generate_minute: 15, units: null, target_payout: null, run_daily_count: 0, order: 2 },
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

describe('Services per-profile scheduler', () => {
    it('renders one row per profile with column headers', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(
            makeServicesData({ profile_schedules: ROWS }),
        )));
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        for (const header of ['Profile', 'Time', 'Daily', 'Auto', 'Units', 'Target Payout', 'Order']) {
            expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument();
        }
        for (const row of ROWS) {
            expect(screen.getByTitle(row.name)).toBeInTheDocument();
            expect(screen.getByLabelText(`Generation hour for ${row.name}`)).toBeInTheDocument();
            expect(screen.getByLabelText(`Daily run count for ${row.name}`)).toBeInTheDocument();
        }
        // first row cannot move up; last row cannot move down
        expect(screen.getByRole('button', { name: 'Move low up' })).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Move high_risk down' })).toBeDisabled();
    });

    it('hides the per-profile section when the backend serves no rows', async () => {
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
        await user.click(screen.getByRole('button', { name: 'Enable auto-generation for high_risk' }));

        // debounced: no POST before the timer, then one POST with all rows
        expect(posts).toHaveLength(0);
        await waitFor(() => expect(posts).toHaveLength(1), { timeout: 3000 });
        const rows = posts[0].profile_schedules as Array<Record<string, number | string | boolean | null>>;
        expect(rows).toHaveLength(3);
        expect(rows[1]).toMatchObject({ name: 'medium', generate_hour: 14, run_daily_count: 3 });
        expect(rows[2]).toMatchObject({ name: 'high_risk', auto_generate: true });
        expect(posts[0].generate_hour).toBeUndefined();
    });

    it('units and target payout are mutually exclusive per row', async () => {
        serveRows([]);
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        // medium has target_payout → its Units input is disabled
        expect(screen.getByLabelText('Units for medium')).toBeDisabled();
        // low has units → its payout input is disabled
        expect(screen.getByLabelText('Target payout for low')).toBeDisabled();
        // high_risk has neither → both enabled
        expect(screen.getByLabelText('Units for high_risk')).not.toBeDisabled();
        expect(screen.getByLabelText('Target payout for high_risk')).not.toBeDisabled();
        // writing units on high_risk blocks its payout input
        fireEvent.change(screen.getByLabelText('Units for high_risk'), { target: { value: '2.5' } });
        await waitFor(() => expect(screen.getByLabelText('Target payout for high_risk')).toBeDisabled());
        // inputs use the right steps
        expect(screen.getByLabelText('Units for high_risk')).toHaveAttribute('step', '0.1');
        expect(screen.getByLabelText('Daily run count for low')).toHaveAttribute('step', '1');
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

    it('shows a failure status when the auto-save POST fails', async () => {
        const user = userEvent.setup();
        server.use(
            http.get('/api/services', () => HttpResponse.json(makeServicesData({ profile_schedules: ROWS }))),
            http.post('/api/services/settings', () => HttpResponse.error()),
        );
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        await user.click(screen.getByRole('button', { name: 'Enable auto-generation for high_risk' }));
        expect(await screen.findByText(/Failed to save profile schedules/)).toBeInTheDocument();
    });
});