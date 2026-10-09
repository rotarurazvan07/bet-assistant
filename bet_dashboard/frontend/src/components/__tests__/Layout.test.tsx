// Layout (issue #64 P1). ACTUAL (cycle-12 divergence): NO sidebar — top
// bar + NavLink×6; Time Horizon pickers on 4 routes only; persisted
// localStorage 'bet-assistant-time-horizon'; Pull → pullDb() →
// onMatchesUpdated only when status==='ok'. Needs MemoryRouter wrapper.
// Issue #36: nav grouped Core/Insights/System — captions above groups,
// separators between groups, flat DOM anchor order = keyboard order.

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../Layout';

interface LayoutOverrides {
    lastPull?: string;
    onRefresh?: () => void;
    onMatchesUpdated?: () => void;
}

function renderLayout(route: string = '/', overrides: LayoutOverrides = {}) {
    const defaults = {
        lastPull: 'Updated: 12:00',
        onRefresh: () => {},
        onMatchesUpdated: () => {},
        ...overrides,
    };
    return render(
        <MemoryRouter initialEntries={[route]}>
            <Layout {...defaults}>
                {(filters) => <div data-testid="child">{filters.dateFrom}|{filters.dateTo}</div>}
            </Layout>
        </MemoryRouter>,
    );
}

beforeEach(() => {
    localStorage.clear();
    // AC-09: existing header/nav assertions must not see first-visit tour.
    localStorage.setItem('bet-assistant-tour-done', '1');
});

