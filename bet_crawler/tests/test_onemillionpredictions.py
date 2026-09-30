"""
test_onemillionpredictions.py
"""

import importlib

from bet_crawler.finders.OneMillionPredictionsFinder import ONE_MILLION_PREDICTIONS_NAME as NAME, OneMillionPredictionsFinder
from .finder_test_helpers import load_fixture, make_finder, patch_fetch, relax_date_window

omp = importlib.import_module("bet_crawler.finders.OneMillionPredictionsFinder")


def _finder(**kw):
    finder, collector = make_finder(OneMillionPredictionsFinder, **kw)
    return relax_date_window(finder), collector


class TestOneMillionPredictions:
    def test_top_leagues_static_urls(self):
        finder, _ = _finder(top_leagues_only=True)
        assert finder.get_matches_urls() == list(omp.TOP_LEAGUES.keys())

    def test_non_top_table_branch(self, monkeypatch):
        hub = '<html><body><table aria-label="Predictions by Days"><tr><td><a href="https://onemillionpredictions.com/day1/">D1</a></td></tr><tr><td><a href="https://onemillionpredictions.com/day2/">D2</a></td></tr></table></body></html>'
        patch_fetch(monkeypatch, omp, {omp.ONE_MILLION_PREDICTIONS_URL: hub})
        finder, _ = _finder(top_leagues_only=False)
        urls = finder.get_matches_urls()
        assert urls == ["https://onemillionpredictions.com/day2/correct-score/"]  # [1:] drops first

    def test_parse_page_stops_at_matchday(self):
        finder, collector = _finder()
        url = next(iter(omp.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("onemillionpredictions", "league.html"))
        assert len(collector) == 2
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.predictions[0].source == NAME
        assert m.predictions[0].home == 2
        assert m.league is not None

    def test_women_team_row_filtered(self):
        html = load_fixture("onemillionpredictions", "league.html").replace("Arsenal", "Arsenal W")
        finder, collector = _finder()
        url = next(iter(omp.TOP_LEAGUES))
        finder._parse_page(url, html)
        assert len(collector) == 1

    def test_broken_structure_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("onemillionpredictions", "broken.html"))
        assert len(collector) == 0
