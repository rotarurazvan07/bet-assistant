// ShortcutsOverlay (issue #47 / Workstream B Part B): help overlay for all
// shortcuts — focus-trapped dialog, Escape closes, focus returns to trigger.

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ShortcutsOverlay } from '../ShortcutsOverlay';
import { SHORTCUTS } from '../../hooks/useKeyboardShortcuts';


afterEach(cleanup);


describe('ShortcutsOverlay', () => {
    it('renders nothing when closed', () => {
        render(<ShortcutsOverlay open={false} onClose={() => {}} />);
        expect(screen.queryByTestId('shortcuts-overlay')).not.toBeInTheDocument();
    });

    it('lists every registered shortcut when open (AC #47: help overlay lists all)', () => {
        render(<ShortcutsOverlay open={true} onClose={() => {}} />);
        expect(screen.getByTestId('shortcuts-overlay')).toBeInTheDocument();
        for (const s of SHORTCUTS) {
            expect(screen.getByText(s.combo)).toBeInTheDocument();
            expect(screen.getByText(s.description)).toBeInTheDocument();
        }
    });

    it('is an ARIA dialog labelled by its title', () => {
        render(<ShortcutsOverlay open={true} onClose={() => {}} />);
        const dialog = screen.getByRole('dialog');
        expect(dialog.getAttribute('aria-modal')).toBe('true');
        expect(dialog.getAttribute('aria-labelledby')).toBe('shortcuts-title');
        expect(document.getElementById('shortcuts-title')).toBeInTheDocument();
    });

    it('Escape closes the overlay (capture-phase wins over other handlers)', () => {
        const onClose = vi.fn();
        render(<ShortcutsOverlay open={true} onClose={onClose} />);
        fireEvent.keyDown(window, { key: 'Escape' });
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('Close button calls onClose', () => {
        const onClose = vi.fn();
        render(<ShortcutsOverlay open={true} onClose={onClose} />);
        fireEvent.click(screen.getByTestId('shortcuts-close'));
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('returns focus to the trigger element when it closes (AC #47)', () => {
        const trigger = document.createElement('button');
        trigger.textContent = 'trigger';
        document.body.appendChild(trigger);
        trigger.focus();
        const { rerender } = render(<ShortcutsOverlay open={true} onClose={() => {}} />);
        rerender(<ShortcutsOverlay open={false} onClose={() => {}} />);
        expect(document.activeElement).toBe(trigger);
        trigger.remove();
    });
});
