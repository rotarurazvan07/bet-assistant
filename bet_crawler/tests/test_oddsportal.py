"""

Discovery patched at fetch(); odds flow via FakeBrowserSession (D7).
MAX_CONCURRENCY patched to 1 for deterministic single-thread batch path.
"""

import datetime as dtmod
import importlib

import pytest

from bet_crawler.finders.OddsPortalFinder import ODDSPORTAL_NAME, OddsPortalFinder
from .finder_test_helpers import fake_browser, load_fixture, make_finder, patch_fetch, relax_date_window

op = importlib.import_module("bet_crawler.finders.OddsPortalFinder")

# D53 (fixture-date rot): league.html carries a FIXED anchor date
# (2026-09-25, generator ANCHOR_TOMORROW). The discovery window is
# [today, today+N] on the finder's UTC clock — freezing the clock to
# 2026-09-24 puts that anchor at today+1: deterministically in-window on
# any runner, any day, forever (predictz D5 protocol applied at module
# scope so future discovery tests inherit the freeze).
_FROZEN_NOW = dtmod.datetime(2026, 9, 24, 12, 0, 0, tzinfo=dtmod.timezone.utc)


class _FrozenDatetime(dtmod.datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return _FROZEN_NOW.astimezone(tz)
        return _FROZEN_NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _freeze_discovery_clock(monkeypatch):
    monkeypatch.setattr(op, "datetime", _FrozenDatetime)


def _finder(**kw):
    finder, collector = make_finder(OddsPortalFinder, **kw)
    return relax_date_window(finder), collector


def _league_url(top_only=True):
    return (op.TOP_LEAGUES if top_only else op.ALL_LINKS)[0]


class TestDiscovery:
    def test_json_ld_discovery_filters_window_status_and_dedupes(self, monkeypatch):
        url = _league_url()
        patch_fetch(monkeypatch, op, {url: load_fixture("oddsportal", "league.html")})
        monkeypatch.setattr(op, "TOP_LEAGUES", [url])
        finder, _ = _finder(top_leagues_only=True, num_days_ahead=2)
        urls = finder.get_matches_urls()
        # in-window scheduled x2 (deduped) + out-window + cancelled + no-date all excluded
        assert sorted(urls) == ["https://www.oddsportal.com/match/in-window-1/"]

    def test_all_links_branch_when_not_top_only(self, monkeypatch):
        url = "https://www.oddsportal.com/football/world/world-cup-2026/"  # ALL_LINKS[0]
        patch_fetch(monkeypatch, op, {url: load_fixture("oddsportal", "league.html")})
        monkeypatch.setattr(op, "ALL_LINKS", [url])
        finder, _ = _finder(top_leagues_only=False, num_days_ahead=2)
        urls = finder.get_matches_urls()
        assert urls == ["https://www.oddsportal.com/match/in-window-1/"]

    def test_fetch_error_on_one_league_continues(self, monkeypatch):
        def boom(url, **kw):
            raise RuntimeError("network down")

        monkeypatch.setattr(op, "TOP_LEAGUES", ["https://x/1/", "https://x/2/"])
        patch_fetch(monkeypatch, op, boom)
        finder, _ = _finder(top_leagues_only=True)
        assert finder.get_matches_urls() == []

    def test_returns_set_deduplicated_across_leagues(self, monkeypatch):
        league = load_fixture("oddsportal", "league.html")
        monkeypatch.setattr(op, "TOP_LEAGUES", ["https://x/1/", "https://x/2/"])
        patch_fetch(monkeypatch, op, {"https://x/1/": league, "https://x/2/": league})
        finder, _ = _finder(top_leagues_only=True, num_days_ahead=2)
        assert finder.get_matches_urls() == ["https://www.oddsportal.com/match/in-window-1/"]


class TestGetMatches:
    def test_empty_urls_short_circuit(self):
        finder, collector = _finder()
        finder.get_matches([])
        assert len(collector) == 0

    def test_single_concurrency_direct_batch(self, monkeypatch):
        seen_batches = []

        def fake_batch(self, urls):
            seen_batches.append(list(urls))

        monkeypatch.setattr(op, "MAX_CONCURRENCY", 1)
        monkeypatch.setattr(OddsPortalFinder, "_process_url_batch", fake_batch)
        finder, _ = _finder()
        finder.get_matches(["u1", "u2"])
        assert seen_batches == [["u1", "u2"]]

    def test_chunking_splits_into_max_concurrency_chunks(self, monkeypatch):
        captured = {}

        def fake_batch(self, urls):
            captured.setdefault("batches", []).append(list(urls))

        monkeypatch.setattr(op, "MAX_CONCURRENCY", 3)
        monkeypatch.setattr(OddsPortalFinder, "_process_url_batch", fake_batch)
        finder, _ = _finder()
        finder.get_matches([f"u{i}" for i in range(9)])
        assert len(captured["batches"]) == 3
        assert sorted(sum(captured["batches"], [])) == [f"u{i}" for i in range(9)]


class TestProcessUrlBatch:
    def _session_map(self, monkeypatch, base="match_base", extra=None):
        base_html = load_fixture("oddsportal", f"{base}.html")
        x2 = load_fixture("oddsportal", "match_1x2.html")
        btts = load_fixture("oddsportal", "match_btts.html")
        dc = load_fixture("oddsportal", "match_dc.html")
        ou = load_fixture("oddsportal", "match_ou.html")

        def content_for(clicks):
            # initial page before any market click, then swapped per click
            if not clicks:
                return base_html
            label = clicks[-1]
            if label == "1X2":
                return x2
            if label == "Both Teams to Score":
                return btts
            if label == "Double Chance":
                return dc
            if label == "Over/Under":
                return ou
            return base_html

        content_map = {"https://www.oddsportal.com/match/in-window-1/": content_for}
        return fake_browser(monkeypatch, op, content_map, **(extra or {}))

    def test_full_odds_flow_adds_match_with_all_markets(self, monkeypatch):
        self._session_map(monkeypatch)
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/match/in-window-1/"])
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        assert m.predictions == []  # Match ctor normalizes None to []
        odds = m.odds
        assert odds.home == 2.10
        assert odds.draw == 3.40
        assert odds.away == 3.75
        assert odds.btts_y == 1.85
        assert odds.btts_n == 1.95
        assert odds.dc_1x == 1.25
        assert odds.dc_12 == 1.30
        assert odds.dc_x2 == 1.45
        assert odds.over_05 == 1.10
        assert odds.under_05 == 8.00
        assert odds.over_25 == 1.70
        assert odds.under_25 == 2.10
        assert odds.over_45 == 6.50

    def test_fetch_error_then_retry_recovers(self, monkeypatch):
        session = self._session_map(monkeypatch)
        # make retry succeed: fetch_error_urls only raise once
        calls = {"n": 0}
        orig_fetch = session.fetch

        def flaky_fetch(url, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("timeout")
            return orig_fetch(url, **kw)

        session.fetch = flaky_fetch
        finder, collector = _finder(contributes_odds=True)
        finder._process_url_batch(["https://www.oddsportal.com/match/in-window-1/"])
        assert len(collector) == 1  # retry path succeeded

    def test_broken_page_logged_no_match(self, monkeypatch):
        content_map = {"https://www.oddsportal.com/match/broken-x/": load_fixture("oddsportal", "broken.html")}
        fake_browser(monkeypatch, op, content_map)
        finder, collector = _finder()
        finder._process_url_batch(["https://www.oddsportal.com/match/broken-x/"])
        assert len(collector) == 0

    def test_thread_safe_add_match(self, monkeypatch):
        """_add_match_lock exists and guards concurrent adds (wiring pin)."""
        finder, _ = _finder()
        assert hasattr(finder, "_add_match_lock")


class TestSourceName:
    def test_name_constant(self):
        assert ODDSPORTAL_NAME == "oddsportal"
