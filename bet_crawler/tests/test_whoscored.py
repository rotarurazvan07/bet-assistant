"""
test_whoscored.py
"""

import importlib

from bet_crawler.finders.WhoScoredFinder import WHOSCORED_NAME, WhoScoredFinder
from .finder_test_helpers import fake_browser, make_finder, relax_date_window

ws = importlib.import_module("bet_crawler.finders.WhoScoredFinder")


def _finder(**kw):
    finder, collector = make_finder(WhoScoredFinder, **kw)
    return relax_date_window(finder), collector


WS_PREVIEW = """<html><body><table class="grid">
<tr><td><a href="/matches/1">M1</a></td><td><a href="/teams">skip</a></td></tr>
</table></body></html>"""

WS_MATCH = """<html><body>
matchHeaderJson: JSON.parse('{"HomeTeamName": "Arsenal", "AwayTeamName": "Chelsea", "StartTimeUtc": "/Date(1772290800000)/"}'),
<div id="preview-prediction"><span class="predicted-score">2</span><span class="predicted-score">1</span></div>
</body></html>"""


class TestWhoScored:
    def test_discovery_via_browser_extracts_match_links(self, monkeypatch):
        fake_browser(monkeypatch, ws, {ws.WHOSCORED_URL + "previews": WS_PREVIEW})
        finder, _ = _finder()
        urls = finder.get_matches_urls()
        assert urls == [ws.WHOSCORED_URL + "/matches/1"]

    def test_parse_page_extracts_embedded_json_and_prediction(self):
        finder, collector = _finder()
        finder._parse_page("https://www.whoscored.com/matches/1", WS_MATCH)
        assert len(collector) == 1
        m = collector.first
        assert m.home_team == "Arsenal"
        assert m.away_team == "Chelsea"
        assert m.predictions[0].source == WHOSCORED_NAME
        assert m.predictions[0].home == 2
        assert m.predictions[0].away == 1

    def test_missing_match_header_json_short_circuits(self, caplog):
        finder, collector = _finder()
        finder._parse_page("u", "<html><body><p>no json here</p></body></html>")
        assert len(collector) == 0

    def test_broken_page_no_crash(self):
        finder, collector = _finder()
        finder._parse_page("u", "garbage not html")
        assert len(collector) == 0
