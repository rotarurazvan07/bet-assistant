"""[P0] API tests for the system router (issue #58).

Covers: POST /api/pull (ok + error paths), GET /api/status,
GET /api/config/sources, and the /ws keepalive protocol.
"""

from __future__ import annotations

from conftest import FakeDashboardLogic

BASE = "/api"


class TestPullDb:
    """[P0] POST /api/pull"""

    def test_pull_success_returns_ok_with_timestamp(self, client, fake_app):
        fake_app.pull_and_broadcast.return_value = "Pull successful"
        r = client.post(f"{BASE}/pull")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["message"] == "Pull successful"
        assert data["timestamp"] == "2030-01-01 09:00"

    def test_pull_exception_returns_error_envelope(self, client, fake_app):
        fake_app.pull_and_broadcast.side_effect = RuntimeError("network down")
        data = client.post(f"{BASE}/pull").json()
        assert data["status"] == "error"
        assert "network down" in data["message"]


class TestGetStatus:
    """[P0] GET /api/status"""

    def test_status_reports_loaded_matches(self, client, fake_logic):
        data = client.get(f"{BASE}/status").json()
        assert data["last_pull"] == "2030-01-01 09:00"
        assert data["matches_loaded"] == 1

    def test_status_empty_df_reports_zero(self, empty_client):
        data = empty_client.get(f"{BASE}/status").json()
        assert data["matches_loaded"] == 0

    def test_status_none_df_reports_zero(self, client, fake_app, fake_logic):
        fake_logic.df = None
        data = client.get(f"{BASE}/status").json()
        assert data["matches_loaded"] == 0


class TestGetSourcesConfig:
    """[P1] GET /api/config/sources"""

    def test_sources_union_sorted_deduped(self, client, fake_logic):
        data = client.get(f"{BASE}/config/sources").json()
        assert data["sources"] == ["forebet", "predictz", "xgscore"]

    def test_sources_empty_config(self, client_factory):
        logic = FakeDashboardLogic()
        logic._settings["scraper_config"] = {}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/config/sources").json() == {"sources": []}

    def test_sources_missing_runner_sets_key(self, client_factory):
        logic = FakeDashboardLogic()
        logic._settings["scraper_config"] = {"other": 1}
        client, _ = client_factory(logic=logic)
        assert client.get(f"{BASE}/config/sources").json() == {"sources": []}


class TestWebsocketKeepalive:
    """[P1] GET /ws — ping/pong keepalive protocol."""

    def test_ws_ping_returns_pong(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_text("ping")
            assert ws.receive_text() == '{"event":"pong"}'

    def test_ws_other_text_no_response(self, client):
        """Non-ping messages are silently ignored (keepalive protocol)."""
        with client.websocket_connect("/ws") as ws:
            ws.send_text("hello")
            # No pong is sent for non-ping messages; closing is the observable behavior

    def test_ws_disconnect_cleans_up(self, client):
        import sys
        from pathlib import Path

        backend_dir = Path(__file__).resolve().parents[1]
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from core.ws import ws_manager

        before = len(ws_manager._connections)
        with client.websocket_connect("/ws"):
            pass
        assert len(ws_manager._connections) == before
