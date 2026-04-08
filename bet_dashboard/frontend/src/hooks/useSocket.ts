import { useEffect, useRef, useCallback } from 'react';
import type { WsEvent, WsEventName } from '../types';

type Handlers = Partial<Record<WsEventName, (ev: WsEvent) => void>>;

const RECONNECT_DELAY_MS = 3_000;
const PING_INTERVAL_MS = 25_000;

/**
 * useSocket — connects to /ws and dispatches named events to handlers.
 *
 * The hook keeps a single WebSocket per mount and auto-reconnects on close.
 * A periodic ping keeps the connection alive through proxies.
 *
 * Events emitted by the backend:
 *   matches_updated  → refetch matches only
 *   slips_updated    → refetch slips + analytics
 *   service_toggled  → refetch services
 */
export function useSocket(handlers: Handlers) {
    const wsRef = useRef<WebSocket | null>(null);
    const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const mountedRef = useRef(true);
    // Use a ref for handlers so the reconnect closure doesn't go stale.
    const handlersRef = useRef(handlers);
    useEffect(() => { handlersRef.current = handlers; });

    const connect = useCallback(() => {
        if (!mountedRef.current) return;

        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
        wsRef.current = ws;

        ws.onopen = () => {
            pingRef.current = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) ws.send('ping');
            }, PING_INTERVAL_MS);
        };

        ws.onmessage = (e) => {
            try {
                const ev: WsEvent = JSON.parse(e.data);
                const handler = handlersRef.current[ev.event];
                if (handler) handler(ev);
            } catch { /* ignore malformed frames */ }
        };

        ws.onclose = () => {
            if (pingRef.current) clearInterval(pingRef.current);
            if (mountedRef.current) setTimeout(connect, RECONNECT_DELAY_MS);
        };

        ws.onerror = () => {
            // Only close if the connection was actually open or connecting
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
                ws.close();
            }
        };
    }, []);

    useEffect(() => {
        mountedRef.current = true;
        connect();
        return () => {
            mountedRef.current = false;
            if (pingRef.current) clearInterval(pingRef.current);
            const ws = wsRef.current;
            // Only close if the connection was actually established or connecting
            if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
                ws.close();
            }
        };
    }, [connect]);
}
