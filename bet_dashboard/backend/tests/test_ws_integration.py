"""WebSocket/TickerService integration tests (issue #60, cycle 4) — REAL stack.

Unlike cycle 3 (broadcast_capture fixture), this file verifies REAL propagation:
TestClient portal loop bound to ws_manager via a lifespan mirroring main.py,
real daemon threads calling broadcast_sync (run_coroutine_threadsafe), and real
WS clients receiving JSON frames through the actual /ws endpoint in
routers/system.py. The final test builds a REAL AppLogic (tmp DBs/config) and
drives the services router end-to-end.

Thread safety: WebSocketTestSession.receive is a BLOCKING portal call with no
timeout, so every receive is wrapped in a watchdog executor with result(timeout)
— a wedged receive fails loudly instead of hanging the suite.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import pytest

from core.ws import ws_manager
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import services, system


# ── Watchdog receive: never block the suite on a wedged portal call ──────────


_RECEIVE_POOL = ThreadPoolExecutor(max_workers=4)


def receive_with_timeout(ws, seconds=3.0):
    """Blocking receive guarded by result(timeout); a wedge becomes a failure."""
    future = _RECEIVE_POOL.submit(ws.receive_text)
    try:
        return future.result(timeout=seconds)
    except TimeoutError:
        raise AssertionError("no WS message within %ss" % seconds) from None

# ── App harness: lifespan binds portal loop to ws_manager (mirrors main.py) ──


@asynccontextmanager
async def _bind_ws_loop(app: FastAPI):
    ws_manager.set_loop(asyncio.get_event_loop())
    yield


def make_ws_app(app_logic=None) -> FastAPI:
    """Fresh app with ONLY the routers under test + loop-binding lifespan."""
    app = FastAPI()
    app.router.lifespan_context = _bind_ws_loop
    if app_logic is not None:
        app.state.app_logic = app_logic
    app.include_router(system.router)
    app.include_router(services.router)
    return app


@pytest.fixture()
def clean_ws_manager():
    """Singleton hygiene: snapshot + restore connections and loop binding."""
    saved_connections = list(ws_manager._connections)
    saved_loop = ws_manager._loop
    yield ws_manager
    ws_manager._connections[:] = saved_connections
    ws_manager.set_loop(saved_loop)


@pytest.fixture()
def ws_client(clean_ws_manager):
    """TestClient whose portal loop is bound to ws_manager at startup."""
    with TestClient(make_ws_app()) as client:
        yield client

# ── Bounded wait helper (deadline poll on observable condition) ──────────────


def wait_for(condition, timeout=2.0, step=0.01):
    """Poll until condition() is truthy or deadline. Bounded, 10ms steps."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(step)
    return condition()


EVENT_PAYLOADS = [
    ("slips_updated", {"event": "slips_updated", "timestamp": "2030-01-01T10:00:00", "live_data": {"n": 1}}),
    ("matches_updated", {"event": "matches_updated", "timestamp": "2030-01-01T09:00"}),
    ("service_toggled", {"event": "service_toggled", "name": "puller", "enabled": False, "timestamp": "2030-01-01T10:00:00"}),
]


# ── /ws endpoint lifecycle through the real endpoint ─────────────────────────


class TestWsEndpointLifecycle:
    def test_connect_registers_exit_deregisters(self, ws_client):
        """[P1] Real /ws endpoint: connect adds to ws_manager, exit removes."""
        before = len(ws_manager._connections)
        with ws_client.websocket_connect("/ws"):
            assert wait_for(condition=lambda: len(ws_manager._connections) == before + 1), \
                "connect did not register with ws_manager"
        assert wait_for(condition=lambda: len(ws_manager._connections) == before), \
            "exit did not deregister from ws_manager"

    def test_ping_pong_keepalive_still_works_with_bound_loop(self, ws_client):
        """[P2] Keepalive protocol unaffected by loop binding (regression guard)."""
        with ws_client.websocket_connect("/ws") as ws:
            ws.send_text("ping")
            assert receive_with_timeout(ws) == '{"event":"pong"}'


# ── Daemon-thread broadcast → real WS client (the broadcast_sync contract) ──


