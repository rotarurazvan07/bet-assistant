"""[P0] Unit tests for AppLogic league helpers (issue #59).

Covers get_leagues(): merge of framework-defined leagues with leagues
present in the loaded matches DataFrame.

All AppLogic instances are REAL, built via logic_test_helpers.build_app()
against tmp_path SQLite DBs — never workspace DBs.
"""

from __future__ import annotations

from bet_framework.core import leagues as framework_leagues

from tests.logic_test_helpers import build_app, make_match_row_db


class TestAppLogicLeagueHelpers:
    """League merging between framework definitions and DB contents."""

    def test_get_leagues_includes_framework_leagues(self, tmp_path, monkeypatch):
        """[P0] Built-in framework leagues are always present in the merged list."""
        env = build_app(tmp_path, monkeypatch, rows=[])
        try:
            out = env.app.get_leagues()
            assert "La Liga" in out
            assert "Premier League" in out
            assert "Champions League" in out
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()

    def test_get_leagues_merges_db_leagues_with_framework(self, tmp_path, monkeypatch):
        """[P0] DB-only leagues are unioned with the framework set (deduped)."""
        row = make_match_row_db(league="Regional Test League")
        env = build_app(tmp_path, monkeypatch, rows=[row])
        try:
            out = env.app.get_leagues()
            assert "Regional Test League" in out  # DB-only league present
            assert "La Liga" in out  # shared league deduped, still present
            assert out.count("La Liga") == 1
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()

    def test_get_leagues_returns_sorted_list(self, tmp_path, monkeypatch):
        """[P1] The merged list is sorted for deterministic display."""
        env = build_app(tmp_path, monkeypatch, rows=[make_match_row_db(league="Zeta League")])
        try:
            out = env.app.get_leagues()
            assert out == sorted(out)
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()

    def test_get_leagues_empty_db_returns_framework_only(self, tmp_path, monkeypatch):
        """[P1] With an empty matches DataFrame the framework set stands alone."""
        env = build_app(tmp_path, monkeypatch, rows=[])
        try:
            out = env.app.get_leagues()
            expected = sorted(
                {
                    getattr(framework_leagues, name)
                    for name in dir(framework_leagues)
                    if not name.startswith("__") and isinstance(getattr(framework_leagues, name), str)
                }
            )
            assert out == expected
        finally:
            env.app._assistant.conn.close()
            env.app._matches_manager.close()
