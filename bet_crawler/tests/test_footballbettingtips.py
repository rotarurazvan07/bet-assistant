"""
test_footballbettingtips.py
"""

import importlib

from datetime import date, timedelta
from bet_crawler.finders.FootballBettingTipsFinder import FOOTBALLBETTINGTIPS_NAME as NAME, FootballBettingTipsFinder
from .finder_test_helpers import load_fixture, make_finder, relax_date_window

fbt = importlib.import_module("bet_crawler.finders.FootballBettingTipsFinder")


def _finder(**kw):
    finder, collector = make_finder(FootballBettingTipsFinder, **kw)
    return relax_date_window(finder), collector


class TestFootballBettingTips:
    def test_url_construction_uses_today_and_tomorrow(self):
        finder, _ = _finder()
        urls = finder.get_matches_urls()
        today = date.today()
        assert f"https://www.footballbettingtips.org/tips/{today.strftime('%Y-%m-%d')}.html" in urls
        assert f"https://www.footballbettingtips.org/tips/{(today + timedelta(days=1)).strftime('%Y-%m-%d')}.html" in urls
        assert len(urls) == 2

    def test_parse_page_extracts_rows_with_odds(self):
        finder, collector = _finder(contributes_odds=True)
        finder._parse_page("u", load_fixture("footballbettingtips", "page.html"))
        assert len(collector) == 2
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.datetime.year == 2035
        assert m.predictions[0].source == NAME
        assert m.predictions[0].home == 2
        assert m.odds.home == 2.10
        assert m.odds.draw == 3.40
        assert m.odds.away == 3.75

    def test_row_without_anchor_skipped(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("footballbettingtips", "page.html"))
        names = [m.home_team for m in collector.matches]
        assert "header-less row skipped" not in str(names)

    def test_missing_odds_fall_back_to_none(self):
        html = load_fixture("footballbettingtips", "page.html").replace('class="desktop"', 'class="laptop"')
        finder, collector = _finder(contributes_odds=True)
        finder._parse_page("u", html)
        assert len(collector) == 2
        assert all(m.odds is None for m in collector.matches)

    def test_broken_page_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("footballbettingtips", "broken.html"))
        assert len(collector) == 0
