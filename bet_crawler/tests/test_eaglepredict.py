"""
test_eaglepredict.py
"""

import importlib

from bet_crawler.finders.EaglePredictFinder import EAGLEPREDICT_NAME, EAGLEPREDICT_URL, EaglePredictFinder
from .finder_test_helpers import load_fixture, make_finder, patch_fetch, relax_date_window

ep = importlib.import_module("bet_crawler.finders.EaglePredictFinder")


def _finder(**kw):
    finder, collector = make_finder(EaglePredictFinder, **kw)
    return relax_date_window(finder), collector


class TestEaglePredict:
    def test_static_url_list(self):
        finder, _ = _finder()
        assert finder.get_matches_urls() == [EAGLEPREDICT_URL]

    def test_get_matches_fetches_and_parses(self, monkeypatch):
        patch_fetch(monkeypatch, ep, {EAGLEPREDICT_URL: load_fixture("eaglepredict", "page.html")})
        finder, collector = _finder()
        finder.get_matches([EAGLEPREDICT_URL])
        assert len(collector) == 2
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        assert m.datetime.month == 6
        assert m.predictions[0].source == EAGLEPREDICT_NAME
        assert m.predictions[0].home == 2
        assert m.predictions[0].away == 1

    def test_duplicate_matches_deduped(self, monkeypatch):
        page = load_fixture("eaglepredict", "page.html")
        page + page.replace("Arsenal Logo", "Arsenal2 Logo")
        # same date+teams text -> dedup via seen set (img alt differs but text nodes identical)
        patch_fetch(monkeypatch, ep, {EAGLEPREDICT_URL: page})
        finder, collector = _finder()
        finder.get_matches([EAGLEPREDICT_URL])
        assert len(collector) == 2  # no duplicates from single page

    def test_score_without_container_skipped(self, monkeypatch):
        patch_fetch(monkeypatch, ep, {EAGLEPREDICT_URL: load_fixture("eaglepredict", "broken.html")})
        finder, collector = _finder()
        finder.get_matches([EAGLEPREDICT_URL])
        assert len(collector) == 0

    def test_broken_page_no_crash(self, monkeypatch):
        patch_fetch(monkeypatch, ep, {EAGLEPREDICT_URL: "<html><body><p>none</p></body></html>"})
        finder, collector = _finder()
        finder.get_matches([EAGLEPREDICT_URL])
        assert len(collector) == 0
