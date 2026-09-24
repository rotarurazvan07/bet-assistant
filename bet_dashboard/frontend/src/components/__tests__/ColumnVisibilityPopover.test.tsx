// ColumnVisibilityPopover (issue #64 P0). ACTUAL behavior (cycle-12
// divergence): NO persistence — parent owns visibleKeys; portal-based
// popover; click-outside closes.

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ColumnVisibilityPopover from '../ColumnVisibilityPopover';


const COLUMNS = [
    { market: 'home', label: 'Home', consKey: 'cons_home', oddsKey: 'odds_home', marketType: 'Result' },
    { market: 'over_25', label: 'O/U 2.5', consKey: 'cons_over_25', oddsKey: 'odds_over_25', marketType: 'O/U 2.5' },
];


function makeVisibleSet(keys: string[]): Set<string> {
    return new Set(keys);
}


describe('ColumnVisibilityPopover', () => {
    it('renders the trigger button without popover initially', () => {
        render(<ColumnVisibilityPopover columns={COLUMNS} visibleKeys={makeVisibleSet(['home'])} onToggle={() => {}} />);
        expect(screen.getByTitle('Toggle columns')).toBeInTheDocument();
        expect(screen.queryByText('Market Columns')).not.toBeInTheDocument();
    });

    it('opens the popover on trigger click showing all column labels', async () => {
        const user = userEvent.setup();
        render(<ColumnVisibilityPopover columns={COLUMNS} visibleKeys={makeVisibleSet(['home'])} onToggle={() => {}} />);
        await user.click(screen.getByTitle('Toggle columns'));
        expect(screen.getByText('Market Columns')).toBeInTheDocument();
        expect(screen.getByText('Home')).toBeInTheDocument();
        expect(screen.getByText('O/U 2.5')).toBeInTheDocument();
    });

    it('checkbox reflects current visibility state', async () => {
        const user = userEvent.setup();
        render(<ColumnVisibilityPopover columns={COLUMNS} visibleKeys={makeVisibleSet(['home'])} onToggle={() => {}} />);
        await user.click(screen.getByTitle('Toggle columns'));
        const homeCheck = screen.getByRole('checkbox', { name: 'Home' }) as HTMLInputElement;
        const ouCheck = screen.getByRole('checkbox', { name: 'O/U 2.5' }) as HTMLInputElement;
        expect(homeCheck.checked).toBe(true);
        expect(ouCheck.checked).toBe(false);
    });

    it('checkbox change fires onToggle with the market key', async () => {
        const user = userEvent.setup();
        const onToggle = vi.fn();
        render(<ColumnVisibilityPopover columns={COLUMNS} visibleKeys={makeVisibleSet(['home'])} onToggle={onToggle} />);
        await user.click(screen.getByTitle('Toggle columns'));
        await user.click(screen.getByRole('checkbox', { name: 'O/U 2.5' }));
        expect(onToggle).toHaveBeenCalledWith('over_25');
    });

    it('closes on click outside (no persistence — parent state test)', async () => {
        const user = userEvent.setup();
        render(<ColumnVisibilityPopover columns={COLUMNS} visibleKeys={makeVisibleSet(['home'])} onToggle={() => {}} />);
        await user.click(screen.getByTitle('Toggle columns'));
        expect(screen.getByText('Market Columns')).toBeInTheDocument();
        // click outside: on body (outside popover + trigger)
        fireEvent.mouseDown(document.body);
        expect(screen.queryByText('Market Columns')).not.toBeInTheDocument();
    });
});
