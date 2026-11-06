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
    onMatchesUpdated?: () => void;
}

function renderLayout(route: string = '/', overrides: LayoutOverrides = {}) {
    const defaults = {
        lastPull: 'Last Pull: 12:00',
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

    it('does not render a refresh button', () => {
        renderLayout();
        expect(screen.queryByRole('button', { name: 'Refresh' })).not.toBeInTheDocument();
    });

    it('Pull Matches resolves via MSW /api/pull and fires onMatchesUpdated on ok', async () => {
        const user = userEvent.setup();
        const onMatchesUpdated = vi.fn();
        renderLayout('/', { onMatchesUpdated });
        await user.click(screen.getByText('↓ Pull Matches'));
        // wait for the pulling state to clear (handler returns {status:'ok'})
        await screen.findByText('↓ Pull Matches');
        expect(onMatchesUpdated).toHaveBeenCalledTimes(1);
    });

    it('shows lastPull text when provided', () => {
        renderLayout('/', { lastPull: 'Last Pull: 12:34' });
        expect(screen.getByText('Last Pull: 12:34')).toBeInTheDocument();
    });

    it('shows the running build commit at the far right of the header', () => {
        renderLayout();
        const buildLabel = screen.getByLabelText(/^Build /);
        expect(buildLabel).toHaveTextContent(/^Build (?:[a-f0-9]{7}|unknown)$/);
        expect(buildLabel).toHaveAttribute('title', expect.stringMatching(/^Commit /));
        expect(buildLabel.parentElement?.lastElementChild).toBe(buildLabel);
    });

    it('does not render a Restart Tour button', () => {
        renderLayout();
        expect(screen.queryByRole('button', { name: 'Restart Tour' })).not.toBeInTheDocument();
    });
});
