"""
test_legitpredict.py
"""

import importlib

from datetime import date, timedelta
from bet_crawler.finders.LegitPredictFinder import LEGITPREDICT_NAME as NAME, LegitPredictFinder
from .finder_test_helpers import load_fixture, make_finder, relax_date_window

lp = importlib.import_module("bet_crawler.finders.LegitPredictFinder")


def _finder(**kw):
    finder, collector = make_finder(LegitPredictFinder, **kw)
    return relax_date_window(finder), collector


class TestLegitPredict:
    def test_urls_cover_num_days_ahead(self):
        finder, _ = _finder(num_days_ahead=3)
        urls = finder.get_matches_urls()
        assert len(urls) == 4  # today + 3 days
        today = date.today()
        assert f"{lp.LEGITPREDICT_URL}{today.strftime('%d-%m-%Y')}" in urls
        assert f"{lp.LEGITPREDICT_URL}{(today + timedelta(days=3)).strftime('%d-%m-%Y')}" in urls

    def test_empty_day_guard(self):
        finder, collector = _finder()
        finder._parse_page(lp.LEGITPREDICT_URL + "25-09-2026", load_fixture("legitpredict", "empty.html"))
        assert len(collector) == 0

    def test_parse_page_extracts_rows(self):
        finder, collector = _finder()
        finder._parse_page(lp.LEGITPREDICT_URL + "25-09-2026", load_fixture("legitpredict", "page.html"))
        assert len(collector) == 2  # third row has garbage score -> per-row skip
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.day == 25
        assert m.predictions[0].source == NAME
        assert m.predictions[0].home == 2

    def test_bad_row_skipped_not_fatal(self, caplog):
        finder, collector = _finder()
        with caplog.at_level("ERROR", logger="bet_crawler.finders.LegitPredictFinder"):
            finder._parse_page(lp.LEGITPREDICT_URL + "25-09-2026", load_fixture("legitpredict", "page.html"))
        assert any("SKIPPED" in r.getMessage() for r in caplog.records)

    def test_broken_page_no_crash(self):
        finder, collector = _finder()
        finder._parse_page(lp.LEGITPREDICT_URL + "25-09-2026", load_fixture("legitpredict", "broken.html"))
        assert len(collector) == 0

    def test_url_dt_parsing(self):
        finder, collector = _finder()
        finder._parse_page(lp.LEGITPREDICT_URL + "15-06-2035", load_fixture("legitpredict", "page.html"))
        assert collector.first.datetime.year == 2035
        assert collector.first.datetime.month == 6
