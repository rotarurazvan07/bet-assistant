import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import Unstable_TrapFocus from '@mui/material/Unstable_TrapFocus';
import { SHORTCUTS } from '../hooks/useKeyboardShortcuts';

/**
 * Keyboard-shortcuts help overlay (issue #47 / Workstream B Part B).
 *
 * Opens on Ctrl/⌘+? (registered by Layout via the shortcut registry). Focus is
 * trapped while open, Escape closes it (capture-phase, so it wins over the slip
 * panel's Escape), and focus returns to the element that had it before opening.
 */
export function ShortcutsOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
    const restoreRef = useRef<HTMLElement | null>(null);

    useEffect(() => {
        if (!open) return;
        restoreRef.current = document.activeElement as HTMLElement | null;
        const onKey = (e: KeyboardEvent) => {
            if (e.key !== 'Escape') return;
            e.stopPropagation();
            e.preventDefault();
            onClose();
        };
        window.addEventListener('keydown', onKey, true);
        return () => {
            window.removeEventListener('keydown', onKey, true);
            restoreRef.current?.focus?.();
        };
    }, [open, onClose]);

    if (!open) return null;

    return createPortal(
        <Unstable_TrapFocus open>
            <div
                className="shortcuts-overlay"
                role="dialog"
                aria-modal="true"
                aria-labelledby="shortcuts-title"
                data-testid="shortcuts-overlay"
            >
                <div className="shortcuts-card">
                    <h2 id="shortcuts-title" className="font-display font-bold text-base"
                        style={{ color: 'var(--text-bright)', margin: '0 0 12px' }}>
                        Keyboard Shortcuts
                    </h2>
                    <table className="w-full text-left border-collapse mb-4">
                        <thead>
                            <tr className="font-mono text-[9px] uppercase tracking-widest"
                                style={{ color: 'var(--text-secondary)' }}>
                                <th className="py-1.5 pr-3">Shortcut</th>
                                <th className="py-1.5 pr-3">Action</th>
                                <th className="py-1.5">Where</th>
                            </tr>
                        </thead>
                        <tbody>
                            {SHORTCUTS.map((s) => (
                                <tr key={s.combo} style={{ borderTop: '1px solid var(--border)' }}>
                                    <td className="py-2 pr-3">
                                        <kbd className="font-mono text-[10px] font-bold px-2 py-0.5 rounded"
                                            style={{ color: 'var(--accent)', background: 'var(--accent-glow)' }}>
                                            {s.combo}
                                        </kbd>
                                    </td>
                                    <td className="py-2 pr-3 font-sans text-[11px]"
                                        style={{ color: 'var(--text-secondary)' }}>
                                        {s.description}
                                    </td>
                                    <td className="py-2 font-mono text-[10px]"
                                        style={{ color: 'var(--text-secondary)' }}>
                                        {s.scope}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <div className="flex justify-end">
                        <button type="button" className="btn-primary" onClick={onClose} data-testid="shortcuts-close">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </Unstable_TrapFocus>,
        document.body,
    );
}
