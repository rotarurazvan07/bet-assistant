// FloatingSlipBuilder (issue #64 P1 + #39 mobile sheet). ACTUAL: portal
// wrapper — minimized shows 'N leg(s) • totalOdds' + ▲; expanded renders
// SlipBuilderPanel. #39 adds the mobile SwipeableDrawer bottom sheet + drag
// handle, snap 50/90, desktop Unstable_TrapFocus, keyboard + a11y fixes.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FloatingSlipBuilder from '../FloatingSlipBuilder';
import { makeCandidateLeg } from '../../test/factories';

// AC-01: drive MUI useMediaQuery through matchMedia (no module mocking —
// a partial @mui/material mock would leak across shared vitest workers).
function setMobile(mobile: boolean) {
    Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: (query: string) => ({
            matches: mobile
                ? query.includes('max-width:767.95px')
                : !query.includes('max-width:767.95px'),
            media: query,
            onchange: null,
            addListener() { /* noop */ },
            removeListener() { /* noop */ },
            addEventListener() { /* noop */ },
            removeEventListener() { /* noop */ },
            dispatchEvent() { return false; },
        }),
    });
}

function legs(n: number) {
    return Array.from({ length: n }, (_, i) => makeCandidateLeg({ odds: 1.5 + i, match_name: `Match ${i + 1}` }));
}

function renderBuilder(overrides: Partial<Parameters<typeof FloatingSlipBuilder>[0]> = {}) {
    const defaults: Parameters<typeof FloatingSlipBuilder>[0] = {
        legs: legs(2),
        onRemoveLeg: () => {},
        onSubmit: () => {},
        isMinimized: false,
        onToggleMinimize: () => {},
    };
    return render(<FloatingSlipBuilder {...defaults} {...overrides} />);
}

const originalMatchMedia = window.matchMedia;

beforeEach(() => {
    setMobile(false);
    localStorage.clear();
});

afterEach(() => {
    Object.defineProperty(window, 'matchMedia', { writable: true, value: originalMatchMedia });
});

describe('FloatingSlipBuilder', () => {
    it('minimized: renders leg count + totalOdds + expand arrow in portal', () => {
        renderBuilder({ legs: legs(2), isMinimized: true });
        expect(screen.getByText('2 legs')).toBeInTheDocument();
        expect(screen.getByText(/3\.75/)).toBeInTheDocument();
        expect(screen.getByText('▲')).toBeInTheDocument();
    });

    it('minimized: singular leg text', () => {
        renderBuilder({ legs: legs(1), isMinimized: true });
        expect(screen.getByText('1 leg')).toBeInTheDocument();
    });

    it('minimized: click expands via onToggleMinimize', async () => {
        const user = userEvent.setup();
        const onToggleMinimize = vi.fn();
        renderBuilder({ legs: legs(2), isMinimized: true, onToggleMinimize });
        await user.click(screen.getByText('▲'));
        expect(onToggleMinimize).toHaveBeenCalledTimes(1);
    });

    it('minimized: hides totalOdds when zero valid legs', () => {
        renderBuilder({ legs: [makeCandidateLeg({ odds: 0 })], isMinimized: true });
        expect(screen.getByText('1 leg')).toBeInTheDocument();
        expect(screen.queryByText(/•/)).not.toBeInTheDocument();
    });

    it('expanded: renders the full SlipBuilderPanel', () => {
        renderBuilder({ legs: legs(2) });
        expect(screen.getByText('Slip Builder')).toBeInTheDocument();
        expect(screen.getByText('2 legs selected')).toBeInTheDocument();
    });

    it('expanded: Add Slip fires through to onSubmit', async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn();
        renderBuilder({ legs: legs(1), onSubmit });
        await user.click(screen.getByText('Add Slip'));
        expect(onSubmit).toHaveBeenCalledWith(1);
    });
});

describe('FloatingSlipBuilder #39 mobile bottom sheet', () => {
    it('AC-01: mobile expanded renders a bottom sheet with a drag handle', () => {
        setMobile(true);
        renderBuilder({ legs: legs(2) });
        expect(screen.getByRole('button', { name: 'Resize slip sheet' })).toBeInTheDocument();
        expect(window.document.querySelector('.floating-slip-panel')).not.toBeNull();
    });

    it('AC-02: handle click toggles snap 50 -> 90 and persists slip-sheet-snap', async () => {
        setMobile(true);
        const user = userEvent.setup();
        renderBuilder({ legs: legs(1) });
        const paper = window.document.querySelector('.floating-slip-panel') as HTMLElement;
        expect(paper).toHaveStyle({ height: '50dvh' });
        await user.click(screen.getByRole('button', { name: 'Resize slip sheet' }));
        expect(paper).toHaveStyle({ height: '90dvh' });
        expect(localStorage.getItem('slip-sheet-snap')).toBe('90');
        await user.click(screen.getByRole('button', { name: 'Resize slip sheet' }));
        expect(paper).toHaveStyle({ height: '50dvh' });
    });

    it('AC-08: snap restores from slip-sheet-snap', () => {
        setMobile(true);
        localStorage.setItem('slip-sheet-snap', '90');
        renderBuilder({ legs: legs(1) });
        const paper = window.document.querySelector('.floating-slip-panel') as HTMLElement;
        expect(paper).toHaveStyle({ height: '90dvh' });
    });

    it('AC-03: desktop keeps the .floating-slip-panel panel, no sheet handle', () => {
        renderBuilder({ legs: legs(1) });
        expect(window.document.querySelector('.floating-slip-panel')).not.toBeNull();
        expect(screen.queryByRole('button', { name: 'Resize slip sheet' })).not.toBeInTheDocument();
    });

    it('AC-13/AC-06: panel is a named dialog wrapped in the MUI focus trap', () => {
        renderBuilder({ legs: legs(1) });
        expect(screen.getByRole('dialog', { name: 'Slip Builder' })).toBeInTheDocument();
        // AC-06 smoke: TrapFocus mounts its tab sentinels around the panel.
        expect(window.document.querySelector('[data-testid="sentinelStart"]')).not.toBeNull();
        expect(window.document.querySelector('[data-testid="sentinelEnd"]')).not.toBeNull();
    });

    it('AC-13: minimized pill is a keyboard button using --text-muted-strong', () => {
        setMobile(true);
        renderBuilder({ legs: legs(2), isMinimized: true });
        expect(screen.getByRole('button', { name: /Open slip builder, 2 legs/ })).toBeInTheDocument();
        expect(screen.getByText('▲').style.color).toBe('var(--text-muted-strong)');
    });

    it('AC-04: Ctrl+Enter submits with current units when expanded', async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn();
        renderBuilder({ legs: legs(1), onSubmit });
        await user.keyboard('{Control>}{Enter}{/Control}');
        expect(onSubmit).toHaveBeenCalledWith(1);
    });

    it('AC-04: Ctrl+Enter on an empty slip is a no-op (no onSubmit, no alert)', async () => {
        const user = userEvent.setup();
        const onSubmit = vi.fn();
        const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
        renderBuilder({ legs: [], onSubmit });
        await user.keyboard('{Control>}{Enter}{/Control}');
        expect(onSubmit).not.toHaveBeenCalled();
        expect(alertSpy).not.toHaveBeenCalled();
        alertSpy.mockRestore();
    });

    it('AC-05: Escape minimizes when expanded', async () => {
        const user = userEvent.setup();
        const onToggleMinimize = vi.fn();
        renderBuilder({ legs: legs(1), onToggleMinimize });
        await user.keyboard('{Escape}');
        expect(onToggleMinimize).toHaveBeenCalledTimes(1);
    });
});
