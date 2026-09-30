"""

Discovery patched at fetch(); odds flow via FakeBrowserSession (D7).
MAX_CONCURRENCY patched to 1 for deterministic single-thread batch path.
"""

import datetime as dtmod
import importlib

import pytest

from bet_crawler.finders.BetExplorerFinder import BETEXPLORER_NAME, BetExplorerFinder
from .finder_test_helpers import fake_browser, load_fixture, make_finder, patch_fetch, relax_date_window

be = importlib.import_module("bet_crawler.finders.BetExplorerFinder")

# D53 (fixture-date rot): league.html carries a FIXED anchor date
# (2026-09-25, generator ANCHOR_TOMORROW). Freeze the discovery clock to
# 2026-09-24 so the anchor sits at today+1 — deterministically in-window on
# any runner, any day (predictz D5 protocol; mirrors test_oddsportal.py).
_FROZEN_NOW = dtmod.datetime(2026, 9, 24, 12, 0, 0, tzinfo=dtmod.timezone.utc)


class _FrozenDatetime(dtmod.datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return _FROZEN_NOW.astimezone(tz)
        return _FROZEN_NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _freeze_discovery_clock(monkeypatch):
    monkeypatch.setattr(be, "datetime", _FrozenDatetime)


def _finder(**kw):
    finder, collector = make_finder(BetExplorerFinder, **kw)
    return relax_date_window(finder), collector


class TestDiscovery:
    def test_json_ld_discovery_filters_and_dedupes(self, monkeypatch):
        url = be.TOP_LEAGUES[0]
        patch_fetch(monkeypatch, be, {url: load_fixture("betexplorer", "league.html")})
        monkeypatch.setattr(be, "TOP_LEAGUES", [url])
        finder, _ = _finder(top_leagues_only=True, num_days_ahead=2)
        urls = finder.get_matches_urls()
        # in-window scheduled kept; out-window + postponed (dict status) excluded
        assert urls == ["https://www.betexplorer.com/match/in-window-1/"]

    def test_fetch_error_continues_to_next_league(self, monkeypatch):
        def boom(url, **kw):
            raise RuntimeError("network down")

        monkeypatch.setattr(be, "TOP_LEAGUES", ["https://x/1/", "https://x/2/"])
        patch_fetch(monkeypatch, be, boom)
        finder, _ = _finder(top_leagues_only=True)
        assert finder.get_matches_urls() == []


class TestGetMatches:
    def test_empty_urls_short_circuit(self):
        finder, collector = _finder()
        finder.get_matches([])
        assert len(collector) == 0

    def test_single_concurrency_direct_batch(self, monkeypatch):
        seen = []

        def fake_batch(self, urls):
            seen.append(list(urls))

        monkeypatch.setattr(be, "MAX_CONCURRENCY", 1)
        monkeypatch.setattr(BetExplorerFinder, "_process_url_batch", fake_batch)
        finder, _ = _finder()
        finder.get_matches(["u1", "u2"])
        assert seen == [["u1", "u2"]]


class TestProcessUrlBatch:
    def _session_map(self, monkeypatch, fetch_error=False):
        base_html = load_fixture("betexplorer", "match_base.html")
        x2 = load_fixture("betexplorer", "match_1x2.html")
        btts = load_fixture("betexplorer", "match_btts.html")
        dc = load_fixture("betexplorer", "match_dc.html")
        ou = load_fixture("betexplorer", "match_ou.html")

        def content_for(clicks):
            if not clicks:
                return base_html
            # BetExplorer clicks pass full selectors (single-arg click()); scan
            # the click history (newest first) for market keywords.
            for entry in reversed(clicks):
                if "1X2" in entry:
                    return x2
                if "Both Teams" in entry:
                    return btts
                if "Double Chance" in entry:
                    return dc
                if "Over/Under" in entry or "li#all" in entry:
                    return ou
            return base_html

        content_map = {"https://www.betexplorer.com/match/in-window-1/": content_for}
        err = ("https://www.betexplorer.com/match/in-window-1/",) if fetch_error else ()
        return fake_browser(monkeypatch, be, content_map, fetch_error_urls=err)

    def test_full_odds_flow_adds_match(self, monkeypatch):
        self._session_map(monkeypatch)
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.betexplorer.com/match/in-window-1/"])
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        odds = m.odds
        assert odds.home == 2.10
        assert odds.draw == 3.40
        assert odds.away == 3.75
        assert odds.btts_y == 2.10  # first btts cell value from fixture
        assert odds.dc_1x == 2.10
        assert odds.over_05 == 1.10
        assert odds.under_05 == 8.00
        assert odds.over_25 == 1.70
        assert odds.under_25 == 2.10
        assert odds.over_45 == 6.50

    def test_retry_after_fetch_error(self, monkeypatch):
        session = self._session_map(monkeypatch, fetch_error=True)
        calls = {"n": 0}
        orig_fetch = session.fetch

        def flaky_fetch(url, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("timeout")
            return orig_fetch(url, **kw)

        session.fetch_error_urls = ()  # clear: only first call should fail
        session.fetch = flaky_fetch
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.betexplorer.com/match/in-window-1/"])
        assert len(collector) == 1

    def test_missing_critical_selectors_skips_url(self, monkeypatch):
        content_map = {"https://www.betexplorer.com/match/empty/": "<html><body><p>nothing</p></body></html>"}
        fake_browser(monkeypatch, be, content_map)
        finder, collector = _finder()
        finder._process_url_batch(["https://www.betexplorer.com/match/empty/"])
        assert len(collector) == 0

    def test_broken_page_no_crash(self, monkeypatch):
        content_map = {"https://www.betexplorer.com/match/broken/": load_fixture("betexplorer", "broken.html")}
        fake_browser(monkeypatch, be, content_map)
        finder, collector = _finder()
        finder._process_url_batch(["https://www.betexplorer.com/match/broken/"])
        assert len(collector) == 0


class TestSourceName:
    def test_name_constant(self):
        assert BETEXPLORER_NAME == "betexplorer"
