"""
test_vitibet.py
"""

import importlib

from bet_crawler.finders.VitibetFinder import VITIBET_NAME, VitibetFinder
from .finder_test_helpers import load_fixture, make_finder, patch_fetch, relax_date_window

vb = importlib.import_module("bet_crawler.finders.VitibetFinder")


def _finder(**kw):
    finder, collector = make_finder(VitibetFinder, **kw)
    return relax_date_window(finder), collector


class TestVitibet:
    def test_top_leagues_urls(self):
        finder, _ = _finder(top_leagues_only=True)
        assert finder.get_matches_urls() == list(vb.TOP_LEAGUES.keys())

    def test_non_top_kokos_branch(self, monkeypatch):
        hub = '<html><body><ul id="primarne"><kokos></kokos><li><a href="index.php?clanek=leagues&liga=39&lang=en"></a></li><li></li></ul></body></html>'
        patch_fetch(monkeypatch, vb, {vb.VITIBET_URL: hub})
        finder, _ = _finder(top_leagues_only=False)
        urls = finder.get_matches_urls()
        assert urls == ["https://www.vitibet.com" + "index.php?clanek=leagues&liga=39&lang=en"]

    def test_parse_page_extracts_matches(self):
        finder, collector = _finder()
        url = next(iter(vb.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("vitibet", "league.html"))
        assert len(collector) == 2
        m = collector.first
        assert m.home_team == "Juventus"
        assert m.away_team == "Napoli"
        assert m.datetime.year == 2035
        assert m.predictions[0].source == VITIBET_NAME
        assert m.predictions[0].home == 2.0
        assert m.league is not None

    def test_date_from_gradient_div(self):
        finder, collector = _finder()
        url = next(iter(vb.TOP_LEAGUES))
        finder._parse_page(url, load_fixture("vitibet", "league.html"))
        assert all(m.datetime.month == 6 and m.datetime.day == 15 for m in collector.matches)

    def test_broken_structure_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("vitibet", "broken.html"))
        assert len(collector) == 0
