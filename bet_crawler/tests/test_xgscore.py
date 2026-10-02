"""
test_xgscore.py
"""

import importlib

from bet_crawler.finders.xGScoreFinder import XGSCORE_NAME, xGScoreFinder
from .finder_test_helpers import fake_browser, load_fixture, make_finder, relax_date_window

xg = importlib.import_module("bet_crawler.finders.xGScoreFinder")


def _finder(**kw):
    finder, collector = make_finder(xGScoreFinder, **kw)
    return relax_date_window(finder), collector


class TestXGScore:
    def test_discovery_via_browser_returns_fixture_links(self, monkeypatch):
        fake_browser(monkeypatch, xg, {xg.XGSCORE_URL: load_fixture("xgscore", "discovery.html")})
        finder, _ = _finder()
        urls = finder.get_matches_urls()
        assert urls == ["https://xgscore.io/prediction/arsenal-chelsea", "https://xgscore.io/prediction/milan-inter"]

    def test_parse_page_extracts_match_and_dc_odds(self):
        finder, collector = _finder(contributes_odds=True)
        finder._parse_page("u", load_fixture("xgscore", "match.html"))
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        assert m.predictions[0].source == XGSCORE_NAME
        assert m.predictions[0].home == 2
        assert m.predictions[0].away == 1
        assert m.odds.dc_1x == 1.25
        assert m.odds.dc_12 == 1.30
        assert m.odds.dc_x2 == 1.45

    def test_finished_match_short_circuits(self, caplog):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("xgscore", "finished.html"))
        assert len(collector) == 0

    def test_broken_page_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("xgscore", "broken.html"))
        assert len(collector) == 0

    def test_odds_extraction_failure_returns_none(self):
        """No xgs-odds elements -> _extract_odds_from_html returns safe default."""
        html = load_fixture("xgscore", "match.html").replace("xgs-odds", "xgs-nope")
        finder, collector = _finder(contributes_odds=True)
        finder._parse_page("u", html)
        assert len(collector) == 1
        # Safe-default Odds object (all None) stripped? contributes_odds=True keeps it
        assert collector.first.odds is not None
        assert collector.first.odds.dc_1x is None
