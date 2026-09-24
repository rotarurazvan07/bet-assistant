// SlipBuilderPanel (issue #64 P1). ACTUAL (cycle-12 divergence): NO match
// autocomplete, NO market select, NO URL validation — display + units
// input + Add Slip only. totalOdds = product of valid odds; potentialWin =
// totalOdds*units - units.

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SlipBuilderPanel from '../SlipBuilderPanel';
import { makeCandidateLeg } from '../../test/factories';


function legs(n: number) {
    return Array.from({ length: n }, (_, i) => makeCandidateLeg({ odds: 2 + i * 0.5, match_name: `Match ${i + 1}` }));
}


describe('SlipBuilderPanel', () => {
    it('empty state: No legs selected message', () => {
        render(<SlipBuilderPanel legs={[]} onRemoveLeg={() => {}} onSubmit={() => {}} />);
        expect(screen.getByText('No legs selected.')).toBeInTheDocument();
    });

    it('renders leg count with plural handling', () => {
        const { unmount } = render(<SlipBuilderPanel legs={legs(1)} onRemoveLeg={() => {}} onSubmit={() => {}} />);
        expect(screen.getByText('1 leg selected')).toBeInTheDocument();
        unmount();
        render(<SlipBuilderPanel legs={legs(2)} onRemoveLeg={() => {}} onSubmit={() => {}} />);
        expect(screen.getByText('2 legs selected')).toBeInTheDocument();
    });

    it('totalOdds = product of leg odds', () => {
        render(<SlipBuilderPanel legs={legs(2)} onRemoveLeg={() => {}} onSubmit={() => {}} />);
        // 2.0 * 2.5 = 5.00
        expect(screen.getByText('5.00')).toBeInTheDocument();
    });

    it('potentialWin = totalOdds*units − units (default 1 unit)', () => {
        render(<SlipBuilderPanel legs={legs(2)} onRemoveLeg={() => {}} onSubmit={() => {}} />);
        // 5.00*1 − 1 = 4.00
        expect(screen.getByText('4.00')).toBeInTheDocument();
    });

    it('units input updates potentialWin', async () => {
        // Controlled number input + Math.max clamping makes user-event's
        // per-keystroke typing unreliable here (re-render resets cursor);
        // fireEvent.change sets the full value deterministically.
        const { fireEvent } = await import('@testing-library/react');
        render(<SlipBuilderPanel legs={legs(2)} onRemoveLeg={() => {}} onSubmit={() => {}} />);
        const input = screen.getByRole('spinbutton');
        fireEvent.change(input, { target: { value: '2' } });
        // 5.00*2 − 2 = 8.00
        expect(screen.getByText('8.00')).toBeInTheDocument();
    });

    it('Add Slip fires onSubmit with current units', async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn();
        render(<SlipBuilderPanel legs={legs(1)} onRemoveLeg={() => {}} onSubmit={onSubmit} />);
        await user.click(screen.getByText('Add Slip'));
        expect(onSubmit).toHaveBeenCalledWith(1);
    });

    it('remove button fires onRemoveLeg with the index', async () => {
        const user = userEvent.setup();
        const onRemoveLeg = vi.fn();
        render(<SlipBuilderPanel legs={legs(2)} onRemoveLeg={onRemoveLeg} onSubmit={() => {}} />);
        const removeBtn = screen.getByRole('button', { name: /Remove Match 2/ });
        await user.click(removeBtn);
        expect(onRemoveLeg).toHaveBeenCalledWith(1);
    });

    it('minimize button fires onToggleMinimize when provided', async () => {
        const user = userEvent.setup();
        const onToggleMinimize = vi.fn();
        render(<SlipBuilderPanel legs={legs(1)} onRemoveLeg={() => {}} onSubmit={() => {}} onToggleMinimize={onToggleMinimize} />);
        await user.click(screen.getByTitle('Minimize'));
        expect(onToggleMinimize).toHaveBeenCalledTimes(1);
    });
});
