// SlipBuilderPanel (issue #64 P1 + #39). ACTUAL: display + units input +
// Add Slip only. #39 adds: isMobileSheet prop drops the L99 maxHeight trap,
// heading id for aria-labelledby, Ctrl+Enter / Esc window listeners.

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

// ── issue #39 ────────────────────────────────────────────────────────────────
describe('SlipBuilderPanel #39', () => {
    it('AC-13: heading carries the id used by the dialog aria-labelledby', () => {
        render(<SlipBuilderPanel legs={legs(1)} onRemoveLeg={() => {}} onSubmit={() => {}} />);
        expect(screen.getByText('Slip Builder').id).toBe('slip-builder-title');
    });

    it('AC-04: Ctrl+Enter calls onSubmit with current units when legs exist', async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn();
        render(<SlipBuilderPanel legs={legs(1)} onRemoveLeg={() => {}} onSubmit={onSubmit} />);
        await user.keyboard('{Control>}{Enter}{/Control}');
        expect(onSubmit).toHaveBeenCalledWith(1);
    });

    it('AC-04: Ctrl+Enter does nothing when there are no legs', async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn();
        render(<SlipBuilderPanel legs={[]} onRemoveLeg={() => {}} onSubmit={onSubmit} />);
        await user.keyboard('{Control>}{Enter}{/Control}');
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('AC-05: Escape calls onToggleMinimize when expanded', async () => {
        const user = userEvent.setup();
        const onToggleMinimize = vi.fn();
        render(<SlipBuilderPanel legs={legs(1)} onRemoveLeg={() => {}} onSubmit={() => {}} onToggleMinimize={onToggleMinimize} />);
        await user.keyboard('{Escape}');
        expect(onToggleMinimize).toHaveBeenCalledTimes(1);
    });

    it('AC-03/AC-02: mobile sheet drops the calc(100vh - 380px) list maxHeight', () => {
        const { container } = render(<SlipBuilderPanel legs={legs(1)} onRemoveLeg={() => {}} onSubmit={() => {}} isMobileSheet />);
        const list = container.querySelector('.overflow-y-auto') as HTMLElement;
        expect(list.style.maxHeight).toBe('');
    });
});