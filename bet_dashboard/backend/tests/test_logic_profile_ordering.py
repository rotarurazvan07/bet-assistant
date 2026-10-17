"""[P0] T4: profile generation ordering + per-profile auto-generation schedules.

Covers AppLogic._get_active_profiles ordering/active filtering,
_profile_schedule_met windows and once-per-day guards, _do_generate
per-profile filtering, and the services router profile_schedules contract.
"""

from datetime import datetime

import pytest
from tests.logic_test_helpers import build_app

PROFILE = {
    "target_odds": 2.0,
    "target_legs": 1,
    "consensus_floor": 50.0,
    "min_odds": 1.05,
    "tolerance_factor": 0.30,
    "stop_threshold": 0.50,
    "odds_movement_weight": 0.0,
    "odds_movement_strength_min": 0.2,
    "units": 1.0,
}


def _freeze(monkeypatch, year=2026, month=9, day=24, hour=9, minute=0):
    """Pin core.logic.datetime.now() to a fixed wall-clock time."""

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(year, month, day, hour, minute)

    monkeypatch.setattr("core.logic.datetime", Frozen)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    built = build_app(tmp_path, monkeypatch, profiles={})
    yield built
    built.app._assistant.conn.close()
    built.app._matches_manager.close()


def _save_profiles(app, profiles):
    """Write raw profile YAML dicts through the SettingsManager."""
    for name, cfg in profiles.items():
        app.settings.write(name, cfg, subpath="profiles")


class TestGetActiveProfilesOrdering:
    """[P0] _get_active_profiles: deterministic order, active filter, tuple shape."""

    def test_legacy_run_daily_count_only(self, env) -> None:
        """[P0] Legacy run_daily_count>0 profiles stay active with same tuple shape."""
        _save_profiles(
            env.app, {"a": {**PROFILE, "run_daily_count": 2}, "b": {**PROFILE}}
        )
        active = env.app._get_active_profiles()
        assert list(active) == ["a"]
        cfg, units, count, payout = active["a"]
        assert count == 2 and units == 1.0 and payout is None
        assert cfg.target_odds == 2.0

    def test_order_ascending_then_insertion(self, env) -> None:
        """[P0] Explicit order sorts ascending; unordered keep settings order after."""
        _save_profiles(
            env.app,
            {
                "zeta": {**PROFILE, "run_daily_count": 1, "order": 2},
                "alpha": {**PROFILE, "run_daily_count": 1, "order": 1},
                "mid": {**PROFILE, "run_daily_count": 1, "order": 1},
                "plain1": {**PROFILE, "run_daily_count": 1},
                "plain2": {**PROFILE, "run_daily_count": 1},
            },
        )
        assert list(env.app._get_active_profiles()) == [
            "alpha",
            "mid",
            "zeta",
            "plain1",
            "plain2",
        ]

    def test_auto_generate_active_without_run_daily_count(self, env) -> None:
        """[P0] auto_generate-only profiles are active and default to count 1."""
        _save_profiles(
            env.app, {"auto": {**PROFILE, "auto_generate": True}, "off": {**PROFILE}}
        )
        active = env.app._get_active_profiles()
        assert list(active) == ["auto"]
        assert active["auto"][2] == 1

    def test_explicit_legacy_zero_order_runs_first(self, env) -> None:
        """[P1] order=0 is explicit (runs first), distinct from missing order."""
        _save_profiles(
            env.app,
            {
                "noseq": {**PROFILE, "run_daily_count": 1},
                "zero": {**PROFILE, "run_daily_count": 1, "order": 0},
            },
        )
        assert list(env.app._get_active_profiles()) == ["zero", "noseq"]


