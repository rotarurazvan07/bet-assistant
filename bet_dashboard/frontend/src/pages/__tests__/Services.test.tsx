// Services page (issue #65). ACTUAL divergences (cycle 13): settings use a
// MUI StaticTimePicker (NOT spec's hour/minute number inputs); NO Pull DB
// button on this page (that is Layout's Pull Update, cycle-12 tested);
// status line confirms save. MSW serves /api/services.

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Services from '../Services';
import { server } from '../../test/handlers';
import { makeServicesData } from '../../test/factories';


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
