// Test setup for Vitest (issue #63, cycle 9).
// Loads jest-dom matchers, polyfills browser APIs missing in jsdom 30,
// and installs the MSW server lifecycle hooks.

import '@testing-library/jest-dom/vitest';
import { afterEach, beforeAll, afterAll, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import { server } from './handlers';

// ── jsdom polyfills ──────────────────────────────────────────────────────────

// MUI useMediaQuery + responsive components.
if (!window.matchMedia) {
    const matchMediaMock = (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener() { /* noop */ },
        removeListener() { /* noop */ },
        addEventListener() { /* noop */ },
        removeEventListener() { /* noop */ },
        dispatchEvent() { return false; },
    });
    Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: matchMediaMock,
    });
}

// Recharts + MUI transitions observe element sizes.
class ResizeObserverMock {
    observe() { /* noop */ }
    unobserve() { /* noop */ }
    disconnect() { /* noop */ }
}
if (!window.ResizeObserver) {
    Object.defineProperty(window, 'ResizeObserver', {
        writable: true,
        value: ResizeObserverMock,
    });
}

// Lazy-mounted widgets (MUI x-date-pickers popovers).
class IntersectionObserverMock {
    readonly root = null;
    readonly rootMargin = '';
    readonly thresholds: ReadonlyArray<number> = [];
    observe() { /* noop */ }
    unobserve() { /* noop */ }
    disconnect() { /* noop */ }
    takeRecords() { return []; }
}
if (!window.IntersectionObserver) {
    Object.defineProperty(window, 'IntersectionObserver', {
        writable: true,
        value: IntersectionObserverMock,
    });
}

// useSocket guards against missing-WS environments. Node 22 ships a global
// WebSocket; jsdom 30 also exposes one — the guard exists for CI runners where
// either may be absent. We only define the mock if none exists.
if (typeof globalThis.WebSocket === 'undefined') {
    class WebSocketMock {
        static readonly CONNECTING = 0;
        static readonly OPEN = 1;
        static readonly CLOSING = 2;
        static readonly CLOSED = 3;
        readonly readyState = WebSocketMock.CLOSED;
        onopen: ((ev?: unknown) => void) | null = null;
        onmessage: ((ev: unknown) => void) | null = null;
        onclose: ((ev?: unknown) => void) | null = null;
        onerror: ((ev?: unknown) => void) | null = null;
        send() { /* noop */ }
        close() { /* noop */ }
    }
    Object.defineProperty(globalThis, 'WebSocket', {
        writable: true,
        value: WebSocketMock,
    });
}

// jsdom does not implement Element.scrollIntoView; BettingTips calls it on
// pagination (topRef.current?.scrollIntoView). Without a stub the rejection
// leaks AFTER the test completes and vitest exits non-zero on unhandled
// errors even when all tests pass. Standard practice: unconditional no-op.
// (Grep verified scrollIntoView is the ONLY scroll/focus API the pages use.)
Element.prototype.scrollIntoView = vi.fn();

// ── MSW lifecycle ────────────────────────────────────────────────────────────

// Establish MSW before all tests; reset request-capture state between tests
// (keeps handlers); restore pristine interceptors after the whole run.
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => {
    server.resetHandlers();
    cleanup(); // RTL unmount — MUI renders outside React trees (portals)
});
afterAll(() => server.close());
