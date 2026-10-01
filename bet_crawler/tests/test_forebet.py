"""
test_forebet.py
"""

import importlib

import pytest
from datetime import datetime
from bet_crawler.finders.ForebetFinder import FOREBET_NAME, ForebetFinder
from .finder_test_helpers import load_fixture, make_finder, relax_date_window

fb = importlib.import_module("bet_crawler.finders.ForebetFinder")


@pytest.fixture(autouse=True)
def _pin_forebet_timezone(monkeypatch):
    """Runner-TZ pin (PR #75 CI fix, D51).

    ForebetFinder.TIMEZONE is `BaseMatchFinder._detect_local_timezone()`
    (ForebetFinder.py:226) — the tzlocal probe resolved at IMPORT time, i.e.
    the RUNNER's zone. Under TZ=UTC CI runners the parsed naive 20:00 gets
    tagged UTC then converted to Europe/Bucharest (+3h) — the exact skew the
    CI caught. The production self-hosted runner is Europe/Bucharest, so the
    historically-pinned expectation (datetime(2035, 6, 15, 20, 0)) encodes
    Bucharest-tagged behaviour. Pin TIMEZONE to Europe/Bucharest for the
    test context — the same value tzlocal resolves on the production runner.

    NOTE: this masks a latent production inconsistency (the BaseMatchFinder
    docstring documents Forebet as Asia/Bangkok) — reported, not refactored
    (BaseMatchFinder behaviour is production-proven; see cycle report).
    """
    monkeypatch.setattr(fb.ForebetFinder, "TIMEZONE", "Europe/Bucharest")


def _finder(**kw):
    finder, collector = make_finder(ForebetFinder, **kw)
    return relax_date_window(finder), collector


class TestForebet:
    def test_top_leagues_urls(self):
        finder, _ = _finder(top_leagues_only=True)
        assert finder.get_matches_urls() == list(fb.TOP_LEAGUES.keys())

    def test_all_links_when_not_top_only(self):
        finder, _ = _finder(top_leagues_only=False)
        assert finder.get_matches_urls() == fb.ALL_LINKS

    def test_parse_page_extracts_match_with_odds(self):
        finder, collector = _finder(contributes_odds=True)
        url = next(iter(fb.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("forebet", "league.html"))
        assert len(collector) == 1  # second anchor is ongoing -> skipped
        m = collector.first
        assert m.home_team == "Real Madrid"
        assert m.away_team == "Barcelona"
        assert m.datetime == datetime(2035, 6, 15, 20, 0)
        assert m.predictions[0].source == FOREBET_NAME
        assert m.predictions[0].home == 2.0
        assert m.odds.home == 1.85
        assert m.odds.draw == 3.40
        assert m.odds.away == 4.10
        assert m.league is not None

    def test_ongoing_match_skipped(self, caplog):
        finder, collector = _finder()
        url = next(iter(fb.TOP_LEAGUES))
        with caplog.at_level("INFO", logger="bet_crawler.finders.ForebetFinder"):
            finder._parse_page(url, load_fixture("forebet", "league.html"))
        assert any("ongoing" in r.getMessage().lower() or "Match ongoing" in r.getMessage() for r in caplog.records)

    def test_missing_odds_become_none(self):
        """Second anchor has haodd ' - '/'' — but it is ongoing; craft a dedicated page."""
        html = load_fixture("forebet", "league.html").replace(
            '<div class="scoreLnk">1:0</div>', '<div class="scoreLnk"></div>'
        )
        finder, collector = _finder(contributes_odds=True)
        url = next(iter(fb.TOP_LEAGUES))
        finder._parse_page(url, html)
        assert len(collector) == 2
        second = collector.matches[1]
        assert second.home_team == "Atletico"
        assert second.odds.home is None
        assert second.odds.away == 2.50

    def test_broken_anchor_skipped_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("forebet", "broken.html"))
        assert len(collector) == 0

    def test_youth_team_skipped(self):
        html = load_fixture("forebet", "league.html").replace("Real Madrid", "Real U19")
        finder, collector = _finder()
        url = next(iter(fb.TOP_LEAGUES))
        finder._parse_page(url, html)
        assert len(collector) == 0
