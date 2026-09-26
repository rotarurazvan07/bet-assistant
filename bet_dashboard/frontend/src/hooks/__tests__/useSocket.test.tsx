// useSocket tests (issue #66). SPEC DIVERGENCES (pinned, see summary D1-D4):
// - URL derives from window.location (ws/wss + host + /ws), NOT hardcoded
//   ws://localhost:8000/ws
// - Reconnect is FIXED 3s delay, NOT exponential backoff
// - The hook does NOT manage app state: it dispatches parsed events to a
//   caller-provided handler map via ref (event semantics live in App.tsx)
// - Extra real behaviors spec missed: 25s ping keepalive, onerror forces
//   close only when OPEN/CONNECTING, mounted-guard blocks post-unmount
//   reconnect, malformed frames silently ignored

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useSocket } from '../useSocket';


class MockWebSocket {
    static instances: MockWebSocket[] = [];
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
    CONNECTING = 0;
    OPEN = 1;
    CLOSING = 2;
    CLOSED = 3;
    url: string;
    sent: string[] = [];
    readyState = MockWebSocket.CONNECTING;
    onopen: (() => void) | null = null;
    onmessage: ((ev: { data: string }) => void) | null = null;
    onclose: (() => void) | null = null;
    onerror: (() => void) | null = null;
    constructor(url: string) {
        this.url = url;
        MockWebSocket.instances.push(this);
    }
    send(data: string) { this.sent.push(data); }
    close() { this.readyState = MockWebSocket.CLOSED; this.onclose?.(); }
    // test helpers
    simulateOpen() { this.readyState = MockWebSocket.OPEN; this.onopen?.(); }
    simulateMessage(data: string) { this.onmessage?.({ data }); }
    simulateClose() { this.readyState = MockWebSocket.CLOSED; this.onclose?.(); }
}


beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket);
});

afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
});


describe('useSocket', () => {
    it('connects to /ws URL derived from window.location (divergence: not hardcoded :8000)', () => {
        renderHook(() => useSocket({}));
        expect(MockWebSocket.instances).toHaveLength(1);
        // jsdom default location is http://localhost:3000/ — hook mirrors host
        expect(MockWebSocket.instances[0].url).toBe(`ws://${window.location.host}/ws`);
    });

    it('URL prefix follows location protocol scheme (jsdom pins http → ws)', () => {
        renderHook(() => useSocket({}));
        const url = MockWebSocket.instances[0].url;
        const expectedProto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        expect(url.startsWith(`${expectedProto}://`)).toBe(true);
        // NOTE: jsdom cannot redefine location.protocol (non-configurable),
        // so the https→wss branch is covered via the ternary pin above only —
        // documented as decision D21 in the cycle summary.
    });

    it('sends 25s keepalive pings while open', () => {
        renderHook(() => useSocket({}));
        const ws = MockWebSocket.instances[0];
        ws.simulateOpen();
        expect(ws.sent).toEqual([]);
        vi.advanceTimersByTime(25_000);
        expect(ws.sent).toEqual(['ping']);
        vi.advanceTimersByTime(25_000);
        expect(ws.sent).toEqual(['ping', 'ping']);
    });

    it('dispatches named events to handlers', () => {
        const handler = vi.fn();
        renderHook(() => useSocket({ matches_updated: handler }));
        const ws = MockWebSocket.instances[0];
        ws.simulateMessage(JSON.stringify({ event: 'matches_updated', timestamp: '2026-09-24T17:00:00' }));
        expect(handler).toHaveBeenCalledWith({ event: 'matches_updated', timestamp: '2026-09-24T17:00:00' });
    });

    it('ignores events with no registered handler', () => {
        const handler = vi.fn();
        renderHook(() => useSocket({ matches_updated: handler }));
        const ws = MockWebSocket.instances[0];
        ws.simulateMessage(JSON.stringify({ event: 'service_toggled' }));
        expect(handler).not.toHaveBeenCalled();
    });

    it('ignores malformed JSON frames without crashing', () => {
        const handler = vi.fn();
        renderHook(() => useSocket({ matches_updated: handler }));
        const ws = MockWebSocket.instances[0];
        expect(() => ws.simulateMessage('not-json{')).not.toThrow();
        expect(handler).not.toHaveBeenCalled();
    });

    it('reconnects after 3s on close (divergence: fixed delay, not exponential backoff)', () => {
        renderHook(() => useSocket({}));
        const first = MockWebSocket.instances[0];
        expect(MockWebSocket.instances).toHaveLength(1);
        first.simulateClose();
        vi.advanceTimersByTime(2_999);
        expect(MockWebSocket.instances).toHaveLength(1); // not yet
        vi.advanceTimersByTime(1);
        expect(MockWebSocket.instances).toHaveLength(2); // reconnected at exactly 3s
    });

    it('clears ping interval on close then pings again after reconnect', () => {
        renderHook(() => useSocket({}));
        const first = MockWebSocket.instances[0];
        first.simulateOpen();
        first.simulateClose();
        vi.advanceTimersByTime(3_000);
        const second = MockWebSocket.instances[1];
        second.simulateOpen();
        vi.advanceTimersByTime(25_000);
        expect(second.sent).toEqual(['ping']);
        expect(first.sent).toEqual([]); // old socket not pinged after close
    });

    it('onerror closes the socket only when OPEN/CONNECTING', () => {
        renderHook(() => useSocket({}));
        const ws = MockWebSocket.instances[0];
        const closeSpy = vi.spyOn(ws, 'close');
        ws.readyState = MockWebSocket.OPEN;
        ws.onerror?.();
        expect(closeSpy).toHaveBeenCalledTimes(1);
    });

    it('onerror does not close an already-CLOSED socket', () => {
        renderHook(() => useSocket({}));
        const ws = MockWebSocket.instances[0];
        ws.readyState = MockWebSocket.CLOSED;
        const closeSpy = vi.spyOn(ws, 'close');
        ws.onerror?.();
        expect(closeSpy).not.toHaveBeenCalled();
    });

    it('unmount cleanup: closes open socket and never reconnects', () => {
        const { unmount } = renderHook(() => useSocket({}));
        const ws = MockWebSocket.instances[0];
        ws.simulateOpen();
        unmount();
        expect(ws.readyState).toBe(MockWebSocket.CLOSED);
        vi.advanceTimersByTime(10_000);
        expect(MockWebSocket.instances).toHaveLength(1); // no reconnect after unmount
    });

    it('handler updates are visible without reconnecting (ref pattern)', () => {
        const first = vi.fn();
        const second = vi.fn();
        const { rerender } = renderHook(({ h }) => useSocket(h), { initialProps: { h: { matches_updated: first } } });
        const ws = MockWebSocket.instances[0];
        ws.simulateMessage(JSON.stringify({ event: 'matches_updated' }));
        expect(first).toHaveBeenCalledTimes(1);
        rerender({ h: { matches_updated: second } });
        ws.simulateMessage(JSON.stringify({ event: 'matches_updated' }));
        expect(first).toHaveBeenCalledTimes(1); // stale handler NOT called again
        expect(second).toHaveBeenCalledTimes(1); // fresh handler used
        expect(MockWebSocket.instances).toHaveLength(1); // no reconnect on rerender
    });
});
