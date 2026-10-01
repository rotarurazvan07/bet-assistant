"""[P0] API tests for the services router (issue #58).

Deterministic time control: services._next_run_hour is wall-clock driven;
tests monkeypatch routers.services.datetime to a fixed value so the
Today/Tomorrow branches are stable.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import routers.services as services_module
from conftest import FakeDashboardLogic, make_test_client

BASE = "/api/services"
FIXED_NOW = datetime(2030, 6, 15, 10, 0, 0)


@pytest.fixture()
def services_client():
    from core.logic import AppLogic

    mock = MagicMock(spec=AppLogic)
    mock.logic = FakeDashboardLogic()
    # services router reads app.settings (AppLogic property), not app.logic.settings —
    # bind it to the fake's settings facade so per-test _settings mutations are visible.
    mock.settings = mock.logic.settings
    mock.services = {
        "puller": SimpleNamespace(enabled=True, is_alive=lambda: True, interval=300),
        "generator": SimpleNamespace(enabled=False, is_alive=lambda: False, interval=300),
        "verifier": SimpleNamespace(enabled=True, is_alive=lambda: True, interval=60),
    }
    tc, _ = make_test_client(app_mock=mock)
    return tc, mock


@pytest.fixture()
def frozen_clock(monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return FIXED_NOW

    monkeypatch.setattr(services_module, "datetime", FrozenDatetime)


class TestGetServices:
    """[P0] GET /api/services"""

    def test_services_envelope_shape(self, services_client):
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert set(data) == {"services", "generate_hour", "generate_minute", "server_time"}

    def test_generator_next_run_today_when_hour_ahead(self, services_client, frozen_clock):
        tc, mock = services_client
        mock.logic._settings["services"]["generate_hour"] = 12
        mock.logic._settings["services"]["generate_minute"] = 0
        nxt = tc.get(BASE).json()["services"]["generator"]["next_run"]
        assert nxt.startswith("Today 12:00")
        assert "2h" in nxt

    def test_generator_next_run_tomorrow_when_hour_passed(self, services_client, frozen_clock):
        tc, mock = services_client
        mock.logic._settings["services"]["generate_hour"] = 8
        mock.logic._settings["services"]["generate_minute"] = 0
        assert tc.get(BASE).json()["services"]["generator"]["next_run"].startswith("Tomorrow 08:00")

    def test_interval_services_label_every_n_minutes(self, services_client):
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert data["services"]["puller"]["next_run"] == "Every 5 min"
        assert data["services"]["verifier"]["next_run"] == "Every 1 min"

    def test_service_fields_contract(self, services_client):
        tc, _ = services_client
        svc = tc.get(BASE).json()["services"]["puller"]
        expected_keys = (
            "name", "description", "enabled", "alive", "hour", "minute",
            "interval_seconds", "next_run", "last_time_generated",
        )
        for key in expected_keys:
            assert key in svc
        assert svc["description"]

    def test_generator_last_time_generated_from_runtime_state(self, services_client):
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert data["services"]["generator"]["last_time_generated"] == "2030-01-01T08:30:00"
        assert data["services"]["puller"]["last_time_generated"] is None

    def test_generate_hour_minute_echoed_from_config(self, services_client):
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert data["generate_hour"] == 8
        assert data["generate_minute"] == 30

    def test_unknown_service_next_run_unknown(self, services_client):
        tc, mock = services_client
        mock.services["mystery"] = SimpleNamespace(enabled=True, is_alive=lambda: True, interval=None)
        assert tc.get(BASE).json()["services"]["mystery"]["next_run"] == "Unknown"

    def test_no_services_config_defaults_generate_hour(self, services_client):
        tc, mock = services_client
        mock.logic._settings["services"] = {}
        data = tc.get(BASE).json()
        assert data["generate_hour"] == 8
        assert data["generate_minute"] == 0

    def test_descriptions_known_services(self, services_client):
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert data["services"]["puller"]["description"].startswith("Checks every 5 minutes")
        assert data["services"]["verifier"]["description"].startswith("Polls every 60 seconds")

class TestNextRunHourUnit:
    """[P1] _next_run_hour/_next_run_interval pure unit coverage."""

    def test_none_hour_returns_none(self):
        assert services_module._next_run_hour(None) is None

    def test_none_interval_returns_none(self):
        assert services_module._next_run_interval(None) is None

    def test_interval_minutes_floor_division(self):
        assert services_module._next_run_interval(90) == "Every 1 min"
        assert services_module._next_run_interval(3600) == "Every 60 min"

    def test_hour_with_none_minute_defaults_zero(self, frozen_clock):
        label = services_module._next_run_hour(23, None)
        assert label.startswith("Today 23:00")


class TestSaveSettings:
    """[P0] POST /api/services/settings"""

    def test_save_settings_persists_via_logic(self, services_client):
        tc, mock = services_client
        r = tc.post(f"{BASE}/settings", json={"generate_hour": 9, "generate_minute": 15})
        assert r.status_code == 200
        assert r.json() == {"generate_hour": 9, "generate_minute": 15}
        mock.save_service_settings.assert_called_once_with(9, 15)

    def test_save_settings_missing_hour_returns_422(self, services_client):
        tc, _ = services_client
        assert tc.post(f"{BASE}/settings", json={"generate_minute": 15}).status_code == 422

    def test_save_settings_defaults_minute_zero(self, services_client):
        tc, mock = services_client
        tc.post(f"{BASE}/settings", json={"generate_hour": 7})
        mock.save_service_settings.assert_called_once_with(7, 0)


class TestToggleService:
    """[P0] POST /api/services/{name}/toggle — includes WS broadcast contract."""

    def test_toggle_returns_new_state(self, services_client):
        tc, mock = services_client
        mock.toggle_service.return_value = False
        r = tc.post(f"{BASE}/puller/toggle")
        assert r.status_code == 200
        assert r.json() == {"name": "puller", "enabled": False}
        mock.toggle_service.assert_called_once_with("puller")

    def test_toggle_unknown_service_returns_enabled_false(self, services_client):
        tc, mock = services_client
        mock.toggle_service.return_value = False
        assert tc.post(f"{BASE}/ghost/toggle").json() == {"name": "ghost", "enabled": False}

    def test_toggle_broadcasts_service_toggled_event(self, services_client, broadcast_capture):
        """Contract: toggling must notify WS clients with service_toggled payload."""
        import core.ws as ws_module

        tc, mock = services_client

        def toggle_side_effect(name):
            ws_module.ws_manager.broadcast_sync(
                {"event": "service_toggled", "name": name, "enabled": False, "timestamp": "2030-01-01T00:00:00"}
            )
            return False

        mock.toggle_service.side_effect = toggle_side_effect
        tc.post(f"{BASE}/puller/toggle")
        assert len(broadcast_capture) == 1
        payload = broadcast_capture[0]
        assert payload["event"] == "service_toggled"
        assert payload["name"] == "puller"
        assert payload["enabled"] is False
        assert "timestamp" in payload
