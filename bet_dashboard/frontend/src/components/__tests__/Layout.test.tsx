// Layout. ACTUAL: NO sidebar — top
// bar + NavLink×6; date filters belong to each page; Pull → pullDb() →
// onMatchesUpdated only when status==='ok'. Needs MemoryRouter wrapper.
// nav grouped by separators; flat DOM anchor order = keyboard order.

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
            <Layout {...defaults}><div data-testid="child">Page content</div></Layout>
        </MemoryRouter>,
    );
}

beforeEach(() => {
    localStorage.clear();
    // existing header/nav assertions must not see first-visit tour.
    localStorage.setItem('bet-assistant-tour-done', '1');
});

describe('Layout', () => {
    it('renders brand and all 6 renamed nav links (divergence: no sidebar)', () => {
        renderLayout();
        const brand = screen.getByText((content, element) => {
            return element !== null && content.includes('Bet') && element.className.includes('font-display');
        });
        expect(brand).toBeInTheDocument();
        // renamed labels render
        for (const label of ['Discover', 'Build', 'Track', 'Analytics', 'Services', 'Odds Alert']) {
            expect(screen.getByText(label)).toBeInTheDocument();
        }
    });

    it('does not render group captions', () => {
        renderLayout();
        for (const caption of ['Core', 'Insights', 'System']) {
            expect(screen.queryByText(caption)).not.toBeInTheDocument();
        }
    });

    it('renders nav anchors in grouped DOM order: Core → Insights → System', () => {
        renderLayout();
        const nav = document.querySelector('nav');
        expect(nav).not.toBeNull();
        const anchors = Array.from(nav!.querySelectorAll('a')).map(a => a.textContent);
        expect(anchors).toEqual(['Discover', 'Build', 'Track', 'Analytics', 'Services', 'Odds Alert']);
    });

    it('renders group separators between the three groups', () => {
        renderLayout();
        const nav = document.querySelector('nav');
        expect(nav!.querySelectorAll('.nav-separator')).toHaveLength(2);
    });

    it('retains accessible nav group labels', () => {
        renderLayout();
        for (const caption of ['Core', 'Insights', 'System']) {
            expect(screen.getByRole('group', { name: caption })).toBeInTheDocument();
        }
    });

    it('preserves route hrefs unchanged (routes untouched)', () => {
        renderLayout();
        const nav = document.querySelector('nav');
        const hrefs = Array.from(nav!.querySelectorAll('a')).map(a => a.getAttribute('href'));
        expect(hrefs).toEqual(['/', '/builder', '/slips', '/analytics', '/services', '/odds-alert']);
    });

    it('keyboard Tab order follows visual group order', async () => {
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

    it('renders page content directly', () => {
        renderLayout();
        const child = screen.getByTestId('child');
        expect(child).toBeInTheDocument();
        expect(child.textContent).toBe('Page content');
    });

    it('does not render a global date range on page routes', () => {
        for (const route of ['/', '/builder', '/slips', '/analytics', '/services', '/odds-alert']) {
            const { unmount } = renderLayout(route);
            expect(screen.queryByText('Time Horizon')).not.toBeInTheDocument();
            expect(document.querySelector('input[type="date"]')).toBeNull();
            unmount();
        }
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
