"""
test_betclan.py
"""

import importlib
import os

from datetime import datetime
from bet_crawler.finders.BetClanFinder import BETCLAN_NAME, BetClanFinder
from .finder_test_helpers import load_fixture, make_finder, patch_fetch, relax_date_window
from bet_crawler.crawl import load_runtime

bc = importlib.import_module("bet_crawler.finders.BetClanFinder")


def _finder(**kw):
    finder, collector = make_finder(BetClanFinder, **kw)
    return relax_date_window(finder), collector


class TestBetClan:
    def test_source_name_matches_crawler_keys(self):

        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        rt = load_runtime(os.path.join(root, "config"))
        assert BETCLAN_NAME in rt["factory"].crawler_keys

    def test_get_matches_urls_fetches_all_listing_pages(self, monkeypatch):
        listing = load_fixture("betclan", "listing.html")
        responses = dict.fromkeys(bc.URLS, listing)
        patch_fetch(monkeypatch, bc, responses)
        finder, _ = _finder()
        urls = finder.get_matches_urls()
        assert len(urls) == 8  # 4 pages x 2 anchors
        assert "https://www.betclan.com/predictions/match-1" in urls

    def test_parse_page_extracts_teams_date_score(self):
        finder, collector = _finder()
        finder._parse_page("https://www.betclan.com/predictions/match-1", load_fixture("betclan", "match.html"))
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime == datetime(2035, 6, 15)
        assert m.predictions[0].source == BETCLAN_NAME
        assert m.predictions[0].home == 2.0
        assert m.predictions[0].away == 1.0
        assert m.odds is None  # contributes_odds=False strips odds

    def test_broken_html_no_match_no_crash(self, caplog):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("betclan", "broken.html"))
        assert len(collector) == 0

    def test_get_matches_delegates_to_scrape(self, monkeypatch):
        seen = {}

        def fake_scrape(urls, callback, **kwargs):
            seen["urls"] = list(urls)
            callback(urls[0], load_fixture("betclan", "match.html"))

        monkeypatch.setattr(bc, "scrape", fake_scrape)
        finder, collector = _finder()
        finder.get_matches(["https://www.betclan.com/predictions/match-1"])
        assert seen["urls"] == ["https://www.betclan.com/predictions/match-1"]
        assert len(collector) == 1

    def test_youth_team_skipped_by_pattern(self):
        finder, collector = _finder()
        html = load_fixture("betclan", "match.html").replace("Arsenal", "Arsenal U19")
        finder._parse_page("u", html)
        assert len(collector) == 0
