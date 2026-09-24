"""
test_footballpredictions.py
"""

import importlib

from bet_crawler.finders.FootballPredictionsFinder import FOOTBALLPREDICTIONS_NAME as NAME, FootballPredictionsFinder
from .finder_test_helpers import load_fixture, make_finder, relax_date_window

fp = importlib.import_module("bet_crawler.finders.FootballPredictionsFinder")


def _finder(**kw):
    finder, collector = make_finder(FootballPredictionsFinder, **kw)
    return relax_date_window(finder), collector


class TestFootballPredictions:
    def test_static_urls(self):
        finder, _ = _finder()
        assert finder.get_matches_urls() == list(fp.TOP_LEAGUES.keys())

    def test_parse_page_extracts_rows(self):
        finder, collector = _finder()
        url = next(iter(fp.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("footballpredictions", "league.html"))
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        assert m.predictions[0].source == NAME
        assert m.predictions[0].home == 2
        assert m.predictions[0].away == 1
        assert m.league is not None

    def test_broken_structure_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("footballpredictions", "broken.html"))
        assert len(collector) == 0

    def test_youth_team_skipped(self):
        html = load_fixture("footballpredictions", "league.html").replace("Arsenal", "Arsenal U19")
        finder, collector = _finder()
        url = next(iter(fp.TOP_LEAGUES))
        finder._parse_page(url, html)
        assert len(collector) == 0
