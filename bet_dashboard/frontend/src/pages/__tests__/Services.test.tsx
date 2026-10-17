// Services page (issue #65). ACTUAL divergences (cycle 13): settings use a
// MUI StaticTimePicker (NOT spec's hour/minute number inputs); NO Pull DB
// button on this page (that is Layout's Pull Update, cycle-12 tested);
// status line confirms save. MSW serves /api/services.

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
        // active (alive && enabled) card shows Running
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

    it('Save Settings POSTs and shows the confirmation status', async () => {
        const user = userEvent.setup();
        let saved = 0;
        server.use(
            http.post('/api/services/settings', () => {
                saved += 1;
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        render(<Services />);
        await screen.findByText('Automation Services');
        await user.click(screen.getByText('Save Settings'));
        expect(await screen.findByText(/Settings saved/)).toBeInTheDocument();
        expect(saved).toBe(1);
    });

    it('renders the MUI StaticTimePicker scheduler panel (divergence: no hour/minute inputs)', async () => {
        render(<Services />);
        await screen.findByText('Automation Services');
        expect(screen.getByText('Scheduled Time')).toBeInTheDocument();
        expect(screen.getByText('Generate Slips')).toBeInTheDocument();
        // spec wished hour/minute inputs; actual is the MUI clock — pin its presence
        expect(document.querySelector('.MuiClock-root')).not.toBeNull();
    });

    it('fetch failure path keeps the loading card (no crash)', async () => {
        server.use(http.get('/api/services', () => HttpResponse.error()));
        render(<Services />);
        // error state: data stays null → loading card persists; assert no crash markers
        await new Promise((r) => setTimeout(r, 50));
        expect(screen.queryByText('Scheduled Time')).not.toBeInTheDocument();
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
        expect(screen.getAllByRole('button', { name: 'Save Settings' }).length).toBeGreaterThan(0);
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

// ── Per-profile auto-generation scheduler (AC-7.6 / issue #95) ────────────────

const ROWS = [
    { name: 'low', auto_generate: true, generate_hour: 8, generate_minute: 30, units: 1.0, target_payout: null, order: 0 },
    { name: 'medium', auto_generate: true, generate_hour: 10, generate_minute: 0, units: 2.0, target_payout: 50, order: 1 },
    { name: 'high_risk', auto_generate: false, generate_hour: 12, generate_minute: 15, units: 1.0, target_payout: null, order: 2 },
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
    it('renders one row per profile with controls, hidden for legacy payloads', async () => {
        server.use(http.get('/api/services', () => HttpResponse.json(
            makeServicesData({ profile_schedules: ROWS }),
        )));
        render(<Services />);
        await screen.findByText('Automation Services');
        expect(screen.getByText('Per-Profile Scheduling')).toBeInTheDocument();
        for (const row of ROWS) {
            expect(screen.getByTitle(row.name)).toBeInTheDocument();
            expect(screen.getByLabelText(`Generation hour for ${row.name}`)).toBeInTheDocument();
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

    it('Save persists all rows in one POST after edits', async () => {
        const user = userEvent.setup();
        const posts: Array<Record<string, unknown>> = [];
        serveRows(posts);
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');

        await user.selectOptions(screen.getByRole('combobox', { name: 'Generation hour for medium' }), '14');
        fireEvent.change(screen.getByLabelText('Units for medium'), { target: { value: '3' } });
        await user.click(screen.getByRole('button', { name: 'Enable auto-generation for high_risk' }));

        await user.click(screen.getByRole('button', { name: 'Save Profile Schedules' }));
        await waitFor(() => expect(posts).toHaveLength(1));
        const rows = posts[0].profile_schedules as Array<Record<string, number | string | boolean | null>>;
        expect(rows).toHaveLength(3);
        expect(rows[1]).toMatchObject({ name: 'medium', generate_hour: 14, units: 3 });
        expect(rows[2]).toMatchObject({ name: 'high_risk', auto_generate: true });
        // legacy global settings are not clobbered when rows are saved
        expect(posts[0].generate_hour).toBeUndefined();
    });

    it('up/down reorder rows and the POST carries the new order', async () => {
        const user = userEvent.setup();
        const posts: Array<Record<string, unknown>> = [];
        serveRows(posts);
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        await user.click(screen.getByRole('button', { name: 'Move medium up' }));
        await user.click(screen.getByRole('button', { name: 'Save Profile Schedules' }));
        await waitFor(() => expect(posts).toHaveLength(1));
        const rows = posts[0].profile_schedules as Array<Record<string, string>>;
        expect(rows.map(r => r.name)).toEqual(['medium', 'low', 'high_risk']);
    });

    it('shows a failure status when the schedules POST fails', async () => {
        const user = userEvent.setup();
        server.use(
            http.get('/api/services', () => HttpResponse.json(makeServicesData({ profile_schedules: ROWS }))),
            http.post('/api/services/settings', () => HttpResponse.error()),
        );
        render(<Services />);
        await screen.findByText('Per-Profile Scheduling');
        await user.click(screen.getByRole('button', { name: 'Save Profile Schedules' }));
        expect(await screen.findByText(/Failed to save profile schedules/)).toBeInTheDocument();
    });
});
