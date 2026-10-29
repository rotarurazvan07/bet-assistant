"""[P0] T4: profile generation ordering + per-profile auto-generation schedules.

Covers AppLogic._get_active_profiles ordering/active filtering,
_profile_schedule_met windows and once-per-day guards, _do_generate
per-profile filtering, and the services router profile_schedules contract.
"""

from datetime import datetime

import pytest
from tests.logic_test_helpers import build_app
import contextlib

PROFILE = {
    "target_odds": 2.0,
    "target_legs": 1,
    "consensus_floor": 50.0,
    "min_leg_odds": 1.05,
    "tolerance_factor": 0.30,
    "stop_threshold": 0.50,
    "odds_movement_weight": 0.0,
    "odds_movement_strength_min": 0.2,
    "units": 1.0,
}


def _freeze(monkeypatch, year=2026, month=9, day=24, hour=9, minute=0) -> None:
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


def _save_profiles(app, profiles) -> None:
    """Write raw profile YAML dicts through the SettingsManager."""
    for name, cfg in profiles.items():
        app.settings.write(name, cfg, subpath="profiles")


class TestGetActiveProfilesOrdering:
    """[P0] _get_active_profiles: deterministic order, active filter, tuple shape."""

    def test_legacy_run_daily_count_only(self, env) -> None:
        """[P0] Legacy run_daily_count>0 profiles stay active with same tuple shape."""
        _save_profiles(env.app, {"a": {**PROFILE, "run_daily_count": 2}, "b": {**PROFILE}})
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
        _save_profiles(env.app, {"auto": {**PROFILE, "auto_generate": True}, "off": {**PROFILE}})
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

    def test_no_per_profile_window_never_met(self, env, monkeypatch) -> None:
        """[P0] No global fallback: a profile without its own window never fires.

        Per-profile windows only: a windowless profile NEVER fires even when a
        stale legacy ``services.generate_hour`` exists in config.
        """
        _save_profiles(env.app, {"legacy": {**PROFILE, "run_daily_count": 1}})
        _freeze(monkeypatch, hour=7)
        assert env.app._profile_schedule_met("legacy") is False
        _freeze(monkeypatch, hour=9)
        assert env.app._profile_schedule_met("legacy") is False
        assert env.app._is_generator_hour_met() is False

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
        # Frozen now is 2026-09-24 09:00 local (EEST) = 06:00Z; a run yesterday
        # local (2026-09-23 06:00Z) must not block today.
        env.app.settings.write(
            "runtime_state",
            {"profile_last_run": {"p": {"at": "2026-09-23T06:00:00+00:00", "status": "ok", "error": None}}},
        )
        _freeze(monkeypatch, hour=9)
        assert env.app._profile_schedule_met("p") is True


class TestGeneratorPredicateTimezone:
    """[P0] Regression: the gate interprets windows in the configured
    local_timezone (Europe/Bucharest), NOT container-local time (UTC in
    Docker) — otherwise a window set "2 minutes ahead" in the Services UI
    is hours away for the backend and generation never fires on time."""

    @staticmethod
    def _freeze_utc(monkeypatch, utc_hour: int, utc_minute: int = 0) -> None:
        """Pin datetime.now(tz) to a fixed AWARE UTC time."""
        from datetime import timezone

        class FrozenUTC(datetime):
            @classmethod
            def now(cls, tz=None):
                base = cls(2026, 9, 24, utc_hour, utc_minute, tzinfo=timezone.utc)
                return base if tz is None else base.astimezone(tz)

        monkeypatch.setattr("core.logic.datetime", FrozenUTC)

    def test_window_fires_in_local_tz_not_container_utc(self, env, monkeypatch) -> None:
        """Window 09:00 Europe/Bucharest (=06:00 UTC in summer). At 07:30 UTC
        (=10:30 local) the profile IS due — container-UTC comparison would say no."""
        _save_profiles(env.app, {"p": {**PROFILE, "auto_generate": True, "generate_hour": 9, "generate_minute": 0}})
        env.app.settings.write("scraper_config", {"local_timezone": "Europe/Bucharest"})
        self._freeze_utc(monkeypatch, utc_hour=7, utc_minute=30)
        assert env.app._is_generator_hour_met() is True
        assert env.app._profile_schedule_met("p") is True

    def test_window_not_yet_due_in_local_tz(self, env, monkeypatch) -> None:
        """At 05:30 UTC (=08:30 local) a 09:00 local window is NOT due yet."""
        _save_profiles(env.app, {"p": {**PROFILE, "auto_generate": True, "generate_hour": 9, "generate_minute": 0}})
        env.app.settings.write("scraper_config", {"local_timezone": "Europe/Bucharest"})
        self._freeze_utc(monkeypatch, utc_hour=5, utc_minute=30)
        assert env.app._is_generator_hour_met() is False
        assert env.app._profile_schedule_met("p") is False