class TestProfileScheduleMet:
    """[P0] _profile_schedule_met: per-profile window, legacy fallback, daily guard."""

    def test_inactive_profile_never_met(self, env) -> None:
        """[P0] Profiles that are neither auto_generate nor daily are never due."""
        assert env.app._profile_schedule_met("ghost", {"units": 1.0}) is False

    def test_per_profile_window_before_hour_false(self, env, monkeypatch) -> None:
        """[P0] Before the profile's own hour the schedule is not met."""
        cfg = {"auto_generate": True, "generate_hour": 12, "generate_minute": 0}
        _freeze(monkeypatch, hour=9)
        assert env.app._profile_schedule_met("p", cfg) is False

    def test_per_profile_window_after_hour_true(self, env, monkeypatch) -> None:
        """[P0] At/after the profile's own hour the schedule is met."""
        cfg = {"run_daily_count": 1, "generate_hour": 8, "generate_minute": 30}
        _freeze(monkeypatch, hour=9)
        assert env.app._profile_schedule_met("p", cfg) is True

    def test_legacy_fallback_uses_global_window(self, env, monkeypatch) -> None:
        """[P0] Without per-profile times the global services window applies."""
        env.app.save_service_settings(8, 0)
        _save_profiles(env.app, {"legacy": {**PROFILE, "run_daily_count": 1}})
        _freeze(monkeypatch, hour=7)
        assert env.app._profile_schedule_met("legacy") is False
        _freeze(monkeypatch, hour=9)
        assert env.app._profile_schedule_met("legacy") is True

    def test_daily_guard_blocks_second_run(self, env, monkeypatch) -> None:
        """[P0] A per-profile stamp for today blocks a second run today."""
        cfg = {"auto_generate": True, "generate_hour": 8, "generate_minute": 0}
        _save_profiles(env.app, {"p": {**PROFILE, **cfg}})
        _freeze(monkeypatch, hour=9)
        assert env.app._profile_schedule_met("p") is True
        env.app._claim_profile_runs({"p": (None, 1.0, 1, None)})
        assert env.app._profile_schedule_met("p") is False

    def test_stamp_from_yesterday_allows_run(self, env, monkeypatch) -> None:
        """[P1] A yesterday stamp does not block today's run."""
        cfg = {"auto_generate": True, "generate_hour": 8, "generate_minute": 0}
        _save_profiles(env.app, {"p": {**PROFILE, **cfg}})
        env.app.settings.write(
            "runtime_state",
            {"profile_last_generated": {"p": "2026-09-23"}},
        )
        _freeze(monkeypatch, hour=9)
        assert env.app._profile_schedule_met("p") is True


class TestGeneratorPredicatePerProfile:
    """[P0] _is_generator_hour_met fires on any active profile's window."""

    def test_per_profile_due_fires_predicate(self, env, monkeypatch) -> None:
        """[P0] A due per-profile window returns True even outside global window."""
        env.app.save_service_settings(23, 0)  # global window not reached at 09:00
        _save_profiles(
            env.app,
            {
                "early": {
                    **PROFILE,
                    "auto_generate": True,
                    "generate_hour": 8,
                    "generate_minute": 0,
                }
            },
        )
        _freeze(monkeypatch, hour=9)
        assert env.app._is_generator_hour_met() is True

    def test_legacy_only_unchanged_semantics(self, env, monkeypatch) -> None:
        """[P0] Legacy-only setups keep the global window + once-per-day guard."""
        env.app.save_service_settings(8, 0)
        _save_profiles(env.app, {"legacy": {**PROFILE, "run_daily_count": 1}})
        _freeze(monkeypatch, hour=9)
        assert env.app._is_generator_hour_met() is True
        assert env.app._last_generator_run == "2026-09-24"
        assert env.app._is_generator_hour_met() is False


