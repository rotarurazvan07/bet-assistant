"""[P0] Unit tests for AppLogic lifecycle (issue #59).

Covers: __init__ TickerService wiring, properties, refresh_data,
pull_matches_db (mocked HTTP + real merge), toggle_service persistence +
WS broadcast, save_service_settings, _is_generator_hour_met daily guard,
_check_for_changes HEAD/ETag paths, odds movement/history delegation, and
ticker callback paths (_do_pull/_do_generate/_do_verify).

All AppLogic instances are REAL, built via logic_test_helpers.build_app()
against tmp_path SQLite DBs — never workspace DBs.
"""

from __future__ import annotations

import json
import os
import urllib.error
from datetime import datetime
from types import SimpleNamespace

import pytest

from tests.logic_test_helpers import (
    FakeHTTPResponse,
    FakeTicker,
    build_app,
    make_match_row_db,
    seed_matches_db,
)


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    env = build_app(tmp_path, monkeypatch)
    yield env
    env.app._assistant.conn.close()
    env.app._matches_manager.close()


class TestAppLogicLifecycle:
    """Lifecycle: construction wiring, data refresh, pull, services, predicates."""

    # ── __init__ wiring ─────────────────────────────────────────────────────

    def test_init_creates_three_services_with_correct_names(self, app_env):
        """[P0] Given AppLogic construction, all three tickers exist."""
        # Given / When: app_env constructed
        # Then
        assert set(app_env.app.services) == {"puller", "generator", "verifier"}

    def test_init_puller_interval_and_predicate(self, app_env):
        """[P0] Puller polls every 5 min gated by _check_for_changes."""
        puller = app_env.app.services["puller"]
        assert puller.interval == 5 * 60
        assert puller.predicate == app_env.app._check_for_changes

    def test_init_generator_interval_and_predicate(self, app_env):
        """[P0] Generator polls every 5 min gated by _is_generator_hour_met."""
        gen = app_env.app.services["generator"]
        assert gen.interval == 5 * 60
        assert gen.predicate == app_env.app._is_generator_hour_met

    def test_init_verifier_interval_and_no_predicate(self, app_env):
        """[P0] Verifier polls every 60 s with no predicate."""
        ver = app_env.app.services["verifier"]
        assert ver.interval == 60
        assert ver.predicate is None

    def test_init_all_services_enabled_by_default(self, app_env):
        """[P1] Without saved toggles all three services start enabled."""
        assert all(s.enabled for s in app_env.app.services.values())

    def test_init_applies_saved_toggle_states(self, tmp_path, monkeypatch):
        """[P1] Saved toggles are applied to services at construction."""
        env = build_app(
            tmp_path,
            monkeypatch,
            services={"generate_hour": 8, "generate_minute": 0, "toggles": {"puller": False}},
        )
        try:
            assert env.app.services["puller"].enabled is False
            assert env.app.services["generator"].enabled is True
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()

    def test_init_no_daemon_threads_spawned(self, app_env):
        """[P2] FakeTicker wiring means no real threads are started."""
        assert all(isinstance(s, FakeTicker) for s in app_env.app.services.values())

    # ── Properties ──────────────────────────────────────────────────────────

    def test_logic_property_returns_self(self, app_env):
        """[P1] .logic backward-compat facade returns self for routers."""
        assert app_env.app.logic is app_env.app

    def test_settings_property_returns_settings_manager(self, app_env):
        """[P1] .settings exposes the SettingsManager used by routers."""
        assert app_env.app.settings.get("services") is not None

    def test_config_path_property(self, app_env):
        """[P2] .config_path echoes constructor config dir."""
        assert app_env.app.config_path == str(app_env.config_dir)

    def test_last_pull_timestamp_reads_db_mtime(self, app_env):
        """[P2] last_pull_timestamp formats matches DB mtime."""
        ts = app_env.app.last_pull_timestamp
        assert isinstance(ts, str) and ts != "Unknown"
        assert len(ts) == len("2030-01-01 10:00")

    def test_last_pull_timestamp_missing_db_returns_unknown(self, tmp_path, monkeypatch):
        """[P2] Missing matches DB yields 'Unknown' instead of raising."""
        env = build_app(tmp_path, monkeypatch, rows=[])
        try:
            os.unlink(env.matches_db)  # delete DB to force mtime failure
            assert env.app.last_pull_timestamp == "Unknown"
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()

    def test_match_df_property_exposes_assistant_df(self, app_env):
        """[P1] match_df is the assistant's internal DataFrame reference."""
        assert app_env.app.match_df is app_env.app._assistant._df
    # ── refresh_data / filter_matches ──────────────────────────────────────

    def test_refresh_data_loads_matches_into_assistant(self, app_env):
        """[P0] refresh_data pulls DB rows into the BetAssistant DataFrame."""
        df = app_env.app.refresh_data()
        assert len(df) == 3
        assert df.iloc[0]["cons_home"] == 75.0  # 3 of 4 sources predict a home win
        assert df.iloc[0]["sources"] == 4

    def test_refresh_data_returns_copy_not_internal_df(self, app_env):
        """[P2] The returned DataFrame is a copy; mutations do not leak inside."""
        df = app_env.app.refresh_data()
        df.drop(df.index, inplace=True)
        assert len(app_env.app.match_df) == 3

    def test_refresh_data_with_excluded_sources_recalculates_consensus(self, app_env):
        """[P1] Excluding the dissenting source lifts home consensus to 100%."""
        df = app_env.app.refresh_data(excluded_sources=["windrawwin"])
        assert df.iloc[0]["sources"] == 3
        assert df.iloc[0]["cons_home"] == 100.0

    def test_filter_matches_by_search_text(self, app_env):
        """[P1] search_text filters home/away names case-insensitively."""
        out = app_env.app.filter_matches(search_text="team home 1")
        assert len(out) == 1
        assert out.iloc[0]["home"] == "Team Home 1"

    def test_filter_matches_by_date_window(self, app_env):
        """[P2] date_from/date_to windows filter matches by datetime."""
        app = app_env.app
        assert len(app.filter_matches(date_from="2030-01-01")) == 3
        assert len(app.filter_matches(date_to="2029-12-31")) == 0

    def test_filter_matches_with_excluded_sources_reloads_data(self, app_env):
        """[P1] excluded_sources triggers a consensus-recalculating reload."""
        out = app_env.app.filter_matches(excluded_sources=["windrawwin"])
        assert app_env.app.match_df.iloc[0]["sources"] == 3
        assert app_env.app.match_df.iloc[0]["cons_home"] == 100.0
        assert len(out) == 3

    # ── pull_matches_db: download → merge → refresh ────────────────────────

    @staticmethod
    def _fake_urlretrieve(fresh_db, captured):
        def fake(url, dest):
            captured.append(url)
            import shutil

            shutil.copyfile(fresh_db, dest)

        return fake

    def test_pull_matches_db_downloads_merges_and_refreshes(self, app_env, monkeypatch):
        """[P0] Pull downloads the release DB, preserves history, refreshes data."""
        fresh_db = app_env.tmp_path / "fresh.db"
        fresh_rows = []
        for i in range(3):
            row = make_match_row_db(i)
            row["odds"] = json.dumps({"home": 2.1, "draw": 3.6, "away": 4.4})
            fresh_rows.append(row)
        seed_matches_db(str(fresh_db), fresh_rows)

        captured: list = []
        monkeypatch.setenv("REPO", "acme/bet-test")
        monkeypatch.setattr(
            "urllib.request.urlretrieve", self._fake_urlretrieve(str(fresh_db), captured)
        )

        result = app_env.app.pull_matches_db(app_env.matches_db)

        assert result == "Pull successful"
        assert captured == [
            "https://github.com/acme/bet-test/releases/download/latest-db/final_matches.db"
        ]
        assert len(app_env.app.match_df) == 3
        assert app_env.app.match_df.iloc[0]["odds"]["home"] == 2.1  # fresh odds won
        history = app_env.app.get_odds_history(0)
        assert len(history) == 2  # 1 preserved + 1 appended snapshot
        assert history[0]["timestamp"] == "2030-01-01T10:00:00"

    def test_pull_matches_db_download_error_raises_runtime_error(self, app_env, monkeypatch):
        """[P1] URLError during download is wrapped into RuntimeError."""

        def boom(url, dest):
            raise urllib.error.URLError("no route to host")

        monkeypatch.setattr("urllib.request.urlretrieve", boom)
        with pytest.raises(RuntimeError, match="Failed to download DB"):
            app_env.app.pull_matches_db(app_env.matches_db)
    # ── Service toggles & settings ─────────────────────────────────────────

    def test_toggle_service_disables_persists_and_broadcasts(self, app_env, broadcast_capture):
        """[P0] Toggle flips state, persists to services.yaml, broadcasts WS event."""
        app = app_env.app
        result = app.toggle_service("puller")
        assert result is False
        assert app.services["puller"].enabled is False
        assert app.settings.get("services")["toggles"]["puller"] is False
        assert broadcast_capture[-1]["event"] == "service_toggled"
        assert broadcast_capture[-1]["name"] == "puller"
        assert broadcast_capture[-1]["enabled"] is False

    def test_toggle_service_reenables_on_second_toggle(self, app_env, broadcast_capture):
        """[P0] Toggling twice returns to enabled and persists True."""
        app = app_env.app
        app.toggle_service("verifier")
        result = app.toggle_service("verifier")
        assert result is True
        assert app.services["verifier"].enabled is True
        assert app.settings.get("services")["toggles"]["verifier"] is True
        assert broadcast_capture[-1]["enabled"] is True

    def test_toggle_service_unknown_name_returns_false(self, app_env, broadcast_capture):
        """[P1] Unknown service name returns False without config or broadcast."""
        result = app_env.app.toggle_service("nope")
        assert result is False
        assert app_env.app.settings.get("services")["toggles"] == {}
        assert not broadcast_capture

    def test_save_service_settings_persists_hour_and_minute(self, app_env):
        """[P0] save_service_settings writes generate_hour/minute to config."""
        app = app_env.app
        app.save_service_settings(9, 30)
        svc = app.settings.get("services")
        assert svc["generate_hour"] == 9
        assert svc["generate_minute"] == 30

    # ── _is_generator_hour_met: daily guard ─────────────────────────────────

    class _Frozen(datetime):
        """datetime subclass with pinned now() for deterministic predicates."""

        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 24, 9, 0)  # 09:00 — past the default 08:00 target

    def _freeze_now(self, monkeypatch):
        monkeypatch.setattr("core.logic.datetime", self._Frozen)

    def test_generator_predicate_false_before_target_time(self, app_env, monkeypatch):
        """[P0] Before the configured generate time the predicate never fires."""
        app = app_env.app
        app.save_service_settings(12, 0)  # target 12:00; frozen now is 09:00
        self._freeze_now(monkeypatch)
        assert app._is_generator_hour_met() is False
        assert app._last_generator_run is None

    def test_generator_predicate_true_on_first_call_after_target(self, app_env, monkeypatch):
        """[P0] First evaluation after the target time fires once per day."""
        app = app_env.app
        self._freeze_now(monkeypatch)
        assert app._is_generator_hour_met() is True
        assert app._last_generator_run == "2026-09-24"

    def test_generator_predicate_in_memory_guard_blocks_second_call(self, app_env, monkeypatch):
        """[P0] The in-memory guard blocks a second run on the same day."""
        app = app_env.app
        self._freeze_now(monkeypatch)
        assert app._is_generator_hour_met() is True
        assert app._is_generator_hour_met() is False

    def test_generator_predicate_respects_persisted_timestamp_same_day(self, tmp_path, monkeypatch):
        """[P0] On restart a same-day persisted timestamp blocks the run and syncs the guard."""
        env = build_app(
            tmp_path,
            monkeypatch,
            runtime_state={"last_time_generated": "2026-09-24T08:30:00"},
        )
        app = env.app
        try:
            self._freeze_now(monkeypatch)
            assert app._is_generator_hour_met() is False
            assert app._last_generator_run == "2026-09-24"
            assert app._is_generator_hour_met() is False  # guard now blocks
        finally:
            app._assistant.conn.close()
            app._matches_manager.close()

    def test_generator_predicate_persisted_yesterday_runs_again(self, tmp_path, monkeypatch):
        """[P1] A persisted timestamp from yesterday does not block today's run."""
        env = build_app(
            tmp_path,
            monkeypatch,
            runtime_state={"last_time_generated": "2026-09-23T08:30:00"},
        )
        app = env.app
        try:
            self._freeze_now(monkeypatch)
            assert app._is_generator_hour_met() is True
        finally:
            app._assistant.conn.close()
            app._matches_manager.close()

    def test_generator_predicate_invalid_persisted_timestamp_runs(self, tmp_path, monkeypatch):
        """[P2] A corrupt persisted timestamp is ignored; the run proceeds."""
        env = build_app(
            tmp_path,
            monkeypatch,
            runtime_state={"last_time_generated": "garbage"},
        )
        app = env.app
        try:
            self._freeze_now(monkeypatch)
            assert app._is_generator_hour_met() is True
        finally:
            app._assistant.conn.close()
            app._matches_manager.close()
    # ── _check_for_changes: HEAD + ETag logic ───────────────────────────────

    @staticmethod
    def _patch_urlopen(monkeypatch, response=None, error=None, captured=None):
        """Patch urllib.request.urlopen with a controllable fake."""

        def fake(req, timeout=None):
            if captured is not None:
                captured.append((req.method, req.full_url))
            if error is not None:
                raise error
            return response

        monkeypatch.setattr("urllib.request.urlopen", fake)

    def test_check_for_changes_head_request_new_etag_returns_true(self, app_env, monkeypatch):
        """[P0] First HEAD with a new ETag reports change and stores the ETag."""
        captured: list = []
        self._patch_urlopen(
            monkeypatch, response=FakeHTTPResponse({"ETag": "v1"}), captured=captured
        )
        monkeypatch.setenv("REPO", "acme/bet-test")
        assert app_env.app._check_for_changes() is True
        method, url = captured[0]
        assert method == "HEAD"
        assert url == "https://github.com/acme/bet-test/releases/download/latest-db/final_matches.db"
        assert app_env.app._last_etag == "v1"

    def test_check_for_changes_same_etag_returns_false(self, app_env, monkeypatch):
        """[P0] An unchanged ETag means no download is needed."""
        self._patch_urlopen(monkeypatch, response=FakeHTTPResponse({"ETag": "v1"}))
        app_env.app._check_for_changes()
        assert app_env.app._check_for_changes() is False

    def test_check_for_changes_changed_etag_returns_true(self, app_env, monkeypatch):
        """[P0] A changed ETag triggers a new download."""
        self._patch_urlopen(monkeypatch, response=FakeHTTPResponse({"ETag": "v2"}))
        app_env.app._last_etag = "v1"
        assert app_env.app._check_for_changes() is True
        assert app_env.app._last_etag == "v2"

    def test_check_for_changes_missing_etag_header_always_downloads(self, app_env, monkeypatch):
        """[P1] Without an ETag header every check reports a change."""
        self._patch_urlopen(monkeypatch, response=FakeHTTPResponse({}))
        assert app_env.app._check_for_changes() is True
        assert app_env.app._check_for_changes() is True

    def test_check_for_changes_request_error_downloads_anyway(self, app_env, monkeypatch):
        """[P1] HEAD failure falls back to attempting the download."""
        self._patch_urlopen(monkeypatch, error=OSError("boom"))
        assert app_env.app._check_for_changes() is True

    # ── Odds movement / history delegation ──────────────────────────────────

    @pytest.fixture()
    def bare_env(self, tmp_path, monkeypatch):
        env = build_app(tmp_path, monkeypatch, rows=[])
        yield env
        env.app._assistant.conn.close()
        env.app._matches_manager.close()

    def test_get_odds_movement_delegates_to_matches_manager(self, app_env):
        """[P0] Movement equals MatchesManager calculation on the same embedded odds."""
        app = app_env.app
        odds = app.match_df.iloc[0]["odds"]
        assert app.get_odds_movement(0) == app._matches_manager.calculate_movement_from_odds(odds)
        assert app.get_odds_movement(0)["home"] == "up"  # 1.8 → 1.9

    def test_get_odds_movement_invalid_index_returns_empty(self, app_env):
        """[P1] Out-of-range match ids return an empty dict."""
        assert app_env.app.get_odds_movement(-1) == {}
        assert app_env.app.get_odds_movement(99) == {}

    def test_get_odds_movement_empty_df_returns_empty(self, bare_env):
        """[P1] With no matches loaded there is nothing to report."""
        assert bare_env.app.get_odds_movement(0) == {}

    def test_get_odds_movement_row_without_odds_returns_empty(self, tmp_path, monkeypatch):
        """[P1] A row whose odds failed to deserialize yields no movement."""
        env = build_app(tmp_path, monkeypatch, rows=[make_match_row_db(odds="null")])
        try:
            assert env.app.get_odds_movement(0) == {}
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()

    def test_get_odds_movement_with_strength_reports_metrics(self, app_env):
        """[P1] Strength variant adds change_pct / significance per market."""
        movement = app_env.app.get_odds_movement_with_strength(0)
        assert movement["home"]["direction"] == "up"
        assert movement["home"]["change_pct"] == 5.56
        assert movement["home"]["significant"] is False  # needs 2+ history entries

    def test_get_odds_history_formats_snapshots_without_ts_key(self, app_env):
        """[P0] History snapshots expose timestamp + odds without the raw 'ts' key."""
        history = app_env.app.get_odds_history(0)
        assert len(history) == 1
        assert history[0]["timestamp"] == "2030-01-01T10:00:00"
        assert history[0]["odds"]["home"] == 1.8
        assert "ts" not in history[0]["odds"]

    def test_get_odds_history_invalid_index_returns_empty(self, app_env):
        """[P2] Out-of-range ids return an empty list."""
        assert app_env.app.get_odds_history(-1) == []
        assert app_env.app.get_odds_history(5) == []
    # ── Ticker callbacks ────────────────────────────────────────────────────

    def test_do_pull_pulls_and_broadcasts_matches_updated(self, app_env, monkeypatch, broadcast_capture):
        """[P0] _do_pull downloads into the matches DB path, then broadcasts."""
        app = app_env.app
        calls: list = []

        def fake_pull(path):
            calls.append(path)
            return "Pull successful"

        monkeypatch.setattr(app, "pull_matches_db", fake_pull)
        app._do_pull()
        assert calls == [app._matches_db_path]
        assert broadcast_capture[-1]["event"] == "matches_updated"
        assert broadcast_capture[-1]["timestamp"] == app.last_pull_timestamp

    def test_do_pull_swallows_errors_without_broadcast(self, app_env, monkeypatch, broadcast_capture):
        """[P1] A failing pull is logged, swallowed, and never broadcast."""

        def boom(path):
            raise RuntimeError("pull failed")

        monkeypatch.setattr(app_env.app, "pull_matches_db", boom)
        app_env.app._do_pull()  # must not raise
        assert not broadcast_capture

    def test_do_generate_generates_slips_and_persists_timestamp(
        self, tmp_path, monkeypatch, broadcast_capture
    ):
        """[P0] With an active daily profile the generator saves a slip and a timestamp."""
        profiles = {
            "p1": {
                "target_odds": 2.0,
                "target_legs": 1,
                "consensus_floor": 50.0,
                "min_odds": 1.05,
                "tolerance_factor": 0.30,
                "stop_threshold": 0.50,
                "odds_movement_weight": 0.0,
                "odds_movement_strength_min": 0.2,
                "units": 1.0,
                "run_daily_count": 1,
            }
        }
        env = build_app(tmp_path, monkeypatch, profiles=profiles)
        app = env.app
        try:
            app._do_generate()
            slips = app.get_slips()
            assert len(slips) == 1
            assert slips[0].profile == "p1"
            runtime = app.settings.get("runtime_state") or {}
            assert runtime.get("last_time_generated")
            assert broadcast_capture[-1]["event"] == "slips_updated"
        finally:
            app._assistant.conn.close()
            app._matches_manager.close()

    def test_do_generate_without_profiles_only_broadcasts(self, app_env, broadcast_capture):
        """[P1] No active profiles → broadcast only, nothing persisted."""
        app_env.app._do_generate()
        assert app_env.app.settings.get("runtime_state") is None
        assert broadcast_capture[-1]["event"] == "slips_updated"
        assert "live_data" not in broadcast_capture[-1]

    def test_do_generate_swallows_errors_without_broadcast(self, app_env, monkeypatch, broadcast_capture):
        """[P1] A failing generate is logged, swallowed, and never broadcast.

        An active profile (run_daily_count>0) is required so generate_slips is
        actually invoked; the built-in default profiles all have count 0.
        """
        app_env.app._manual_excluded.add("https://example.com/match/0")
        profiles = {"p1": (object(), 1.0, 1, None)}
        monkeypatch.setattr(app_env.app, "_get_active_profiles", lambda: profiles)

        def boom(profiles):
            raise RuntimeError("boom")

        monkeypatch.setattr(app_env.app, "generate_slips", boom)
        app_env.app._do_generate()
        assert not broadcast_capture

    def test_do_verify_broadcasts_live_leg_data(self, app_env, monkeypatch, broadcast_capture):
        """[P0] _do_verify maps live legs to {match: score/minute} and broadcasts."""
        from bet_framework.core.Slip import LegOutcomeInfo

        report = SimpleNamespace(
            live=[LegOutcomeInfo(leg_id=1, match_name="M 1", market="1", score="1:0", minute="23")]
        )
        monkeypatch.setattr(app_env.app, "validate_slips", lambda: report)
        app_env.app._do_verify()
        payload = broadcast_capture[-1]
        assert payload["event"] == "slips_updated"
        assert payload["live_data"] == {"M 1": {"score": "1:0", "minute": "23"}}

    def test_do_verify_swallows_errors_without_broadcast(self, app_env, monkeypatch, broadcast_capture):
        """[P1] A failing verify is logged, swallowed, and never broadcast."""

        def boom():
            raise RuntimeError("nope")

        monkeypatch.setattr(app_env.app, "validate_slips", boom)
        app_env.app._do_verify()
        assert not broadcast_capture

    def test_pull_and_broadcast_returns_message_and_broadcasts(
        self, app_env, monkeypatch, broadcast_capture
    ):
        """[P1] pull_and_broadcast returns the pull message and broadcasts matches_updated."""
        monkeypatch.setattr(app_env.app, "pull_matches_db", lambda path: "ok")
        assert app_env.app.pull_and_broadcast() == "ok"
        assert broadcast_capture[-1]["event"] == "matches_updated"
