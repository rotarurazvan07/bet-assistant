"""

Covers BOTH classes: SoccerVistaFinder_per_league and SoccerVistaFinder_per_match.
League fixture uses TODAY+1 dates (closest-year search, decision D5).
"""

import importlib

from bet_crawler.finders.SoccerVistaFinder_per_league import SOCCERVISTA_NAME as NAME_PL, SoccerVistaFinder_per_league
from bet_crawler.finders.SoccerVistaFinder_per_match import SoccerVistaFinder_per_match
from .finder_test_helpers import load_fixture, make_finder, relax_date_window

sv_pl = importlib.import_module("bet_crawler.finders.SoccerVistaFinder_per_league")
sv_pm = importlib.import_module("bet_crawler.finders.SoccerVistaFinder_per_match")


def _finder(cls, **kw):
    finder, collector = make_finder(cls, **kw)
    return relax_date_window(finder), collector


class TestSoccerVistaPerLeague:
    def test_top_leagues_static_urls(self):
        finder, _ = _finder(SoccerVistaFinder_per_league, top_leagues_only=True)
        assert finder.get_matches_urls() == list(sv_pl.TOP_LEAGUES.keys())

    def test_league_page_parses_rows_with_result_url(self):
        finder, collector = _finder(SoccerVistaFinder_per_league)
        url = next(iter(sv_pl.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("soccervista", "league.html"))
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.predictions[0].source == NAME_PL
        assert m.predictions[0].home == 2
        assert m.result_url == "https://www.soccervista.com/match/arsenal-chelsea/"
        assert m.league is not None

    def test_ongoing_match_row_skipped(self):
        """Row whose date-cell is empty (ongoing) is skipped via date-parse failure."""
        html = load_fixture("soccervista", "league.html").replace(
            "</td><td><span>x</span><span>Arsenal", "</td><td></td><td><span>x</span><span>Arsenal", 1
        )
        finder, collector = _finder(SoccerVistaFinder_per_league)
        url = next(iter(sv_pl.TOP_LEAGUES))
        finder._parse_page(url, html)
        assert len(collector) == 0

    def test_broken_page_no_crash(self):
        finder, collector = _finder(SoccerVistaFinder_per_league)
        finder._parse_page("u", load_fixture("soccervista", "league_broken.html"))
        assert len(collector) == 0


class TestSoccerVistaPerMatch:
    def test_match_page_parses_metadata_prediction_odds(self):
        finder, collector = _finder(SoccerVistaFinder_per_match, contributes_odds=True)
        url = "https://www.soccervista.com/match/arsenal-chelsea/"
        finder._parse_page(url, load_fixture("soccervista", "match.html"))
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime == __import__("datetime").datetime(2035, 6, 15)
        assert m.predictions[0].home == 2
        assert m.odds.home == 2.10
        assert m.odds.draw == 3.40
        assert m.odds.away == 3.75
        assert m.odds.over_25 == 1.70
        assert m.odds.btts_y == 1.85
        assert m.result_url == url

    def test_missing_prediction_raises_no_match(self):
        html = load_fixture("soccervista", "match.html").replace("correctScorePrediction", "nothingHere")
        finder, collector = _finder(SoccerVistaFinder_per_match)
        finder._parse_page("u", html)
        assert len(collector) == 0

    def test_broken_match_page_no_crash(self):
        finder, collector = _finder(SoccerVistaFinder_per_match)
        finder._parse_page("u", load_fixture("soccervista", "match_broken.html"))
        assert len(collector) == 0

    def test_reserve_team_skipped(self):
        html = load_fixture("soccervista", "match.html").replace('"name": "Arsenal"', '"name": "Arsenal II"')
        finder, collector = _finder(SoccerVistaFinder_per_match)
        finder._parse_page("u", html)
        assert len(collector) == 0
