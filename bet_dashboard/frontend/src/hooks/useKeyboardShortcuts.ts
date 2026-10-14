import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

/** One row in the help overlay (single source of truth for all shortcuts). */
export interface ShortcutEntry {
    combo: string;
    description: string;
    scope: string;
}

export const SHORTCUTS: ShortcutEntry[] = [
    { combo: 'Ctrl/⌘ + R', description: 'Refresh the current tab', scope: 'Anywhere' },
    { combo: 'Ctrl/⌘ + P', description: 'Pull update (download the latest database)', scope: 'Anywhere' },
    { combo: 'Ctrl/⌘ + V', description: 'Validate slip results', scope: 'Track tab' },
    { combo: 'Ctrl/⌘ + G', description: 'Generate slips from profiles', scope: 'Track tab' },
    { combo: 'Ctrl/⌘ + N', description: 'New slip — go to Build and focus the config', scope: 'Anywhere' },
    { combo: 'Ctrl/⌘ + /', description: 'Focus the search box', scope: 'Discover tab' },
    { combo: 'Ctrl/⌘ + ?', description: 'Show this help overlay', scope: 'Anywhere' },
];

/** Page-provided actions. Entries are optional; pages register on mount and
 * unregister on unmount. The hook reads them lazily at keypress time. */
export const shortcutRegistry: {
    refresh?: () => void;
    pull?: () => void;
    validate?: () => void;
    generate?: () => void;
    focusSearch?: () => void;
    toggleHelp?: () => void;
} = {};

function isEditable(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false;
    const tag = target.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
}

/**
 * Global keyboard-shortcut layer (issue #47 / Workstream B Part B).
 *
 * Installs ONE keydown listener. Combos require Cmd/Ctrl and are ignored while
 * focus is in an editable element (input/textarea/select/contenteditable).
 * Tab-gated keys check the current route; handled combos call preventDefault
 * so browser-reserved bindings (Ctrl+R reload, Ctrl+P print) do not fire.
 */
export function useKeyboardShortcuts(): void {
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (!(e.metaKey || e.ctrlKey)) return;
            if (isEditable(e.target)) return;
            const path = location.pathname;
            switch (e.key.toLowerCase()) {
                case 'r':
                    e.preventDefault();
                    shortcutRegistry.refresh?.();
                    break;
                case 'p':
                    e.preventDefault();
                    shortcutRegistry.pull?.();
                    break;
                case 'v':
                    if (path === '/slips') {
                        e.preventDefault();
                        shortcutRegistry.validate?.();
                    }
                    break;
                case 'g':
                    if (path === '/slips') {
                        e.preventDefault();
                        shortcutRegistry.generate?.();
                    }
                    break;
                case 'n': {
                    e.preventDefault();
                    navigate('/builder');
                    setTimeout(() => {
                        document.querySelector<HTMLElement>('[data-shortcut-target]')?.focus();
                    }, 0);
                    break;
                }
                case '/':
                    if (path === '/') {
                        e.preventDefault();
                        shortcutRegistry.focusSearch?.();
                    }
                    break;
                case '?':
                    e.preventDefault();
                    shortcutRegistry.toggleHelp?.();
                    break;
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [location.pathname, navigate]);
}
