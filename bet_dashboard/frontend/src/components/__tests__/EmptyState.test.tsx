// EmptyState (issue #46 AC-09). Presentational: icon, title, numbered steps, CTAs.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EmptyState from '../EmptyState';

describe('EmptyState', () => {
    it('renders icon, title, numbered steps, and fires both CTAs', async () => {
        const user = userEvent.setup();
        const primary = vi.fn();
        const secondary = vi.fn();
        render(
            <EmptyState
                icon={<span data-testid="empty-icon">icon</span>}
                title="No matches yet"
                steps={['Click ↓ Pull Update', 'Adjust filters', 'Add to Slip']}
                primary={{ label: 'Pull Update Now', onClick: primary }}
                secondary={{ label: 'Adjust Filters', onClick: secondary }}
            />,
        );
        const region = screen.getByRole('region', { name: 'No matches yet' });
        expect(region).toHaveAttribute('data-empty-state');
        expect(screen.getByTestId('empty-icon')).toBeInTheDocument();
        expect(screen.getByText('No matches yet')).toBeInTheDocument();
        const items = screen.getAllByRole('listitem');
        expect(items.map((el) => el.textContent)).toEqual([
            'Click ↓ Pull Update',
            'Adjust filters',
            'Add to Slip',
        ]);
        await user.click(screen.getByRole('button', { name: 'Pull Update Now' }));
        await user.click(screen.getByRole('button', { name: 'Adjust Filters' }));
        expect(primary).toHaveBeenCalledTimes(1);
        expect(secondary).toHaveBeenCalledTimes(1);
    });

    it('omits secondary when not provided', () => {
        render(
            <EmptyState
                icon={null}
                title="Solo"
                steps={['Only step']}
                primary={{ label: 'Go', onClick: () => {} }}
            />,
        );
        expect(screen.getByRole('button', { name: 'Go' })).toBeInTheDocument();
        expect(screen.getAllByRole('button')).toHaveLength(1);
    });
});