class TestGeneratorPredicatePerProfile:
    """[P0] _is_generator_hour_met fires on any active profile's window."""

    def test_per_profile_due_fires_predicate(self, env, monkeypatch) -> None:
        """[P0] A due per-profile window returns True (no global window exists)."""
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

    def test_legacy_only_no_window_never_fires(self, env, monkeypatch) -> None:
        """[P0] Legacy-only setups (no per-profile window) never fire."""
        _save_profiles(env.app, {"legacy": {**PROFILE, "run_daily_count": 1}})
        _freeze(monkeypatch, hour=9)
        assert env.app._is_generator_hour_met() is False


class TestDoGeneratePerProfile:
    """[P0] _do_generate filters to due profiles and stamps per-profile runs."""

    def test_due_profile_generates_and_stamps(self, env, monkeypatch, broadcast_capture) -> None:
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
        runs = runtime.get("profile_last_run") or {}
        # Single consolidated entry: at/status/error, no legacy keys
        assert runs.get("due", {}).get("status") == "ok"
        assert runs.get("due", {}).get("at")
        assert "later" not in runs
        for legacy in ("profile_last_generated", "profile_last_generated_at", "profile_run_status", "last_time_generated"):
            assert legacy not in runtime
        assert broadcast_capture[-1]["event"] == "slips_updated"

    def test_nothing_due_generates_nothing(self, env, monkeypatch, broadcast_capture) -> None:
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
        before = len(broadcast_capture)
        env.app._do_generate()
        assert env.app.settings.get("runtime_state") is None
        # F17: a no-op tick appends no slips_updated broadcast, so clients do
        # not refetch slips for nothing.
        assert len(broadcast_capture) == before


