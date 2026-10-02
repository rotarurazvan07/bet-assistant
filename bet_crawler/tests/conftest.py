"""Shared fixtures for crawler pipeline stage tests (issue #68)."""

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

import pytest

from bet_framework.core.Match import Match, Score

DT_BASE = datetime(2026, 9, 25, 15, 0, 0)


def make_match(home="Team A", away="Team B", dt=None, preds=None, odds=None, url=None, league=None):
    """Factory: build a Match quickly (mirrors root-suite helper)."""
    return Match(
        home_team=home,
        away_team=away,
        datetime=dt or DT_BASE,
        predictions=preds if preds is not None else [Score(source="src", home=3, away=1)],
        odds=odds,
        result_url=url,
        league=league,
    )


def make_chunk_db(path, matches):
    """Create a standalone chunk .db compatible with MatchesManager merge schema."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team_name     TEXT NOT NULL,
            away_team_name     TEXT NOT NULL,
            datetime           TEXT NOT NULL,
            predictions_scores TEXT,
            odds               TEXT,
            result_url         TEXT,
            league             TEXT
        )
    """
    )
    for m in matches:
        preds_json = json.dumps([s.__dict__ for s in m.predictions]) if m.predictions else None
        odds_json = json.dumps(asdict(m.odds)) if m.odds else None
        conn.execute(
            "INSERT INTO matches (home_team_name, away_team_name, datetime, predictions_scores, odds, result_url, league) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (m.home_team, m.away_team, m.datetime.isoformat(), preds_json, odds_json, m.result_url, m.league),
        )
    conn.commit()
    conn.close()
    return str(path)


class StubCrawler:
    """Stub finder: returns canned URLs and emits matches via callback."""

    def __init__(self, urls, matches=None, raise_on_get=False, raise_on_urls=False):
        self.urls = list(urls)
        self.matches = matches or []
        self.raise_on_get = raise_on_get
        self.raise_on_urls = raise_on_urls
        self.get_matches_urls_calls = 0
        self.get_matches_calls = 0

    def get_matches_urls(self):
        self.get_matches_urls_calls += 1
        if self.raise_on_urls:
            raise RuntimeError("stub url failure")
        return list(self.urls)

    def get_matches(self, urls):
        self.get_matches_calls += 1
        if self.raise_on_get:
            raise RuntimeError("stub scrape failure")
        for m in self.matches:
            self.add_match_callback(m)

    def add_match_callback(self, match):
        # assigned by StubFactory.create
        raise NotImplementedError


class StubFactory:
    """Factory stub mirroring CrawlerFactory's public surface for stage tests."""

    def __init__(self, runner_crawlers, url_to_crawler=None):
        # runner_crawlers: {runner: [StubCrawler|class, ...]}
        # url_to_crawler: {domain_core_name: StubCrawler|class, ...}
        # NOTE: keyed by domain core (e.g. 'alpha' for alpha.com/www.alpha.com),
        # because scrape.py groups by domain and passes group_urls[0] — after
        # prepare_scrape's shuffle that first URL is random within the group.
        self.runner_crawlers = runner_crawlers
        self.url_to_crawler = url_to_crawler or {}
        self.created = []

    def create_for_runner(self, runner, on_match_callback=None):
        return [self._spawn(c, on_match_callback) for c in self.runner_crawlers.get(runner, [])]

    def create_for_url(self, url, on_match_callback=None):
        from urllib.parse import urlparse

        domain = urlparse(url).netloc
        core = domain.split(".")[-2] if "." in domain else domain
        if core not in self.url_to_crawler:
            raise ValueError(f"No crawler registered for URL: {url}")
        return self._spawn(self.url_to_crawler[core], on_match_callback)

    def _spawn(self, crawler_or_class, on_match_callback):
        crawler = crawler_or_class() if isinstance(crawler_or_class, type) else crawler_or_class
        if hasattr(crawler, "add_match_callback") and on_match_callback is not None:
            crawler.add_match_callback = on_match_callback
        self.created.append(crawler)
        return crawler


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    """Run test with CWD inside tmp_path (prepare_scrape writes chunk files relative)."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def runner_sets_config():
    """Minimal runner-set + crawler-key config mirroring scraper_config.yaml shape."""
    return {
        "actions": ["alpha", "beta"],
        "local": ["gamma"],
        "test": ["delta"],
    }


def make_result_html_ft(score="2:1"):
    """Result page HTML that parses as finished (FT) with a score."""
    return f'<html><body><div id="status-container">FT</div><div id="livescore-container">{score}</div></body></html>'


def make_result_html_live(minute="63'", score="1:0"):
    """Result page HTML that parses as LIVE at minute with a score."""
    return f"<html><body><div id=\"status-container\">{minute}</div><div id='livescore-container'>{score}</div></body></html>"


def make_result_html_pending():
    """Result page HTML with no status markers -> parses as PENDING."""
    return "<html><body><p>Upcoming fixtures and odds preview.</p></body></html>"
