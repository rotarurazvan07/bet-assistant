"""[P0] Unit tests for AppLogic exclusion management (issue #59).

Covers: add/remove/clear/get_manual_excluded (in-memory server-lifetime
set), _combined_excluded (manual ∪ DB exclusions), get_pending_urls
(pending/live slip legs), and get_excluded_urls delegation.

All AppLogic instances are REAL, built via logic_test_helpers.build_app()
against tmp_path SQLite DBs — never workspace DBs.
"""

from __future__ import annotations

import pytest

from tests.logic_test_helpers import (
    build_app,
    make_leg_row,
    seed_slip,
)


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    env = build_app(tmp_path, monkeypatch)
    yield env
    env.app._assistant.conn.close()
    env.app._matches_manager.close()


class TestAppLogicExcludedManagement:
    """Manual exclusions, combined exclusions, pending/excluded URL rules."""

    # ── Manual excluded set ─────────────────────────────────────────────────

    def test_add_excluded_adds_url(self, app_env):
        """[P0] add_excluded puts the URL into the in-memory set."""
        app_env.app.add_excluded("https://example.com/match/0")
        assert "https://example.com/match/0" in app_env.app._manual_excluded

    def test_add_excluded_is_idempotent(self, app_env):
        """[P2] Adding the same URL twice keeps a single entry (set semantics)."""
        app_env.app.add_excluded("https://example.com/match/0")
        app_env.app.add_excluded("https://example.com/match/0")
        assert app_env.app.get_manual_excluded() == ["https://example.com/match/0"]

    def test_remove_excluded_discards_existing_url(self, app_env):
        """[P0] remove_excluded removes a previously added URL."""
        app = app_env.app
        app.add_excluded("https://example.com/match/0")
        app.remove_excluded("https://example.com/match/0")
        assert app.get_manual_excluded() == []

    def test_remove_excluded_missing_url_is_noop(self, app_env):
        """[P1] Removing an unknown URL is a safe no-op (discard semantics)."""
        app_env.app.remove_excluded("https://example.com/never-added")  # must not raise
        assert app_env.app.get_manual_excluded() == []

    def test_clear_excluded_empties_all_manual_urls(self, app_env):
        """[P0] clear_excluded drops every manual exclusion at once."""
        app = app_env.app
        for i in range(3):
            app.add_excluded(f"https://example.com/match/{i}")
        app.clear_excluded()
        assert app.get_manual_excluded() == []
        assert app._manual_excluded == set()

    def test_get_manual_excluded_returns_sorted_list(self, app_env):
        """[P1] get_manual_excluded exposes a sorted, deterministic list."""
        app = app_env.app
        app.add_excluded("https://example.com/match/2")
        app.add_excluded("https://example.com/match/0")
        app.add_excluded("https://example.com/match/1")
        assert app.get_manual_excluded() == [
            "https://example.com/match/0",
            "https://example.com/match/1",
            "https://example.com/match/2",
        ]

    # ── _combined_excluded: manual ∪ DB ─────────────────────────────────────

    def test_combined_excluded_merges_manual_and_db_urls(self, app_env):
        """[P0] Manual exclusions and DB (pending-slip) URLs are unioned."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Pending", result_url="https://example.com/match/0")])
        app.add_excluded("https://example.com/match/1")
        combined = app._combined_excluded()
        assert set(combined) == {
            "https://example.com/match/0",  # from DB (pending slip leg)
            "https://example.com/match/1",  # manual
        }

    def test_combined_excluded_manual_only_when_db_empty(self, app_env):
        """[P1] With no DB exclusions the combined list is the manual set."""
        app = app_env.app
        app.add_excluded("https://example.com/match/2")
        assert app._combined_excluded() == ["https://example.com/match/2"]

    def test_combined_excluded_db_only_when_manual_empty(self, app_env):
        """[P1] With no manual exclusions the combined list is the DB set."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Pending", result_url="https://example.com/match/0")])
        assert app._combined_excluded() == ["https://example.com/match/0"]

    def test_combined_excluded_deduplicates_overlap(self, app_env):
        """[P1] A URL both manual and in the DB appears exactly once."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Won", result_url="https://example.com/match/0")])
        app.add_excluded("https://example.com/match/0")
        assert app._combined_excluded() == ["https://example.com/match/0"]

    # ── get_pending_urls: pending/live slip legs ─────────────────────────────

    def test_get_pending_urls_returns_pending_slip_leg_urls(self, app_env):
        """[P0] Pending slip legs contribute their result URLs."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Pending", result_url="https://example.com/match/0")])
        assert app.get_pending_urls() == {"https://example.com/match/0"}

    def test_get_pending_urls_includes_live_slip_legs(self, app_env):
        """[P0] A slip with a Live leg derives status 'Live' and still reports URLs."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Live", result_url="https://example.com/match/1")])
        assert app.get_pending_urls() == {"https://example.com/match/1"}

    def test_get_pending_urls_excludes_settled_slips(self, app_env):
        """[P1] Won/Lost slips no longer report pending URLs."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Won", result_url="https://example.com/match/0")])
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Lost", result_url="https://example.com/match/1")])
        assert app.get_pending_urls() == set()

    def test_get_pending_urls_mixed_leg_slip_counts_as_pending(self, app_env):
        """[P1] A slip with Won + Pending legs derives 'Pending'; its pending URL counts."""
        app = app_env.app
        seed_slip(
            app,
            date_generated="2030-01-01",
            total_odds=1.9,
            units=1.0,
            legs=[
                make_leg_row(status="Won", result_url="https://example.com/match/0"),
                make_leg_row(status="Pending", result_url="https://example.com/match/1"),
            ],
        )
        assert app.get_pending_urls() == {"https://example.com/match/1"}

    # ── get_excluded_urls delegation ────────────────────────────────────────

    def test_get_excluded_urls_delegates_to_assistant(self, app_env):
        """[P1] get_excluded_urls mirrors BetAssistant exclusion rules: settled
        legs excluded forever, pending legs while their slip is alive."""
        app = app_env.app
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Won", result_url="https://example.com/match/0")])
        seed_slip(app, date_generated="2030-01-01", total_odds=1.9, units=1.0,
                  legs=[make_leg_row(status="Pending", result_url="https://example.com/match/1")])
        assert set(app.get_excluded_urls()) == {
            "https://example.com/match/0",
            "https://example.com/match/1",
        }
