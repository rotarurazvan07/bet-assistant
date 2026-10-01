"""
test_scorepredictor.py
"""

import importlib

from datetime import datetime
from bet_crawler.finders.ScorePredictorFinder import SCOREPREDICTOR_NAME, ScorePredictorFinder
from .finder_test_helpers import load_fixture, make_finder, patch_fetch, relax_date_window

sp = importlib.import_module("bet_crawler.finders.ScorePredictorFinder")


def _finder(**kw):
    finder, collector = make_finder(ScorePredictorFinder, **kw)
    return relax_date_window(finder), collector


class TestScorePredictor:
    def test_top_leagues_static_urls(self):
        finder, _ = _finder(top_leagues_only=True)
        urls = finder.get_matches_urls()
        assert len(urls) == len(sp.TOP_LEAGUES)
        assert all(u.startswith("https://scorepredictor.net/") for u in urls)

    def test_non_top_leagues_fetches_categories(self, monkeypatch):
        hub = '<html><body><div class="block_categories"><a href="index.php?section=football&season=England">E</a><a href="#">skip</a></div></body></html>'
        patch_fetch(monkeypatch, sp, {sp.SCOREPREDICTOR_URL + "index.php?section=football": hub})
        finder, _ = _finder(top_leagues_only=False)
        urls = finder.get_matches_urls()
        assert urls == [sp.SCOREPREDICTOR_URL + "index.php?section=football&season=England"]

    def test_parse_page_extracts_rows(self):
        finder, collector = _finder()
        url = next(iter(sp.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("scorepredictor", "league.html"))
        assert len(collector) == 2  # U19-row has invalid scores -> skipped; rows 1+3 added
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.predictions[0].source == SCOREPREDICTOR_NAME
        assert m.predictions[0].home == 2
        assert m.predictions[0].away == 1
        assert m.league is not None  # top_leagues_only + url in map

    def test_invalid_score_row_skipped_not_fatal(self, caplog):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("scorepredictor", "league.html"))
        names = [m.home_team for m in collector.matches]
        assert "Youth U19 XI" not in names  # digit-gate fired before skip patterns

    def test_year_inference_uses_current_year(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("scorepredictor", "league.html"))
        assert collector.first.datetime.year == datetime.now().year
        assert collector.first.datetime.month == 6
        assert collector.first.datetime.day == 16

    def test_no_matches_guard(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("scorepredictor", "broken.html"))
        assert len(collector) == 0

    def test_broken_structure_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", "<html><body><p>nothing</p></body></html>")
        assert len(collector) == 0

    def test_odds_none_for_non_odds_finder(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("scorepredictor", "league.html"))
        assert all(m.odds is None for m in collector.matches)
