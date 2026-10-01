"""[P0] Unit tests for AppLogic slip operations (issue #59).

Covers: build_slip / build_preview exclusion semantics, generate_slips
(profile loop, dynamic units, auto-exclusion), slip persistence + broadcast
wrappers, get_slips filters, get_pending_urls / get_excluded_urls, stats()
(all 25+ metrics), and analytics delegation.

All AppLogic instances are REAL, built via logic_test_helpers.build_app()
against tmp_path SQLite DBs — never workspace DBs.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bet_framework.core.Slip import BetSlipConfig, LegOutcomeInfo

from tests.logic_test_helpers import (
    build_app,
    make_candidate,
    make_leg_row,
    seed_slip,
)


def _slip_cfg(**overrides):
    """A permissive 1-leg BetSlipConfig that matches the seeded matches."""
    cfg = {
        "target_odds": 2.0,
        "target_legs": 1,
        "consensus_floor": 50.0,
        "min_odds": 1.05,
        "tolerance_factor": 0.30,
        "stop_threshold": 0.50,
        "odds_movement_weight": 0.0,
        "odds_movement_strength_min": 0.2,
    }
    cfg.update(overrides)
    return BetSlipConfig(**cfg)


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    env = build_app(tmp_path, monkeypatch)
    yield env
    env.app._assistant.conn.close()
    env.app._matches_manager.close()


class TestAppLogicSlipOperations:
    """Slip building, generation, persistence, retrieval, stats, analytics."""

    # ── build_slip ──────────────────────────────────────────────────────────

    def test_build_slip_respects_excluded_sources_from_config(self, app_env):
        """[P0] cfg.excluded_sources triggers a consensus-recalculating reload."""
        app = app_env.app
        cfg = _slip_cfg(excluded_sources=["windrawwin"])
        legs = app.build_slip(cfg)
        # Given the dissenting source is excluded, matches keep 3 sources
        # and home consensus is unanimous (100%).
        assert app.match_df.iloc[0]["sources"] == 3
        assert app.match_df.iloc[0]["cons_home"] == 100.0
        assert legs, "expected at least one leg from 3 viable matches"
        assert all(leg.consensus >= 50.0 for leg in legs)

    def test_build_slip_with_none_excluded_sources_reloads_all(self, app_env):
        """[P1] excluded_sources=None is an explicit no-filter reload."""
        app = app_env.app
        # Force a filtered state first so the reload is observable.
        app.refresh_data(excluded_sources=["windrawwin"])
        legs = app.build_slip(_slip_cfg(excluded_sources=None))
        assert app.match_df.iloc[0]["sources"] == 4  # reload with [] restored all
        assert legs

    def test_build_slip_passes_extra_excluded_urls(self, app_env):
        """[P1] extra_excluded_urls are skipped on top of config exclusions."""
        app = app_env.app
        urls = ["https://example.com/match/0", "https://example.com/match/1"]
        legs = app.build_slip(_slip_cfg(), extra_excluded_urls=urls)
        assert legs
        assert all(leg.result_url not in urls for leg in legs)

    def test_build_slip_empty_df_returns_no_legs(self, tmp_path, monkeypatch):
        """[P2] With no matches loaded the build is an empty list."""
        env = build_app(tmp_path, monkeypatch, rows=[])
        try:
            assert env.app.build_slip(_slip_cfg()) == []
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()

    # ── build_preview ───────────────────────────────────────────────────────

    def test_build_preview_uses_manual_exclusions_only(self, app_env):
        """[P0] Preview excludes only manual URLs, not pending-slip URLs."""
        app = app_env.app
        # Seed a pending slip whose leg URL should still appear in previews.
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0, legs=[make_leg_row()])
        app.add_excluded("https://example.com/match/1")
        legs = app.build_preview(_slip_cfg())
        urls = [leg.result_url for leg in legs]
        assert "https://example.com/match/1" not in urls  # manual exclusion honored
        assert "https://example.com/match/0" in urls or "https://example.com/match/2" in urls

    def test_build_preview_without_manual_exclusions_shows_pending(self, app_env):
        """[P1] Without manual exclusions pending-slip matches still preview."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0, legs=[make_leg_row()])
        legs = app.build_preview(_slip_cfg())
        urls = {leg.result_url for leg in legs}
        assert "https://example.com/match/0" in urls  # pending URL NOT hidden in preview

    def test_build_preview_respects_cfg_excluded_sources(self, app_env):
        """[P1] Preview also honors cfg.excluded_sources via the same reload path."""
        app = app_env.app
        app.build_preview(_slip_cfg(excluded_sources=["windrawwin"]))
        assert app.match_df.iloc[0]["sources"] == 3

    # ── save_slip ───────────────────────────────────────────────────────────

    def test_save_slip_persists_profile_units_and_legs(self, app_env):
        """[P0] save_slip returns the new id and stores legs verbatim."""
        app = app_env.app
        leg = make_candidate(odds=1.9)
        slip_id = app.save_slip("manual", [leg], units=2.5)
        slips = app.get_slips()
        assert slip_id == slips[0].slip_id
        assert slips[0].profile == "manual"
        assert slips[0].units == 2.5
        assert slips[0].total_odds == 1.9
        assert slips[0].legs[0].match_name == leg.match_name
        assert slips[0].slip_status == "Pending"
    # ── generate_slips ──────────────────────────────────────────────────────

    def _active_profile_tuple(self, **overrides):
        cfg = _slip_cfg(**overrides)
        return cfg, 1.0, 1, None

    def test_generate_slips_loops_profiles_and_count(self, app_env):
        """[P0] Each profile generates run_daily_count slips; ids are collected."""
        app = app_env.app
        profiles = {"p1": (self._active_profile_tuple()[0], 1.0, 2, None)}
        results = app.generate_slips(profiles)
        assert results == {"p1": [1, 2]}
        slips = app.get_slips("p1")
        assert len(slips) == 2
        assert all(s.slip_status == "Pending" for s in slips)

    def test_generate_slips_auto_excludes_used_urls(self, app_env):
        """[P0] build_slip_auto_exclude never reuses a URL already in a slip."""
        app = app_env.app
        app.generate_slips({"p1": (self._active_profile_tuple()[0], 1.0, 3, None)})
        # 3 matches, 3 single-leg slips → every URL consumed exactly once.
        urls = [leg.result_url for s in app.get_slips() for leg in s.legs]
        assert sorted(urls) == [f"https://example.com/match/{i}" for i in range(3)]
        assert len(urls) == len(set(urls))

    def test_generate_slips_dynamic_units_from_target_payout(self, app_env):
        """[P0] target_payout recalculates units: payout / total_odds rounded to 1dp."""
        app = app_env.app
        results = app.generate_slips({"p": (self._active_profile_tuple()[0], 1.0, 1, 10.0)})
        assert results["p"]
        slip = app.get_slips("p")[0]
        assert slip.total_odds == 1.9
        assert slip.units == 5.3  # round(10 / 1.9, 1)

    def test_generate_slips_zero_target_payout_keeps_units(self, app_env):
        """[P2] target_payout=0 is falsy → configured units are kept."""
        app = app_env.app
        app.generate_slips({"p": (self._active_profile_tuple()[0], 2.0, 1, 0)})
        assert app.get_slips("p")[0].units == 2.0

    def test_generate_slips_no_viable_matches_returns_empty(self, app_env):
        """[P1] When no legs can be built the profile yields no slips."""
        app = app_env.app
        cfg = _slip_cfg(consensus_floor=99.9)
        results = app.generate_slips({"p": (cfg, 1.0, 1, None)})
        assert results == {}
        assert app.get_slips() == []

    # ── get_slips filters ───────────────────────────────────────────────────

    @staticmethod
    def _seed_three_slips(app):
        seed_slip(app, date_generated="2030-01-01T10:00:00", total_odds=2.0, units=1.0,
                  legs=[make_leg_row(result_url="https://example.com/match/0")], profile="a")
        seed_slip(app, date_generated="2030-01-02T10:00:00", total_odds=3.0, units=1.0,
                  legs=[make_leg_row(result_url="https://example.com/match/1")], profile="b")
        seed_slip(app, date_generated="2030-01-03T10:00:00", total_odds=4.0, units=1.0,
                  legs=[make_leg_row(result_url="https://example.com/match/2")], profile="c")

    def test_get_slips_profile_list_filter(self, app_env):
        """[P0] A profile list returns only slips from those profiles."""
        self._seed_three_slips(app_env.app)
        out = app_env.app.get_slips(["a", "b"])
        assert {s.profile for s in out} == {"a", "b"}

    def test_get_slips_single_profile_filter(self, app_env):
        """[P1] A single profile string filters to that profile."""
        self._seed_three_slips(app_env.app)
        out = app_env.app.get_slips("c")
        assert [s.profile for s in out] == ["c"]

    def test_get_slips_all_normalizes_to_none(self, app_env):
        """[P1] profile='all' is normalized to None → every slip returned."""
        self._seed_three_slips(app_env.app)
        assert len(app_env.app.get_slips("all")) == 3

    def test_get_slips_date_from_filter(self, app_env):
        """[P1] date_from keeps slips generated on/after that date."""
        self._seed_three_slips(app_env.app)
        out = app_env.app.get_slips(date_from="2030-01-02")
        assert {s.date_generated.split("T")[0] for s in out} == {"2030-01-02", "2030-01-03"}

    def test_get_slips_date_to_filter(self, app_env):
        """[P1] date_to keeps slips generated on/before that date."""
        self._seed_three_slips(app_env.app)
        out = app_env.app.get_slips(date_to="2030-01-02")
        assert {s.date_generated.split("T")[0] for s in out} == {"2030-01-01", "2030-01-02"}

    def test_get_slips_date_window_filter(self, app_env):
        """[P1] A from/to window narrows to the enclosed day only."""
        self._seed_three_slips(app_env.app)
        out = app_env.app.get_slips(date_from="2030-01-02", date_to="2030-01-02")
        assert [s.date_generated.split("T")[0] for s in out] == ["2030-01-02"]

    def test_validate_slips_delegates_and_returns_report(self, app_env):
        """[P1] validate_slips delegates to BetAssistant and returns its report."""
        report = app_env.app.validate_slips()
        assert report.checked == 0  # empty slips DB → nothing to validate
        assert report.live == []

    # ── broadcast wrappers ──────────────────────────────────────────────────

    def test_save_slip_and_broadcast_saves_and_broadcasts(self, app_env, broadcast_capture):
        """[P0] save_slip_and_broadcast persists and fires slips_updated."""
        slip_id = app_env.app.save_slip_and_broadcast("manual", [make_candidate()], 1.0)
        assert slip_id == app_env.app.get_slips()[0].slip_id
        assert broadcast_capture[-1]["event"] == "slips_updated"
        assert "live_data" not in broadcast_capture[-1]

    def test_delete_slip_and_broadcast_deletes_and_broadcasts(self, app_env, broadcast_capture):
        """[P0] delete_slip_and_broadcast removes the slip and fires slips_updated."""
        app = app_env.app
        slip_id = seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                            legs=[make_leg_row()])
        app.delete_slip_and_broadcast(slip_id)
        assert app.get_slips() == []
        assert broadcast_capture[-1]["event"] == "slips_updated"

    def test_delete_slip_removes_slip_and_legs(self, app_env):
        """[P1] Plain delete_slip drops both slip rows and leg rows."""
        app = app_env.app
        slip_id = seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                            legs=[make_leg_row(),
                                  make_leg_row(result_url="https://example.com/match/9")])
        app.delete_slip(slip_id)
        assert app.get_slips() == []
        rows = app._assistant.fetch_rows("SELECT COUNT(*) FROM legs")
        assert rows[0][0] == 0

    def test_validate_and_broadcast_returns_report_and_live_data(
        self, app_env, monkeypatch, broadcast_capture
    ):
        """[P0] validate_and_broadcast returns the report and broadcasts live_data."""
        report = SimpleNamespace(
            live=[LegOutcomeInfo(leg_id=1, match_name="M 1", market="1", score="1:0", minute="23")]
        )

        def fake_validate():
            return report

        monkeypatch.setattr(app_env.app, "validate_slips", fake_validate)
        result = app_env.app.validate_and_broadcast()
        assert result is report
        payload = broadcast_capture[-1]
        assert payload["event"] == "slips_updated"
        assert payload["live_data"] == {"M 1": {"score": "1:0", "minute": "23"}}

    def test_validate_and_broadcast_no_live_legs_omits_live_data(
        self, app_env, monkeypatch, broadcast_capture
    ):
        """[P1] An empty live list still broadcasts, but without a live_data key."""

        def fake_validate():
            return SimpleNamespace(live=[])

        monkeypatch.setattr(app_env.app, "validate_slips", fake_validate)
        app_env.app.validate_and_broadcast()
        assert "live_data" not in broadcast_capture[-1]

    def test_generate_and_broadcast_generates_and_persists(self, tmp_path, monkeypatch, broadcast_capture):
        """[P0] generate_and_broadcast runs active profiles and persists the timestamp."""
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
            result = app.generate_and_broadcast()
            assert result == {"p1": [1]}
            runtime = app.settings.get("runtime_state") or {}
            assert runtime.get("last_time_generated")
            assert broadcast_capture[-1]["event"] == "slips_updated"
        finally:
            app._assistant.conn.close()
            app._matches_manager.close()

    def test_generate_and_broadcast_without_profiles_returns_empty(self, app_env, broadcast_capture):
        """[P1] No active profiles → empty dict, broadcast still fires."""
        assert app_env.app.generate_and_broadcast() == {}
        assert broadcast_capture[-1]["event"] == "slips_updated"

    # ── stats: all 25+ metrics ────────────────────────────────────────────

    @staticmethod
    def _seed_stats_slips(app):
        """3 settled slips over 3 days + 1 pending slip.

        Won 1.0u @2.0 (D1), Lost 2.0u @3.0 (D2), Won 1.0u @4.0 (D3),
        Pending 1.0u @5.0 (D3). Dates are fixed 2030 values: for any real
        now < 2030 all slips fall in the recent edge window, so the rolling
        trend is deterministic.
        """
        seed_slip(app, date_generated="2030-01-01T10:00:00", total_odds=2.0, units=1.0,
                  legs=[make_leg_row(status="Won")], profile="a")
        seed_slip(app, date_generated="2030-01-02T10:00:00", total_odds=3.0, units=2.0,
                  legs=[make_leg_row(status="Lost")], profile="a")
        seed_slip(app, date_generated="2030-01-03T10:00:00", total_odds=4.0, units=1.0,
                  legs=[make_leg_row(status="Won")], profile="b")
        seed_slip(app, date_generated="2030-01-03T11:00:00", total_odds=5.0, units=1.0,
                  legs=[make_leg_row(status="Pending")], profile="b")

    def test_stats_computes_all_core_metrics(self, app_env):
        """[P0] stats() derives every metric from the seeded P&L history."""
        self._seed_stats_slips(app_env.app)
        st = app_env.app.stats()
        # Counts and rates: 2 of 3 settled won; implied from 1/odds mean.
        assert st["total_settled"] == 3
        assert st["total_won_count"] == 2
        assert st["pending_count"] == 1
        assert st["win_rate"] == 66.67
        assert st["implied_win_rate"] == 36.11
        assert st["edge"] == 30.56
        # Money: stakes 4.0, returns 2.0+4.0=6.0, net +2.0.
        assert st["total_units_bet"] == 4.0
        assert st["gross_return"] == 6.0
        assert st["net_profit"] == 2.0
        assert st["roi_percentage"] == 50.0
        # Odds / staking: mean odds 3.0; units 1,2,1 → mean 1.33, std 0.58.
        assert st["avg_odds"] == 3.0
        assert st["avg_units"] == 1.33
        assert st["units_std"] == 0.58
        # Daily P&L: +1.0, −2.0, +3.0 → sharpe over 3 days (annualized).
        assert st["sharpe_ratio"] == 5.15
        assert st["best_day_pnl"] == 3.0
        assert st["worst_day_pnl"] == -2.0
        # Kelly: b=2.0, p=2/3 → fraction 0.5 × gross_return 6.0.
        assert st["kelly_suggested_units"] == 3.0
        # Trend: all slips in the recent window → growing at current edge.
        assert st["edge_trend"] == "growing"
        assert st["recent_edge_value"] == 30.56
        # Extremes: biggest win +3.0 (4.0×1.0 − 1.0), biggest loss −2.0.
        assert st["biggest_win_units"] == 3.0
        assert st["biggest_loss_units"] == -2.0
        # Streaks: W/L/W daily pattern → current win streak 1, longest 1/1.
        assert st["current_streak"] == 1
        assert st["longest_win_streak"] == 1
        assert st["longest_loss_streak"] == 1
        # Profit factor: gross wins (1.0 + 3.0) vs losses 2.0.
        assert st["profit_factor"] == 2.0

    def test_stats_empty_history_returns_zeroed_metrics(self, app_env):
        """[P1] No slips → all rate/money metrics zero, optionals None."""
        st = app_env.app.stats()
        assert st["total_settled"] == 0
        assert st["win_rate"] == 0.0
        assert st["edge"] == 0.0
        assert st["net_profit"] == 0.0
        assert st["roi_percentage"] == 0.0
        assert st["sharpe_ratio"] is None
        assert st["kelly_suggested_units"] == 0.0
        assert st["biggest_win_units"] is None
        assert st["biggest_loss_units"] is None
        assert st["best_day_pnl"] is None
        assert st["worst_day_pnl"] is None
        assert st["profit_factor"] == 0.0
        assert st["current_streak"] == 0

    def test_stats_respects_profile_and_date_filters(self, app_env):
        """[P1] stats() filters flow through get_slips (profile + window)."""
        self._seed_stats_slips(app_env.app)
        st = app_env.app.stats(profile="a", date_from="2030-01-01", date_to="2030-01-02")
        assert st["total_settled"] == 2
        assert st["total_won_count"] == 1
        assert st["pending_count"] == 0

    # ── Analytics delegation ───────────────────────────────────────────────

    def test_daily_summary_delegates_to_analytics_utils(self, app_env, monkeypatch):
        """[P0] daily_summary passes retrieved slips + filters to analytics_utils."""
        import core.analytics_utils as au

        calls: list = []

        def recorder(slips, profile, date_from, date_to):
            calls.append((slips, profile, date_from, date_to))
            return [{"day": "2030-01-01"}]

        monkeypatch.setattr(au, "calculate_daily_summary", recorder)
        self._seed_three_slips(app_env.app)
        out = app_env.app.daily_summary(profile="a", date_from="2030-01-01", date_to="2030-01-01")
        assert out == [{"day": "2030-01-01"}]
        slips, profile, date_from, date_to = calls[0]
        assert [s.profile for s in slips] == ["a"]
        assert (profile, date_from, date_to) == ("a", "2030-01-01", "2030-01-01")

    def test_daily_summary_defaults_profile_to_all(self, app_env, monkeypatch):
        """[P2] A None profile is normalized to 'all' for retrieval only.

        The raw None still flows to analytics_utils as the profile arg;
        the normalization exists so get_slips fetches every profile.
        """
        import core.analytics_utils as au

        seen: list = []

        def recorder(slips, profile, date_from, date_to):
            seen.append((profile, len(slips)))
            return []

        monkeypatch.setattr(au, "calculate_daily_summary", recorder)
        self._seed_three_slips(app_env.app)
        app_env.app.daily_summary()
        # 'all' was used for retrieval (all 3 slips fetched)...
        assert seen[0][1] == 3
        # ...while the original None is passed through to analytics_utils.
        assert seen[0][0] is None

    def test_market_accuracy_delegates_to_analytics_utils(self, app_env, monkeypatch):
        """[P0] market_accuracy passes the retrieved slips to analytics_utils."""
        import core.analytics_utils as au

        calls: list = []

        def recorder(slips):
            calls.append(slips)
            return [{"market": "1", "accuracy": 60.0}]

        monkeypatch.setattr(au, "calculate_market_accuracy", recorder)
        self._seed_three_slips(app_env.app)
        out = app_env.app.market_accuracy(profile=["a", "b"])
        assert out == [{"market": "1", "accuracy": 60.0}]
        assert len(calls[0]) == 2

    def test_correlation_data_filters_settled_then_delegates(self, app_env, monkeypatch):
        """[P0] correlation_data settles-filters before delegating."""
        import core.analytics_utils as au

        calls: list = []

        def recorder(slips):
            calls.append(slips)
            return [{"factor": "x"}]

        monkeypatch.setattr(au, "calculate_correlation_data", recorder)
        app = app_env.app
        self._seed_stats_slips(app)  # 3 settled + 1 pending
        out = app.correlation_data()
        assert out == [{"factor": "x"}]
        statuses = {s.slip_status for s in calls[0]}
        assert statuses <= {"Won", "Lost"}
        assert len(calls[0]) == 3  # pending slip filtered out