class TestDoGeneratePerProfile:
    """[P0] _do_generate filters to due profiles and stamps per-profile runs."""

    def test_due_profile_generates_and_stamps(
        self, env, monkeypatch, broadcast_capture
    ) -> None:
        """[P0] The due profile generates a slip and gets a per-profile stamp."""
        from tests.logic_test_helpers import seed_matches_db

        seed_matches_db(env.matches_db, rows=[])
        _save_profiles(
            env.app,
            {
                "due": {
                    **PROFILE,
                    "auto_generate": True,
                    "generate_hour": 8,
                    "generate_minute": 0,
                },
                "later": {
                    **PROFILE,
                    "auto_generate": True,
                    "generate_hour": 20,
                    "generate_minute": 0,
                },
            },
        )
        generated: list[str] = []

        def fake_generate(profiles):
            generated.extend(profiles)
            return {}

        monkeypatch.setattr(env.app, "generate_slips", fake_generate)
        _freeze(monkeypatch, hour=9)
        env.app._do_generate()
        assert generated == ["due"]
        runtime = env.app.settings.get("runtime_state") or {}
        assert (runtime.get("profile_last_generated") or {}).get("due") == "2026-09-24"
        assert "later" not in (runtime.get("profile_last_generated") or {})
        assert broadcast_capture[-1]["event"] == "slips_updated"

    def test_nothing_due_generates_nothing(
        self, env, monkeypatch, broadcast_capture
    ) -> None:
        """[P0] When no profile is due nothing generates and no timestamps persist."""
        _save_profiles(
            env.app,
            {
                "later": {
                    **PROFILE,
                    "auto_generate": True,
                    "generate_hour": 20,
                    "generate_minute": 0,
                }
            },
        )

        def boom(profiles):
            raise AssertionError("generate_slips must not run")

        monkeypatch.setattr(env.app, "generate_slips", boom)
        _freeze(monkeypatch, hour=9)
        env.app._do_generate()
        assert env.app.settings.get("runtime_state") is None
        assert broadcast_capture[-1]["event"] == "slips_updated"


class TestProfileSchedulesAPI:
    """[P0] GET/POST /api/services profile_schedules contract."""

    def test_get_includes_profile_schedules_rows(self, env) -> None:
        """[P0] Every saved profile appears with defaults from legacy config."""
        env.app.save_service_settings(8, 30)
        _save_profiles(
            env.app,
            {
                "legacy": {
                    **PROFILE,
                    "run_daily_count": 1,
                    "units": 2.0,
                    "target_payout": 50.0,
                },
                "auto": {
                    **PROFILE,
                    "auto_generate": True,
                    "generate_hour": 6,
                    "generate_minute": 15,
                    "order": 3,
                },
                "off": {**PROFILE},
            },
        )
        rows = {r["name"]: r for r in env.app.get_profile_schedules()}
        assert {"legacy", "auto", "off"} <= set(rows)
        assert rows["legacy"] == {
            "name": "legacy",
            "auto_generate": True,
            "generate_hour": 8,
            "generate_minute": 30,
            "units": 2.0,
            "target_payout": 50.0,
            "order": 0,
        }
        assert rows["auto"]["generate_hour"] == 6
        assert rows["auto"]["generate_minute"] == 15
        assert rows["auto"]["order"] == 3
        assert rows["off"]["auto_generate"] is False

    def test_save_profile_schedules_merges_without_dropping_keys(self, env) -> None:
        """[P0] POSTed rows merge into YAML and keep unrelated profile keys."""
        _save_profiles(env.app, {"p": {**PROFILE, "run_daily_count": 1}})
        env.app.save_profile_schedules(
            [
                {
                    "name": "p",
                    "auto_generate": True,
                    "generate_hour": 7,
                    "generate_minute": 45,
                    "units": 3.0,
                    "target_payout": 25.0,
                    "order": 5,
                }
            ]
        )
        stored = env.app.settings.get("profiles")["p"]
        assert stored["auto_generate"] is True
        assert stored["generate_hour"] == 7
        assert stored["generate_minute"] == 45
        assert stored["units"] == 3.0
        assert stored["target_payout"] == 25.0
        assert stored["order"] == 5
        assert stored["run_daily_count"] == 1  # untouched keys survive
        assert stored["target_odds"] == PROFILE["target_odds"]

    def test_save_profile_schedules_ignores_unknown_profile(self, env) -> None:
        """[P1] Rows for unknown profiles are skipped, existing data untouched."""
        _save_profiles(env.app, {"p": {**PROFILE, "run_daily_count": 1}})
        env.app.save_profile_schedules([{"name": "ghost", "auto_generate": True}])
        assert "ghost" not in env.app.settings.get("profiles")
