// Infra smoke suite (issue #63): one file, three concerns — RTL render,
// MSW interception, vitest+jsdom sanity. Single file sidesteps the
// per-file worker-spawn timeout observed under container CPU (D9).

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BaseBadge } from '../components/ui/BaseBadge';
import { fetchMatches } from '../api/matches';
import { fetchStatus } from '../api/data';
import { makeMatch, makeSlipsPage, makeAnalyticsData, makeServicesData } from './factories';

describe('infra smoke: RTL component render', () => {
    it('renders BaseBadge with children text', () => {
        render(<BaseBadge status="success">Pending</BaseBadge>);
        expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    it('renders default status variant', () => {
        render(<BaseBadge>Plain</BaseBadge>);
        expect(screen.getByText('Plain')).toBeInTheDocument();
    });
});

describe('infra smoke: MSW-intercepted API', () => {
    it('fetchMatches resolves through mocked /api/matches', async () => {
        const page = await fetchMatches({ page: 1, page_size: 20 });
        expect(page.total).toBe(1);
        expect(page.matches[0].home).toBe('Arsenal');
        expect(page.matches[0].cons_home).toBe(75);
    });

    it('fetchStatus resolves through mocked /api/status', async () => {
        const status = await fetchStatus();
        expect(status.last_pull).toBe('2026-09-24T12:00:00');
        expect(status.matches_loaded).toBe(120);
    });

    it('per-test handler overrides via server.use', async () => {
        const { server } = await import('./handlers');
        const { http, HttpResponse } = await import('msw');
        server.use(
            http.get('/api/matches', () =>
                HttpResponse.json({
                    total: 1, page: 1, page_size: 20, total_pages: 1,
                    matches: [makeMatch({ home: 'Override FC' })],
                })),
        );
        const page = await fetchMatches({ page: 1, page_size: 20 });
        expect(page.matches[0].home).toBe('Override FC');
    });
});

describe('infra smoke: vitest + jsdom sanity', () => {
    it('jsdom document works', () => {
        const el = document.createElement('div');
        el.textContent = 'hello';
        document.body.appendChild(el);
        expect(document.body.textContent).toBe('hello');
    });

    it('factories produce valid defaults', () => {
        expect(makeSlipsPage().slips[0].legs[0].odds).toBe(1.9);
        expect(Object.keys(makeAnalyticsData()).length).toBeGreaterThan(10);
        expect(Object.keys(makeServicesData().services)).toContain('verifier');
    });
});
