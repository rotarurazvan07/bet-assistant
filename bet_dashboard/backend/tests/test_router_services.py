"""[P0] API tests for the services router (issue #58).

Deterministic time control: services._next_run_hour is wall-clock driven;
tests monkeypatch routers.services.datetime to a fixed value so the
Today/Tomorrow branches are stable.
"""

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
    mock.get_profile_schedules.return_value = []
    mock.services = {
        "puller": SimpleNamespace(enabled=True, is_alive=lambda: True, interval=300),
        "generator": SimpleNamespace(enabled=False, is_alive=lambda: False, interval=300),
        "verifier": SimpleNamespace(enabled=True, is_alive=lambda: True, interval=60),
    }
    tc, _ = make_test_client(app_mock=mock)
    return tc, mock


@pytest.fixture()
def frozen_clock(monkeypatch) -> None:
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return FIXED_NOW

    monkeypatch.setattr(services_module, "datetime", FrozenDatetime)


class TestGetServices:
    """[P0] GET /api/services"""

    def test_services_envelope_shape(self, services_client) -> None:
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert set(data) == {
            "services",
            "profile_schedules",
            "server_time",
        }

    def test_generator_next_run_earliest_profile_window_today(self, services_client, frozen_clock) -> None:
        tc, mock = services_client
        mock.get_profile_schedules.return_value = [
            {"name": "late", "auto_generate": True, "generate_hour": 12, "generate_minute": 0},
            {"name": "early", "auto_generate": True, "generate_hour": 11, "generate_minute": 0},
        ]
        nxt = tc.get(BASE).json()["services"]["generator"]["next_run"]
        assert nxt.startswith("Today 11:00")
        assert "1h" in nxt


    def test_generator_next_run_none_without_any_window(self, services_client, frozen_clock) -> None:
        tc, mock = services_client
        mock.get_profile_schedules.return_value = [
            {"name": "legacy", "auto_generate": True, "generate_hour": None, "generate_minute": None},
            {"name": "off", "auto_generate": False, "generate_hour": 6, "generate_minute": 0},
        ]
        assert tc.get(BASE).json()["services"]["generator"]["next_run"] is None

    def test_generator_next_run_tomorrow_when_window_passed(self, services_client, frozen_clock) -> None:
        tc, mock = services_client
        mock.get_profile_schedules.return_value = [
            {"name": "early", "auto_generate": True, "generate_hour": 8, "generate_minute": 0},
        ]
        assert tc.get(BASE).json()["services"]["generator"]["next_run"].startswith("Tomorrow 08:00")


    def test_interval_services_label_every_n_minutes(self, services_client) -> None:
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert data["services"]["puller"]["next_run"] == "Every 5 min"
        assert data["services"]["verifier"]["next_run"] == "Every 1 min"

    def test_service_fields_contract(self, services_client) -> None:
        tc, _ = services_client
        svc = tc.get(BASE).json()["services"]["puller"]
        expected_keys = (
            "name",
            "description",
            "enabled",
            "alive",
            "hour",
            "minute",
            "interval_seconds",
            "next_run",
            "last_time_generated",
        )
        for key in expected_keys:
            assert key in svc
        assert svc["description"]

    def test_generator_last_time_generated_from_runtime_state(self, services_client) -> None:
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert data["services"]["generator"]["last_time_generated"] == "2030-01-01T08:30:00"
        assert data["services"]["puller"]["last_time_generated"] is None

    def test_unknown_service_next_run_unknown(self, services_client) -> None:
        tc, mock = services_client
        mock.services["mystery"] = SimpleNamespace(enabled=True, is_alive=lambda: True, interval=None)
        assert tc.get(BASE).json()["services"]["mystery"]["next_run"] == "Unknown"

    def test_no_services_config_omits_global_hour(self, services_client) -> None:
        tc, mock = services_client
        mock.logic._settings["services"] = {}
        data = tc.get(BASE).json()
        assert "generate_hour" not in data
        assert "generate_minute" not in data
        assert data["services"]["verifier"]["next_run"] == "Every 1 min"

    def test_descriptions_known_services(self, services_client) -> None:
        tc, _ = services_client
        data = tc.get(BASE).json()
        assert data["services"]["puller"]["description"].startswith("Checks every 5 minutes")
        assert data["services"]["verifier"]["description"].startswith("Polls every 60 seconds")


class TestNextRunHourUnit:
    """[P1] _next_run_hour/_next_run_interval pure unit coverage."""

    def test_none_hour_returns_none(self) -> None:
        assert services_module._next_run_hour(None) is None

    def test_none_interval_returns_none(self) -> None:
        assert services_module._next_run_interval(None) is None

    def test_interval_minutes_floor_division(self) -> None:
        assert services_module._next_run_interval(90) == "Every 1 min"
        assert services_module._next_run_interval(3600) == "Every 60 min"

    def test_hour_with_none_minute_defaults_zero(self, frozen_clock) -> None:
        label = services_module._next_run_hour(23, None)
        assert label.startswith("Today 23:00")


class TestSaveSettings:
    """[P0] POST /api/services/settings"""

    def test_save_settings_persists_profile_schedules_only(self, services_client) -> None:
        tc, mock = services_client
        rows = [{"name": "low", "auto_generate": True, "generate_hour": 9, "generate_minute": 15}]
        r = tc.post(f"{BASE}/settings", json={"profile_schedules": rows})
        assert r.status_code == 200
        echoed = r.json()["profile_schedules"][0]
        assert {k: echoed[k] for k in rows[0]} == rows[0]
        sent = mock.save_profile_schedules.call_args[0][0]
        assert sent[0]["name"] == "low" and sent[0]["generate_hour"] == 9

    def test_save_settings_legacy_hour_only_body_rejected(self, services_client) -> None:
        tc, mock = services_client
        r = tc.post(f"{BASE}/settings", json={"generate_hour": 9, "generate_minute": 15})
        assert r.status_code == 422
        mock.save_profile_schedules.assert_not_called()

    def test_save_settings_empty_body_rejected(self, services_client) -> None:
        tc, _ = services_client
        assert tc.post(f"{BASE}/settings", json={}).status_code == 422


class TestToggleService:
    """[P0] POST /api/services/{name}/toggle — includes WS broadcast contract."""

    def test_toggle_returns_new_state(self, services_client) -> None:
        tc, mock = services_client
        mock.toggle_service.return_value = False
        r = tc.post(f"{BASE}/puller/toggle")
        assert r.status_code == 200
        assert r.json() == {"name": "puller", "enabled": False}
        mock.toggle_service.assert_called_once_with("puller")

    def test_toggle_unknown_service_returns_enabled_false(self, services_client) -> None:
        tc, mock = services_client
        mock.toggle_service.return_value = False
        assert tc.post(f"{BASE}/ghost/toggle").json() == {
            "name": "ghost",
            "enabled": False,
        }

    def test_toggle_broadcasts_service_toggled_event(self, services_client, broadcast_capture) -> None:
        """Contract: toggling must notify WS clients with service_toggled payload."""
        import core.ws as ws_module

        tc, mock = services_client

        def toggle_side_effect(name) -> bool:
            ws_module.ws_manager.broadcast_sync(
                {
                    "event": "service_toggled",
                    "name": name,
                    "enabled": False,
                    "timestamp": "2030-01-01T00:00:00",
                }
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
