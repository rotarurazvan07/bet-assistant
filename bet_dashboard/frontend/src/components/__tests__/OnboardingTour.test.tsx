// Onboarding tour (issue #50 AC-10). MemoryRouter required (useNavigate).
// Do not mock the @mui/material barrel. Role locators only.

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import OnboardingTour from '../OnboardingTour';
import { FIRST_SLIP_KEY, TOUR_DONE_KEY, markFirstSlip } from '../tourStorage';

function renderTour(route = '/') {
    return render(
        <MemoryRouter initialEntries={[route]}>
            <OnboardingTour />
        </MemoryRouter>,
    );
}

beforeEach(() => {
    localStorage.clear();
});

describe('OnboardingTour', () => {
    it('shows Find value bets when the done key is absent', () => {
        renderTour();
        expect(screen.getByRole('dialog', { name: 'Find value bets' })).toBeInTheDocument();
    });

    it('treats invalid and empty done keys as a first visit', () => {
        localStorage.setItem(TOUR_DONE_KEY, '0');
        const { unmount } = renderTour();
        expect(screen.getByRole('dialog', { name: 'Find value bets' })).toBeInTheDocument();
        unmount();
        localStorage.setItem(TOUR_DONE_KEY, '');
        renderTour();
        expect(screen.getByRole('dialog', { name: 'Find value bets' })).toBeInTheDocument();
    });

    it('Skip persists done and hides the dialog', async () => {
        const user = userEvent.setup();
        renderTour();
        await user.click(screen.getByRole('button', { name: 'Skip' }));
        expect(localStorage.getItem(TOUR_DONE_KEY)).toBe('1');
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('Next moves to Create your strategy', async () => {
        const user = userEvent.setup();
        renderTour();
        await user.click(screen.getByRole('button', { name: 'Next' }));
        expect(screen.getByRole('dialog', { name: 'Create your strategy' })).toBeInTheDocument();
    });

    it('Back is disabled on step 0', () => {
        renderTour();
        expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled();
    });

    it('does not show a dialog when the done key is 1', () => {
        localStorage.setItem(TOUR_DONE_KEY, '1');
        renderTour();
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('Esc skips, persists, and hides the dialog', async () => {
        const user = userEvent.setup();
        renderTour();
        await user.keyboard('{Escape}');
        expect(localStorage.getItem(TOUR_DONE_KEY)).toBe('1');
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('markFirstSlip toasts only once', () => {
        expect(markFirstSlip()).toBe(true);
        expect(localStorage.getItem(FIRST_SLIP_KEY)).toBe('1');
        expect(markFirstSlip()).toBe(false);
    });
});
