"""
test_footballbettingtips.py
"""

import importlib
from datetime import date, timedelta

from bet_crawler.finders.FootballBettingTipsFinder import FOOTBALLBETTINGTIPS_NAME as NAME
from bet_crawler.finders.FootballBettingTipsFinder import FootballBettingTipsFinder

from .finder_test_helpers import fake_browser, load_fixture, make_finder, relax_date_window

fbt = importlib.import_module("bet_crawler.finders.FootballBettingTipsFinder")


def _finder(**kw):
    finder, collector = make_finder(FootballBettingTipsFinder, **kw)
    return relax_date_window(finder), collector


class TestFootballBettingTips:
    def test_url_construction_uses_today_and_tomorrow(self) -> None:
        finder, _ = _finder()
        urls = finder.get_matches_urls()
        today = date.today()
        assert f"https://www.footballbettingtips.org/tips/{today.strftime('%Y-%m-%d')}.html" in urls
        assert f"https://www.footballbettingtips.org/tips/{(today + timedelta(days=1)).strftime('%Y-%m-%d')}.html" in urls
        assert len(urls) == 2

    def test_parse_page_extracts_rows_with_odds(self) -> None:
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

    def test_row_without_anchor_skipped(self) -> None:
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("footballbettingtips", "page.html"))
        names = [m.home_team for m in collector.matches]
        assert "header-less row skipped" not in str(names)

    def test_missing_odds_fall_back_to_none(self) -> None:
        html = load_fixture("footballbettingtips", "page.html").replace('class="desktop"', 'class="laptop"')
        finder, collector = _finder(contributes_odds=True)
        finder._parse_page("u", html)
        assert len(collector) == 2
        assert all(m.odds is None for m in collector.matches)

    def test_broken_page_no_crash(self) -> None:
        finder, collector = _finder()
        finder._parse_page("u", load_fixture("footballbettingtips", "broken.html"))
        assert len(collector) == 0

    def test_get_matches_browser_path_collects_matches(self, monkeypatch) -> None:
        page = load_fixture("footballbettingtips", "page.html")
        urls = [
            "https://www.footballbettingtips.org/tips/2035-01-01.html",
            "https://www.footballbettingtips.org/tips/2035-01-02.html",
        ]
        content_map = {urls[0]: page, urls[1]: page}
        fake_browser(monkeypatch, fbt, content_map)

        def fake_fetch_page(session, url, wait_until, timeout_ms):
            return content_map[url]

        monkeypatch.setattr(fbt, "fetch_page", fake_fetch_page)
        finder, collector = _finder(contributes_odds=True)
        finder.get_matches(urls)
        assert len(collector) == 4
        assert collector.first.home_team == "Arsenal"

    def test_get_matches_skips_failed_fetch_and_logs_retry(self, monkeypatch, caplog) -> None:
        page = load_fixture("footballbettingtips", "page.html")
        good_url = "https://www.footballbettingtips.org/tips/2035-01-01.html"
        bad_url = "https://www.footballbettingtips.org/tips/2035-01-02.html"
        content_map = {good_url: page, bad_url: page}
        fake_browser(monkeypatch, fbt, content_map)

        def fake_fetch_page(session, url, wait_until, timeout_ms):
            if url == bad_url:
                raise RuntimeError("still blocked after browser fetch")
            return content_map[url]

        monkeypatch.setattr(fbt, "fetch_page", fake_fetch_page)
        finder, collector = _finder()
        with caplog.at_level("INFO", logger="bet_crawler.finders.FootballBettingTipsFinder"):
            finder.get_matches([bad_url, good_url])
        assert len(collector) == 2
        retry_records = [r for r in caplog.records if getattr(r, "event", None) == "source.fetch.retry"]
        assert retry_records, "expected a source.fetch.retry event for the failed url"
        assert any("still blocked after browser fetch" in r.getMessage() for r in retry_records)
