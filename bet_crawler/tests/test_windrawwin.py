"""

Covers BOTH classes: WinDrawWinFinder_per_match and WinDrawWinFinder_per_league
(they share the CRAWLER_KEYS entry 'windrawwin').
"""

import importlib

from datetime import datetime
from bet_crawler.finders.WinDrawWinFinder_per_match import WINDRAWWIN_NAME as NAME_PM, WinDrawWinFinder_per_match
from bet_crawler.finders.WinDrawWinFinder_per_league import WinDrawWinFinder_per_league
from .finder_test_helpers import load_fixture, make_finder, patch_fetch, relax_date_window

wdw_pm = importlib.import_module("bet_crawler.finders.WinDrawWinFinder_per_match")
wdw_pl = importlib.import_module("bet_crawler.finders.WinDrawWinFinder_per_league")


def _finder(cls, **kw):
    finder, collector = make_finder(cls, **kw)
    return relax_date_window(finder), collector


class TestPerMatchUrls:
    def test_url_chain_hub_then_fixtures(self, monkeypatch):
        hub = load_fixture("windrawwin", "hub.html")
        fixtures = load_fixture("windrawwin", "fixtures.html")
        league_url = "https://www.windrawwin.com/tips/england-premier-league/"

        def fake_fetch(url, **kwargs):
            if url == wdw_pm.WINDRAWWIN_URL:
                return hub
            if url == league_url:
                return fixtures
            raise KeyError(url)

        patch_fetch(monkeypatch, wdw_pm, fake_fetch)
        finder, _ = _finder(WinDrawWinFinder_per_match)
        urls = finder.get_matches_urls()
        assert len(urls) == 2
        assert "https://www.windrawwin.com/match/arsenal-chelsea/" in urls

    def test_match_page_parses_all_odds_markets(self):
        finder, collector = _finder(WinDrawWinFinder_per_match, contributes_odds=True)
        finder._parse_page("https://www.windrawwin.com/match/arsenal-chelsea/", load_fixture("windrawwin", "match.html"))
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime == datetime(2035, 6, 15)
        assert m.predictions[0].source == NAME_PM
        assert m.predictions[0].home == 2.0
        assert m.odds.home == 2.10
        assert m.odds.btts_y == 1.85
        assert m.odds.over_25 == 1.70
        assert m.odds.over_15 == 1.30

    def test_closed_voting_skipped(self):
        finder, collector = _finder(WinDrawWinFinder_per_match)
        finder._parse_page("u", load_fixture("windrawwin", "closed.html"))
        assert len(collector) == 0

    def test_broken_match_page_no_crash(self):
        finder, collector = _finder(WinDrawWinFinder_per_match)
        finder._parse_page("u", "<html><body><p>error</p></body></html>")
        assert len(collector) == 0


class TestPerLeague:
    def test_top_leagues_static_urls(self):
        finder, _ = _finder(WinDrawWinFinder_per_league, top_leagues_only=True)
        assert finder.get_matches_urls() == list(wdw_pl.TOP_LEAGUES.keys())

    def test_non_top_hub_branch(self, monkeypatch):
        hub = '<html><body><div class="widetable"><tr><td>Cup and International Leagues</td></tr><tr><td><a href="https://www.windrawwin.com/tips/x/"></a></td></tr></div></body></html>'
        patch_fetch(monkeypatch, wdw_pl, {wdw_pl.WINDRAWWIN_URL: hub})
        finder, _ = _finder(WinDrawWinFinder_per_league, top_leagues_only=False)
        assert finder.get_matches_urls() == ["https://www.windrawwin.com/tips/x/"]

    def test_league_page_parses_rows_and_odds(self):
        finder, collector = _finder(WinDrawWinFinder_per_league, contributes_odds=True)
        url = next(iter(wdw_pl.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("windrawwin", "league.html"))
        assert len(collector) == 2
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        assert m.odds.home == 2.05
        assert m.odds.draw == 3.30
        assert m.odds.away == 3.80
        assert m.odds.over_25 == 1.65
        assert m.odds.btts_y == 1.90

    def test_league_page_no_matches_div(self):
        finder, collector = _finder(WinDrawWinFinder_per_league)
        finder._parse_page("u", load_fixture("windrawwin", "league_broken.html"))
        assert len(collector) == 0

    def test_women_team_row_skipped(self):
        html = load_fixture("windrawwin", "league.html").replace("Arsenal", "Arsenal W")
        finder, collector = _finder(WinDrawWinFinder_per_league)
        url = next(iter(wdw_pl.TOP_LEAGUES))
        finder._parse_page(url, html)
        assert len(collector) == 1  # only Liverpool vs Spurs row survives
