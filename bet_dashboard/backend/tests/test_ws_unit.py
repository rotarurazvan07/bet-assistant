"""Unit tests for core/ws.py ConnectionManager (issue #60, cycle 4).

Covers: connect/disconnect bookkeeping, async broadcast with dead-connection
pruning, broadcast_sync no-op guards (loop unset / loop closed) and the REAL
run_coroutine_threadsafe path against a background asyncio event loop.

All tests use a FRESH ConnectionManager instance. The module-level ws_manager
singleton is exercised (and restored) by the integration suite instead.
"""

from __future__ import annotations

import asyncio
import json
import threading

import pytest

from core.ws import ConnectionManager


# ── Fake WebSocket ────────────────────────────────────────────────────────────


class FakeWebSocket:
    """Minimal async stand-in for starlette WebSocket (accept + send_text)."""

    def __init__(self, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[str] = []
        self.fail_on_send = fail_on_send
        self.first_send = threading.Event()

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        if self.fail_on_send:
            raise RuntimeError("connection is dead")
        self.sent.append(data)
        self.first_send.set()


@pytest.fixture()
def manager():
    return ConnectionManager()


def make_payload(event: str = "slips_updated", **extra) -> dict:
    payload = {"event": event, "timestamp": "2030-01-01T10:00:00"}
    payload.update(extra)
    return payload


# ── connect / disconnect ─────────────────────────────────────────────────────


class TestConnectDisconnect:
    def test_connect_awaits_accept_and_registers(self, manager):
        ws = FakeWebSocket()
        asyncio.run(manager.connect(ws))
        assert ws.accepted is True
        assert manager._connections == [ws]

    def test_disconnect_removes_registered_connection(self, manager):
        ws = FakeWebSocket()
        manager._connections.append(ws)
        manager.disconnect(ws)
        assert ws not in manager._connections

    def test_disconnect_unknown_connection_is_noop(self, manager):
        ws = FakeWebSocket()
        manager.disconnect(ws)
        assert manager._connections == []

    def test_disconnect_twice_is_idempotent(self, manager):
        ws = FakeWebSocket()
        manager._connections.append(ws)
        manager.disconnect(ws)
        manager.disconnect(ws)
        assert manager._connections == []


# ── async broadcast ──────────────────────────────────────────────────────────


class TestBroadcast:
    def test_broadcast_delivers_json_to_all_clients(self, manager):
        payload = make_payload("slips_updated", live_data={"n": 1})
        first, second = FakeWebSocket(), FakeWebSocket()
        manager._connections.extend([first, second])
        asyncio.run(manager.broadcast(payload))
        assert json.loads(first.sent[0]) == payload
        assert json.loads(second.sent[0]) == payload

    def test_broadcast_prunes_dead_connection_and_keeps_survivors(self, manager):
        dead = FakeWebSocket(fail_on_send=True)
        live = FakeWebSocket()
        manager._connections.extend([dead, live])
        asyncio.run(manager.broadcast(make_payload()))
        assert dead not in manager._connections
        assert manager._connections == [live]
        assert len(live.sent) == 1

    def test_broadcast_to_zero_clients_is_noop(self, manager):
        asyncio.run(manager.broadcast(make_payload()))
        assert manager._connections == []


# ── broadcast_sync: no-op guards ─────────────────────────────────────────────


class TestBroadcastSyncGuards:
    """[P0] broadcast_sync must be a silent no-op without a usable loop."""

    def test_set_loop_stores_loop_reference(self, manager):
        loop = asyncio.new_event_loop()
        try:
            manager.set_loop(loop)
            assert manager._loop is loop
        finally:
            loop.close()

    def test_broadcast_sync_noop_when_loop_unset(self, manager):
        manager.broadcast_sync(make_payload())  # _loop is None — must not raise
        assert manager._connections == []

    def test_broadcast_sync_noop_when_loop_closed(self, manager):
        loop = asyncio.new_event_loop()
        loop.close()
        manager.set_loop(loop)
        manager.broadcast_sync(make_payload())  # closed loop — must not raise
        assert manager._connections == []


# ── broadcast_sync: REAL run_coroutine_threadsafe path ─────────────────────


class BackgroundLoop:
    """Dedicated asyncio loop on a daemon thread — mirrors FastAPI lifespan.

    run_forever() alone binds execution to this loop object; no
    set_event_loop needed (run_coroutine_threadsafe targets the loop directly).
    """

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ws-test-loop")
        self._thread.start()
        assert self._ready.wait(timeout=5), "background loop failed to start"

    def _run(self) -> None:
        self._ready.set()
        self.loop.run_forever()

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)
        self.loop.close()


@pytest.fixture()
def bg_loop():
    bg = BackgroundLoop()
    yield bg
    bg.stop()


class TestBroadcastSyncRealPath:
    """[P0] Thread-safe broadcast: sync thread → run_coroutine_threadsafe → loop."""

    def test_broadcast_sync_delivers_via_run_coroutine_threadsafe(self, manager, bg_loop):
        manager.set_loop(bg_loop.loop)
        ws = FakeWebSocket()
        manager._connections.append(ws)
        manager.broadcast_sync(make_payload("service_toggled", name="puller", enabled=False))
        assert ws.first_send.wait(timeout=2), "broadcast never reached the FakeWebSocket"
        received = json.loads(ws.sent[0])
        assert received["event"] == "service_toggled"
        assert received["name"] == "puller"

    def test_broadcast_sync_multiple_clients_all_receive(self, manager, bg_loop):
        manager.set_loop(bg_loop.loop)
        first, second = FakeWebSocket(), FakeWebSocket()
        manager._connections.extend([first, second])
        manager.broadcast_sync(make_payload("matches_updated"))
        assert first.first_send.wait(timeout=2)
        assert second.first_send.wait(timeout=2)
        assert json.loads(first.sent[0]) == json.loads(second.sent[0])