class TestDaemonThreadBroadcastDelivery:
    @pytest.mark.parametrize(
        "event_name,payload",
        EVENT_PAYLOADS,
        ids=[name for name, _ in EVENT_PAYLOADS],
    )
    def test_daemon_thread_broadcast_delivers_event(self, ws_client, event_name, payload):
        """[P0] All three event types reach a connected client when broadcast
        from a daemon thread via broadcast_sync (run_coroutine_threadsafe)."""
        with ws_client.websocket_connect("/ws") as ws:
            assert wait_for(condition=lambda: len(ws_manager._connections) > 0)
            worker = threading.Thread(target=ws_manager.broadcast_sync, args=(payload,), daemon=True)
            worker.start()
            worker.join(timeout=2)
            received = json.loads(receive_with_timeout(ws, seconds=5.0))
            assert received == payload

    def test_multiple_clients_receive_same_broadcast(self, ws_client):
        """[P0] Two connected clients both receive one daemon-thread broadcast."""
        payload = {"event": "matches_updated", "timestamp": "2030-01-01T09:00"}
        with ws_client.websocket_connect("/ws") as first, ws_client.websocket_connect("/ws") as second:
            assert wait_for(condition=lambda: len(ws_manager._connections) >= 2)
            worker = threading.Thread(target=ws_manager.broadcast_sync, args=(payload,), daemon=True)
            worker.start()
            worker.join(timeout=2)
            assert json.loads(receive_with_timeout(first, seconds=5.0)) == payload
            assert json.loads(receive_with_timeout(second, seconds=5.0)) == payload

# ── RealTicker daemon thread → broadcast_sync → real WS client ───────────────


class TestRealTickerToWsPropagation:
    def test_real_ticker_thread_broadcasts_reach_ws_client(self, ws_client):
        """[P0] Full push path with REAL moving parts: TickerService daemon
        thread (0.05s) → broadcast_sync → run_coroutine_threadsafe → portal
        loop → real WS client queue. Two consecutive heartbeats prove sustained
        propagation, not a one-shot fluke."""
        from core.ticker_service import TickerService

        state = {"seq": 0}
        lock = threading.Lock()

        def on_tick():
            with lock:
                state["seq"] += 1
                seq = state["seq"]
            ws_manager.broadcast_sync({"event": "ticker_heartbeat", "seq": seq})

        svc = TickerService("ws-ticker", on_tick, interval=0.05)
        try:
            with ws_client.websocket_connect("/ws") as ws:
                assert wait_for(condition=lambda: len(ws_manager._connections) > 0)
                first = json.loads(receive_with_timeout(ws, seconds=5.0))
                second = json.loads(receive_with_timeout(ws, seconds=5.0))
                assert first["event"] == "ticker_heartbeat"
                assert second["event"] == "ticker_heartbeat"
                assert second["seq"] > first["seq"]  # sustained, ordered delivery
        finally:
            svc.set_enabled(False)  # park the daemon


# ── REAL AppLogic + services router → ws_manager → real WS client (e2e) ─────


class TestAppLogicToggleE2E:
    def test_real_applogic_toggle_broadcasts_service_toggled(self, tmp_path, monkeypatch, clean_ws_manager):
        """[P0] End-to-end wiring: real AppLogic (real TickerServices, tmp DBs,
        throwaway config) + POST /api/services/puller/toggle → router →
        AppLogic.toggle_service → ws_manager.broadcast_sync → real WS client.

        The 3 spawned services tick at 300/300/60s — none can fire inside this
        test window, so the ONLY broadcast the client can receive is the toggle
        event itself. Teardown parks all three services.
        """
        from core.logic import AppLogic
        from logic_test_helpers import make_match_row_db, seed_matches_db, write_config

        config_dir = tmp_path / "config"
        write_config(config_dir)  # services.yaml with neutral toggles: {}
        matches_db = str(tmp_path / "matches.db")
        slips_db = str(tmp_path / "slips.db")
        seed_matches_db(matches_db, [make_match_row_db(0)])  # proven cycle-3 construction sequence

        app_logic = AppLogic(matches_db, slips_db, str(config_dir))
        try:
            with (
                TestClient(make_ws_app(app_logic=app_logic)) as client,
                client.websocket_connect("/ws") as ws,
            ):
                assert wait_for(condition=lambda: len(ws_manager._connections) > 0)
                response = client.post("/api/services/puller/toggle")
                assert response.status_code == 200
                assert response.json() == {"name": "puller", "enabled": False}
                received = json.loads(receive_with_timeout(ws, seconds=5.0))
                assert received["event"] == "service_toggled"
                assert received["name"] == "puller"
                assert received["enabled"] is False
        finally:
            for svc in app_logic.services.values():
                svc.set_enabled(False)  # park all real daemons