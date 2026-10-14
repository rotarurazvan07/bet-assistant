// useKeyboardShortcuts (issue #47 / Workstream B Part B): global shortcut layer.
// Guards: requires Cmd/Ctrl; ignored in editables; route-gated V, G, /;
// preventDefault on handled combos so browser bindings (reload/print) stay ours.

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { useKeyboardShortcuts, shortcutRegistry } from '../useKeyboardShortcuts';


function LocationProbe() {
    const location = useLocation();
    return <span data-testid="location">{location.pathname}</span>;
}

function Harness() {
    useKeyboardShortcuts();
    return <LocationProbe />;
}

function renderAt(route: string) {
    return render(
        <MemoryRouter initialEntries={[route]}>
            <Harness />
        </MemoryRouter>,
    );
}

function ctrlKey(key: string, target?: Element) {
    fireEvent.keyDown(target ?? window, { key, ctrlKey: true, metaKey: false });
}


beforeEach(() => {
    vi.clearAllMocks();
    for (const k of Object.keys(shortcutRegistry) as Array<keyof typeof shortcutRegistry>) {
        delete shortcutRegistry[k];
    }
});

afterEach(() => {
    cleanup();
    for (const k of Object.keys(shortcutRegistry) as Array<keyof typeof shortcutRegistry>) {
        delete shortcutRegistry[k];
    }
});


describe('useKeyboardShortcuts', () => {
    it('Ctrl+R dispatches registry.refresh and preventDefaults', () => {
        const refresh = vi.fn();
        shortcutRegistry.refresh = refresh;
        renderAt('/');
        const ev = new KeyboardEvent('keydown', { key: 'r', ctrlKey: true, cancelable: true });
        const spy = vi.spyOn(ev, 'preventDefault');
        fireEvent(window, ev);
        expect(refresh).toHaveBeenCalledTimes(1);
        expect(spy).toHaveBeenCalled();
    });

    it('Ctrl+P dispatches registry.pull', () => {
        const pull = vi.fn();
        shortcutRegistry.pull = pull;
        renderAt('/');
        ctrlKey('p');
        expect(pull).toHaveBeenCalledTimes(1);
    });

    it('no modifier key — nothing fires', () => {
        const refresh = vi.fn();
        shortcutRegistry.refresh = refresh;
        renderAt('/');
        fireEvent.keyDown(window, { key: 'r' });
        expect(refresh).not.toHaveBeenCalled();
    });

    it('focus inside an input — shortcut ignored (AC #47)', () => {
        const refresh = vi.fn();
        shortcutRegistry.refresh = refresh;
        renderAt('/');
        const input = document.createElement('input');
        document.body.appendChild(input);
        fireEvent.keyDown(input, { key: 'r', ctrlKey: true });
        expect(refresh).not.toHaveBeenCalled();
        input.remove();
    });

    it('Ctrl+V fires validate on /slips only', () => {
        const validate = vi.fn();
        shortcutRegistry.validate = validate;
        renderAt('/slips');
        ctrlKey('v');
        expect(validate).toHaveBeenCalledTimes(1);
        cleanup();
        renderAt('/builder');
        ctrlKey('v');
        expect(validate).toHaveBeenCalledTimes(1); // no additional call
    });

    it('Ctrl+G fires generate on /slips only', () => {
        const generate = vi.fn();
        shortcutRegistry.generate = generate;
        renderAt('/slips');
        ctrlKey('g');
        expect(generate).toHaveBeenCalledTimes(1);
        cleanup();
        renderAt('/');
        ctrlKey('g');
        expect(generate).toHaveBeenCalledTimes(1);
    });

    it('Ctrl+/ fires focusSearch on Discover only', () => {
        const focusSearch = vi.fn();
        shortcutRegistry.focusSearch = focusSearch;
        renderAt('/');
        ctrlKey('/');
        expect(focusSearch).toHaveBeenCalledTimes(1);
        cleanup();
        renderAt('/analytics');
        ctrlKey('/');
        expect(focusSearch).toHaveBeenCalledTimes(1);
    });

    it('Ctrl+? toggles the help overlay', () => {
        const toggleHelp = vi.fn();
        shortcutRegistry.toggleHelp = toggleHelp;
        renderAt('/');
        ctrlKey('?');
        expect(toggleHelp).toHaveBeenCalledTimes(1);
    });

    it('Ctrl+N navigates to /builder and focuses the shortcut target', async () => {
        const { findByTestId } = renderAt('/slips');
        const focusSpy = vi.fn();
        const probe = document.createElement('button');
        probe.setAttribute('data-shortcut-target', '');
        probe.focus = focusSpy;
        // N handler queries [data-shortcut-target] after navigation — inject ours
        document.body.appendChild(probe);
        ctrlKey('n');
        expect(await findByTestId('location')).toHaveTextContent('/builder');
        await new Promise((r) => setTimeout(r, 0));
        expect(focusSpy).toHaveBeenCalled();
        probe.remove();
    });

    it('unregistered actions are safe no-ops', () => {
        renderAt('/');
        expect(() => ctrlKey('r')).not.toThrow();
    });
});