class TestProfileSchedulesAPI:
    """[P0] GET/POST /api/services profile_schedules contract."""

    def test_get_includes_profile_schedules_rows(self, env) -> None:
        """[P0] Every saved profile appears with persisted values only."""
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
        all_rows = env.app.get_profile_schedules()
        rows = {r["name"]: r for r in all_rows}
        assert {"legacy", "auto", "off"} <= set(rows)
        # Issue #95: rows carry computed scheduler state (stake_mode,
        # last_generated_at/next_run_at/last_run_status/last_run_error), and
        # "order" is the EFFECTIVE UI position (0-based), never the raw null —
        # a profile without order on disk still has a concrete row position.
        # legacy is active (run_daily_count=1) but has no window of its own →
        # next_run_at is None (no fabricated 08:00 fallback); the daemon never
        # fires a windowless profile, so the column shows "—".
        legacy_row = rows["legacy"]
        assert legacy_row["name"] == "legacy"
        assert legacy_row["auto_generate"] is True
        assert legacy_row["generate_hour"] is None
        assert legacy_row["units"] == 2.0
        assert legacy_row["target_payout"] == 50.0
        assert legacy_row["stake_mode"] == "payout"
        assert legacy_row["run_daily_count"] == 1
        assert legacy_row["last_generated_at"] is None
        assert legacy_row["last_run_status"] is None
        assert legacy_row["last_run_error"] is None
        assert legacy_row["next_run_at"] is None  # windowless active profile never fires
        assert rows["auto"]["generate_hour"] == 6
        assert rows["auto"]["generate_minute"] == 15
        assert rows["off"]["auto_generate"] is False
        assert rows["off"]["next_run_at"] is None  # auto off → no next run
        # Effective order = position in UI-sorted rows (built-ins included):
        # every row carries its 0-based position, never the raw null.
        assert [r["order"] for r in all_rows] == list(range(len(all_rows)))
        assert rows["legacy"]["order"] is not None  # was null on disk → positional
        assert rows["off"]["order"] is not None
        # auto has explicit order 3 → sorts after all order-0 (null) rows
        assert rows["auto"]["order"] == len(all_rows) - 1

    def test_get_profile_schedules_order_reflects_ui_position(self, env) -> None:
        """[P0] Issue #95 follow-up: a NEW profile has order=null in YAML, but
        the Services tab shows it at a concrete position — the GET row must
        report that effective position (and rows come back in UI order), not
        the raw null. The autosave writes these back, so YAML converges."""
        _save_profiles(
            env.app,
            {
                "b_new": {**PROFILE, "auto_generate": True, "order": None},  # no order on disk
                "a_old": {**PROFILE, "auto_generate": True, "order": 7},
            },
        )
        rows = env.app.get_profile_schedules()
        by_name = {r["name"]: r for r in rows}
        # null order sorts as 0 → b_new ahead of a_old (order 7); both rows
        # carry concrete positional ints (never the raw null from disk)
        assert isinstance(by_name["b_new"]["order"], int)
        assert isinstance(by_name["a_old"]["order"], int)
        assert by_name["b_new"]["order"] < by_name["a_old"]["order"]
        assert [r["order"] for r in rows] == list(range(len(rows)))

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

    def test_save_profile_schedules_stake_mode_switch_preserves_both_fields(self, env) -> None:
        """[P0] Issue #95: switching stake_mode units→payout keeps BOTH values on
        disk — stake_mode only selects which is active, never nulls the other."""
        _save_profiles(env.app, {"p": {**PROFILE, "units": 1.0, "target_payout": 25.0}})
        env.app.save_profile_schedules([{"name": "p", "stake_mode": "payout", "units": 1.0, "target_payout": 50.0}])
        stored = env.app.settings.get("profiles")["p"]
        assert stored["stake_mode"] == "payout"
        assert stored["units"] == 1.0  # preserved, not nulled
        assert stored["target_payout"] == 50.0

    def test_save_profile_schedules_without_stake_mode_keeps_null_fields(self, env) -> None:
        """[P0] Issue #95: no stake_mode → null units/payout means 'not provided', persisted value kept."""
        _save_profiles(env.app, {"p": {**PROFILE, "units": 2.0, "target_payout": 30.0}})
        env.app.save_profile_schedules([{"name": "p", "units": None, "target_payout": None}])
        stored = env.app.settings.get("profiles")["p"]
        assert stored["units"] == 2.0
        assert stored["target_payout"] == 30.0

    def test_save_profile_schedules_value_edit_in_units_mode_keeps_payout(self, env) -> None:
        """[P0] Issue #95: editing units while stake_mode=units (no mode switch) must not null payout."""
        _save_profiles(env.app, {"p": {**PROFILE, "units": 1.0, "target_payout": 50.0, "stake_mode": "units"}})
        env.app.save_profile_schedules([{"name": "p", "stake_mode": "units", "units": 3.0}])
        stored = env.app.settings.get("profiles")["p"]
        assert stored["units"] == 3.0
        assert stored["target_payout"] == 50.0  # untouched — not nulled

    def test_get_profile_schedules_returns_persisted_stake_mode(self, env) -> None:
        """[P0] Issue #95: GET returns the persisted stake_mode (not just inferred)."""
        _save_profiles(env.app, {"p": {**PROFILE, "units": 1.0, "target_payout": 50.0, "stake_mode": "payout"}})
        rows = {r["name"]: r for r in env.app.get_profile_schedules()}
        assert rows["p"]["stake_mode"] == "payout"
        assert rows["p"]["units"] == 1.0
        assert rows["p"]["target_payout"] == 50.0

    def test_save_profile_schedules_ignores_unknown_profile(self, env) -> None:
        """[P1] Rows for unknown profiles are skipped, existing data untouched."""
        _save_profiles(env.app, {"p": {**PROFILE, "run_daily_count": 1}})
        env.app.save_profile_schedules([{"name": "ghost", "auto_generate": True}])
        assert "ghost" not in env.app.settings.get("profiles")

    def test_services_scope_payout_defaults_to_1_not_null(self, env) -> None:
        """[P0] Services-tab scope only: a profile with no target_payout on
        disk reports 1 (like units) in GET and gets 1 persisted on save —
        never null in the YAML through this path."""
        _save_profiles(env.app, {"p": {**PROFILE, "run_daily_count": 1}})  # no target_payout key
        rows = {r["name"]: r for r in env.app.get_profile_schedules()}
        assert rows["p"]["target_payout"] == 1.0
        assert rows["p"]["units"] == 1.0
        env.app.save_profile_schedules([{"name": "p", "auto_generate": True}])
        stored = env.app.settings.get("profiles")["p"]
        assert stored["target_payout"] == 1.0
        assert stored["units"] == 1.0

    def test_save_profile_schedules_strips_runtime_only_keys(self, env) -> None:
        """[P0] date_from/date_to/excluded_urls are runtime-only (Build page
        filters) and must never persist into profile YAML — stripped on save."""
        _save_profiles(
            env.app,
            {
                "p": {
                    **PROFILE,
                    "run_daily_count": 1,
                    "date_from": "2030-01-01",
                    "date_to": "2030-01-02",
                    "excluded_urls": ["x"],
                },
            },
        )
        env.app.save_profile_schedules([{"name": "p", "auto_generate": True}])
        stored = env.app.settings.get("profiles")["p"]
        assert "date_from" not in stored
        assert "date_to" not in stored
        assert "excluded_urls" not in stored


