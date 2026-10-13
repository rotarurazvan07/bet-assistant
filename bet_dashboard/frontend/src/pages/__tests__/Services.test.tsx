// Services page (issue #65 + Workstream B Part D). The MUI StaticTimePicker is
// GONE: scheduler is a per-profile table (enable toggle, hour/minute selects,
// units, target payout, next run) with one Save persisting all rows.
// Backwards compat: profiles without a saved schedule prefill from the legacy
// global generate_hour/generate_minute. MSW serves /api/services + /api/profiles.

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Services from '../Services';
import { server } from '../../test/handlers';
import { makeProfileSchedule, makeServicesData, makeServiceInfo } from '../../test/factories';


const DATA = makeServicesData({
    profiles_schedule: {
        low: makeProfileSchedule({ enabled: true, hour: 9, minute: 30, units: 2.5, target_payout: 100, next_run: 'Today 09:30 (in 2h 30m)' }),
        medium: makeProfileSchedule({ enabled: false, hour: 12, minute: 0, units: 1, target_payout: null, next_run: 'Disabled' }),
        high_risk: makeProfileSchedule({ enabled: false, hour: 14, minute: 15, units: 1.5, target_payout: 50, next_run: 'Disabled' }),
    },
});


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

    it('renders one scheduler row per saved profile with controls', async () => {
        render(<Services />);
        await screen.findByText('Per-profile Auto-Generation');
        for (const name of ['low', 'medium', 'high_risk']) {
            expect(screen.getByText(name)).toBeInTheDocument();
            expect(screen.getByRole('switch', { name: `Auto-generate ${name}` })).toBeInTheDocument();
            expect(screen.getByRole('combobox', { name: `${name} hour` })).toBeInTheDocument();
            expect(screen.getByRole('combobox', { name: `${name} minute` })).toBeInTheDocument();
            expect(screen.getByRole('spinbutton', { name: `${name} units` })).toBeInTheDocument();
            expect(screen.getByRole('spinbutton', { name: `${name} target payout` })).toBeInTheDocument();
        }
    });

    it('shows saved next_run labels from the backend', async () => {
        render(<Services />);
        await screen.findByText('Per-profile Auto-Generation');
        expect(screen.getByText('Today 09:30 (in 2h 30m)')).toBeInTheDocument();
        expect(screen.getAllByText('Disabled').length).toBe(2);
    });

    it('MUI StaticTimePicker is gone — no clock artifacts on the page', async () => {
        render(<Services />);
        await screen.findByText('Automation Services');
        expect(document.querySelector('.MuiClock-root')).toBeNull();
        expect(screen.queryByText('Scheduled Time')).not.toBeInTheDocument();
        expect(screen.getByText('Per-profile Auto-Generation')).toBeInTheDocument();
    });

    it('legacy fallback: profile without saved schedule prefills from global hour/minute', async () => {
        const legacy = makeServicesData({ generate_hour: 7, generate_minute: 0, profiles_schedule: {} });
        server.use(http.get('/api/services', () => HttpResponse.json(legacy)));
        render(<Services />);
        await screen.findByText('Per-profile Auto-Generation');
        for (const name of ['low', 'medium', 'high_risk']) {
            const hour = screen.getByRole('combobox', { name: `${name} hour` }) as HTMLSelectElement;
            expect(hour.value).toBe('7');
            const toggle = screen.getByRole('switch', { name: `Auto-generate ${name}` });
            expect(toggle.getAttribute('aria-checked')).toBe('false');
        }
    });

    it('Save Settings POSTs the per-profile map in one call', async () => {
        const user = userEvent.setup();
        const savedBodies: object[] = [];
        server.use(
            http.post('/api/services/settings', async ({ request }) => {
                savedBodies.push(await request.json() as object);
                return HttpResponse.json({ status: 'ok' });
            }),
        );
        render(<Services />);
        await screen.findByText('Per-profile Auto-Generation');
        // medium starts disabled — flip it on before saving
        await user.click(screen.getByRole('switch', { name: 'Auto-generate medium' }));
        await user.click(screen.getByRole('button', { name: 'Save Settings' }));
        expect(await screen.findByText(/Schedules saved/)).toBeInTheDocument();
        expect(savedBodies.length).toBe(1);
        const body = savedBodies[0] as { profiles: Record<string, { enabled: boolean; hour: number; minute: number; units: number; target_payout: number | null }> };
        expect(body.profiles).toBeDefined();
        expect(Object.keys(body.profiles).sort()).toEqual(['high_risk', 'low', 'medium']);
        expect(body.profiles.low.enabled).toBe(true);
        expect(body.profiles.low.hour).toBe(9);
        expect(body.profiles.low.units).toBe(2.5);
        expect(body.profiles.low.target_payout).toBe(100);
        expect(body.profiles.medium.enabled).toBe(true);
    });

    it('save failure surfaces the error status without crashing', async () => {
        const user = userEvent.setup();
        server.use(http.post('/api/services/settings', () => HttpResponse.error()));
        render(<Services />);
        await screen.findByText('Per-profile Auto-Generation');
        await user.click(screen.getByRole('button', { name: 'Save Settings' }));
        expect(await screen.findByText(/Save failed/)).toBeInTheDocument();
    });

    it('fetch failure path keeps the loading card (no crash)', async () => {
        server.use(http.get('/api/services', () => HttpResponse.error()));
        render(<Services />);
        await new Promise((r) => setTimeout(r, 50));
        expect(screen.queryByText('Per-profile Auto-Generation')).not.toBeInTheDocument();
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
                profiles_schedule: DATA.profiles_schedule,
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
