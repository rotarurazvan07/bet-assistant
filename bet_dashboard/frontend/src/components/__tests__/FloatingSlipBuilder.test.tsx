// FloatingSlipBuilder (issue #64 P1). ACTUAL: portal wrapper — minimized
// shows 'N leg(s) • totalOdds' + ▲; expanded renders SlipBuilderPanel.

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FloatingSlipBuilder from '../FloatingSlipBuilder';
import { makeCandidateLeg } from '../../test/factories';


function legs(n: number) {
    return Array.from({ length: n }, (_, i) => makeCandidateLeg({ odds: 1.5 + i, match_name: `Match ${i + 1}` }));
}


describe('FloatingSlipBuilder', () => {
    it('minimized: renders leg count + totalOdds + expand arrow in portal', () => {
        render(<FloatingSlipBuilder legs={legs(2)} onRemoveLeg={() => {}} onSubmit={() => {}} isMinimized={true} onToggleMinimize={() => {}} />);
        expect(screen.getByText('2 legs')).toBeInTheDocument();
        expect(screen.getByText(/3\.75/)).toBeInTheDocument(); // 1.5*2.5
        expect(screen.getByText('▲')).toBeInTheDocument();
    });

    it('minimized: singular leg text', () => {
        render(<FloatingSlipBuilder legs={legs(1)} onRemoveLeg={() => {}} onSubmit={() => {}} isMinimized={true} onToggleMinimize={() => {}} />);
        expect(screen.getByText('1 leg')).toBeInTheDocument();
    });

    it('minimized: click expands via onToggleMinimize', async () => {
        const user = userEvent.setup();
        const onToggleMinimize = vi.fn();
        render(<FloatingSlipBuilder legs={legs(2)} onRemoveLeg={() => {}} onSubmit={() => {}} isMinimized={true} onToggleMinimize={onToggleMinimize} />);
        await user.click(screen.getByText('▲'));
        expect(onToggleMinimize).toHaveBeenCalledTimes(1);
    });

    it('minimized: hides totalOdds when zero valid legs', () => {
        render(<FloatingSlipBuilder legs={[makeCandidateLeg({ odds: 0 })]} onRemoveLeg={() => {}} onSubmit={() => {}} isMinimized={true} onToggleMinimize={() => {}} />);
        expect(screen.getByText('1 leg')).toBeInTheDocument();
        expect(screen.queryByText(/•/)).not.toBeInTheDocument();
    });

    it('expanded: renders the full SlipBuilderPanel', () => {
        render(<FloatingSlipBuilder legs={legs(2)} onRemoveLeg={() => {}} onSubmit={() => {}} isMinimized={false} onToggleMinimize={() => {}} />);
        expect(screen.getByText('Slip Builder')).toBeInTheDocument();
        expect(screen.getByText('2 legs selected')).toBeInTheDocument();
    });

    it('expanded: Add Slip fires through to onSubmit', async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn();
        render(<FloatingSlipBuilder legs={legs(1)} onRemoveLeg={() => {}} onSubmit={onSubmit} isMinimized={false} onToggleMinimize={() => {}} />);
        await user.click(screen.getByText('Add Slip'));
        expect(onSubmit).toHaveBeenCalledWith(1);
    });
});