class TestOrderingRobustness:
    """[P0] F4/F2: hand-edited YAML and legacy profiles survive the ticker."""

    def test_mixed_order_types_do_not_raise(self, env) -> None:
        """[P0] A quoted or float order alongside ints sorts instead of raising."""
        _save_profiles(
            env.app,
            {
                "a": {**PROFILE, "auto_generate": True, "order": "2"},
                "b": {**PROFILE, "auto_generate": True, "order": 1},
                "c": {**PROFILE, "auto_generate": True, "order": 3},
            },
        )
        active = list(env.app._get_active_profiles())
        assert active.index("b") < active.index("a") < active.index("c")

    def test_windowed_profile_is_stamped_on_generate(self, env, monkeypatch) -> None:
        """[P0] A profile with its own window is stamped on generate."""
        _save_profiles(
            env.app,
            {"due": {**PROFILE, "run_daily_count": 1, "generate_hour": 8, "generate_minute": 0}},
        )
        monkeypatch.setattr(env.app, "generate_slips", lambda profiles: {})
        _freeze(monkeypatch, hour=9)
        env.app._do_generate()
        runs = (env.app.settings.get("runtime_state") or {}).get("profile_last_run") or {}
        entry = runs.get("due") or {}
        assert entry.get("status") == "ok"
        # Frozen now is 2026-09-24 09:00 EEST → 06:00Z; entry must be today local
        assert env.app._last_run_local_date("due") == "2026-09-24"

    def test_claim_writes_single_entry_and_drops_legacy_keys(self, env) -> None:
        """[P0] runtime_state holds ONE entry per profile (profile_last_run with
        at/status/error); legacy keys present on disk are removed on write."""
        env.app.settings.write(
            "runtime_state",
            {
                "last_time_generated": "2026-09-23T20:00:00",
                "profile_last_generated": {"p": "2026-09-23"},
                "profile_last_generated_at": {"p": "2026-09-23T20:00:00+00:00"},
                "profile_run_status": {"p": {"status": "ok", "error": None, "at": "2026-09-23T20:00:00"}},
                "profile_last_run": {"p": {"at": "2026-09-23T20:00:00+00:00", "status": "ok", "error": None}},
            },
        )
        env.app._claim_profile_runs({"p": (None, 1.0, 1, None), "q": (None, 1.0, 1, None)}, status="failed", error="boom")
        runtime = env.app.settings.get("runtime_state") or {}
        assert set(runtime) == {"profile_last_run"}
        runs = runtime["profile_last_run"]
        assert runs["p"] == {"at": runs["p"]["at"], "status": "failed", "error": "boom"}
        assert runs["q"]["status"] == "failed" and runs["q"]["error"] == "boom"
        assert datetime.fromisoformat(runs["p"]["at"]).tzinfo is not None

    def test_manual_slip_save_never_touches_generation_state(self, env) -> None:
        """[P0] Build-independence: saving a manual slip (Build page) must not
        write or modify profile_last_run — only the generator claims runs."""
        env.app.settings.write(
            "runtime_state", {"profile_last_run": {"p": {"at": "2026-09-23T06:00:00+00:00", "status": "ok", "error": None}}}
        )
        before = env.app.settings.get("runtime_state")
        # Manual path: save_slip_and_broadcast -> save_slip only; empty legs may
        # raise inside BetAssistant, but generation state must stay untouched.
        with contextlib.suppress(Exception):
            env.app.save_slip_and_broadcast("manual", [], 1.0)
        after = env.app.settings.get("runtime_state")
        assert after == before
