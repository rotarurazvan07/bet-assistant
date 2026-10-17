"""Structured logging assertions for finder skip and match pipeline events."""

import json

from bet_crawler.crawler_logging import configure_event_logging, disable_event_logging
from bet_crawler.finders.EaglePredictFinder import EaglePredictFinder
from bet_crawler.finders.LegitPredictFinder import LegitPredictFinder
from bet_crawler.tests.finder_test_helpers import make_finder


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_benign_shared_filters_are_structured_info_events(tmp_path, monkeypatch) -> None:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("SCRAPE_EVENT_LOG_PATH", str(path))
    configure_event_logging(str(path))
    finder, _ = make_finder(LegitPredictFinder)
    try:
        assert finder.add_match(_match(home="Arsenal U19")) is False
        assert finder.add_match(_match(dt=_past_datetime(finder))) is False
        events = [
            event
            for event in _records(path)
            if event["event"] == "match.skipped"
            and event["reason_code"]
            in {
                "team_pattern_excluded",
                "outside_match_date_window",
            }
        ]
        assert {event["reason_code"] for event in events} == {
            "team_pattern_excluded",
            "outside_match_date_window",
        }
        assert all(event["severity"] == "INFO" for event in events)
        assert events[0]["match_id"].startswith("Arsenal U19|")
    finally:
        disable_event_logging()


def test_eaglepredict_candidate_drops_are_warning_events(tmp_path, monkeypatch) -> None:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("SCRAPE_EVENT_LOG_PATH", str(path))
    configure_event_logging(str(path))
    finder, _ = make_finder(EaglePredictFinder)
    try:
        finder._parse_page(None, "<html><body><p>Correct Score: unavailable</p></body></html>")
        events = [event for event in _records(path) if event["event"] == "match.skipped"]
        assert events
        assert events[0]["severity"] == "WARNING"
        assert events[0]["reason_code"] == "score_not_found"
        assert events[0]["source_key"] == "eagle_predict"
        assert events[0]["candidate"] == "Correct Score: unavailable"
    finally:
        disable_event_logging()


def _match(home: str = "Arsenal", dt=None):
    from bet_framework.core.Match import Match, Score

    return Match(home, "Chelsea", dt, [Score("test", 2, 1)], None)


def _past_datetime(finder):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(finder.local_timezone)).replace(tzinfo=None) - timedelta(days=1)