describe('Layout', () => {
    it('renders brand and all 6 renamed nav links (divergence: no sidebar)', () => {
        renderLayout();
        const brand = screen.getByText((content, element) => {
            return element !== null && content.includes('Bet') && element.className.includes('font-display');
        });
        expect(brand).toBeInTheDocument();
        // AC-02: renamed labels render
        for (const label of ['Discover', 'Build', 'Track', 'Analytics', 'Services', 'Odds Alert']) {
            expect(screen.getByText(label)).toBeInTheDocument();
        }
    });

    it('renders group micro-captions Core, Insights, System (issue #36, SM-approved)', () => {
        renderLayout();
        // AC-03: micro-captions above each group
        for (const caption of ['Core', 'Insights', 'System']) {
            expect(screen.getByText(caption)).toBeInTheDocument();
        }
    });

    it('renders nav anchors in grouped DOM order: Core → Insights → System (AC-01, AC-04)', () => {
        renderLayout();
        const nav = document.querySelector('nav');
        expect(nav).not.toBeNull();
        const anchors = Array.from(nav!.querySelectorAll('a')).map(a => a.textContent);
        expect(anchors).toEqual(['Discover', 'Build', 'Track', 'Analytics', 'Services', 'Odds Alert']);
    });

    it('renders group separators between the three groups (AC-03)', () => {
        renderLayout();
        const nav = document.querySelector('nav');
        expect(nav!.querySelectorAll('.nav-separator')).toHaveLength(2);
    });

    it('labels each nav group for assistive tech (issue #36 polish)', () => {
        renderLayout();
        for (const caption of ['Core', 'Insights', 'System']) {
            expect(screen.getByRole('group', { name: caption })).toBeInTheDocument();
        }
    });

    it('preserves route hrefs unchanged (AC-01: routes untouched)', () => {
        renderLayout();
        const nav = document.querySelector('nav');
        const hrefs = Array.from(nav!.querySelectorAll('a')).map(a => a.getAttribute('href'));
        expect(hrefs).toEqual(['/', '/builder', '/slips', '/analytics', '/services', '/odds-alert']);
    });

    it('keyboard Tab order follows visual group order (AC-04)', async () => {
        const user = userEvent.setup();
        renderLayout();
        const nav = document.querySelector('nav');
        const anchors = Array.from(nav!.querySelectorAll('a')) as HTMLAnchorElement[];
        anchors[0].focus();
        const seen: string[] = [document.activeElement!.textContent!];
        for (let i = 1; i < anchors.length; i++) {
            await user.tab();
            seen.push(document.activeElement!.textContent!);
        }
        expect(seen).toEqual(['Discover', 'Build', 'Track', 'Analytics', 'Services', 'Odds Alert']);
    });

    it('renders children via render prop with empty filters initially', () => {
        renderLayout();
        const child = screen.getByTestId('child');
        expect(child).toBeInTheDocument();
        expect(child.textContent).toBe('|');
    });

    it('shows Time Horizon on the root route', () => {
        renderLayout('/');
        expect(screen.getByText('Time Horizon')).toBeInTheDocument();
    });

    it('shows Time Horizon on builder, slips and analytics routes', () => {
        for (const route of ['/builder', '/slips', '/analytics']) {
            const { unmount } = renderLayout(route);
            expect(screen.getByText('Time Horizon')).toBeInTheDocument();
            unmount();
        }
    });

    it('hides Time Horizon on services and odds-alert routes', () => {
        const { unmount } = renderLayout('/services');
        expect(screen.queryByText('Time Horizon')).not.toBeInTheDocument();
        unmount();
        renderLayout('/odds-alert');
        expect(screen.queryByText('Time Horizon')).not.toBeInTheDocument();
    });

    it('date inputs update filters passed to children', async () => {
        const user = userEvent.setup();
        renderLayout('/');
        // input[type=date] has no textbox role in jsdom - query DOM directly
        const inputs = document.querySelectorAll('input[type="date"]') as NodeListOf<HTMLInputElement>;
        const dateFrom = inputs[0];
        // typing date digits into input[type=date] via user-event: assign value
        await user.type(dateFrom, '2026-09-01');
        expect(screen.getByTestId('child').textContent).toContain('2026-09');
    });

    it('persists date range to localStorage after change', async () => {
        const user = userEvent.setup();
        renderLayout('/');
        const inputs = document.querySelectorAll('input[type="date"]') as NodeListOf<HTMLInputElement>;
        await user.type(inputs[0], '2026-09-01');
        const saved = localStorage.getItem('bet-assistant-time-horizon');
        expect(saved).not.toBeNull();
        expect(JSON.parse(saved as string).dateFrom).toBe('2026-09-01');
    });

    it('restores dates from localStorage on mount', () => {
        localStorage.setItem('bet-assistant-time-horizon', JSON.stringify({ dateFrom: '2026-08-01', dateTo: '2026-08-15' }));
        renderLayout('/');
        expect(screen.getByTestId('child').textContent).toBe('2026-08-01|2026-08-15');
    });

    it('Refresh button fires onRefresh', async () => {
        const user = userEvent.setup();
        const onRefresh = vi.fn();
        renderLayout('/', { onRefresh });
        await user.click(screen.getByText('Refresh'));
        expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    it('Pull Update resolves via MSW /api/pull and fires onMatchesUpdated on ok', async () => {
        const user = userEvent.setup();
        const onMatchesUpdated = vi.fn();
        renderLayout('/', { onMatchesUpdated });
        await user.click(screen.getByText('↓ Pull Update'));
        // wait for the pulling state to clear (handler returns {status:'ok'})
        await screen.findByText('↓ Pull Update');
        expect(onMatchesUpdated).toHaveBeenCalledTimes(1);
    });

    it('shows lastPull text when provided', () => {
        renderLayout('/', { lastPull: 'Updated: 12:34' });
        expect(screen.getByText('Updated: 12:34')).toBeInTheDocument();
    });

    it('Restart Tour clears the done key and shows step 0', async () => {
        const user = userEvent.setup();
        renderLayout();
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
        await user.click(screen.getByRole('button', { name: 'Restart Tour' }));
        expect(localStorage.getItem('bet-assistant-tour-done')).toBeNull();
        expect(screen.getByRole('dialog', { name: 'Find value bets' })).toBeInTheDocument();
    });
});
