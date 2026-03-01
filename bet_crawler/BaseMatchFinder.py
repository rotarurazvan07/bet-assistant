from abc import abstractmethod
from datetime import datetime
import re
from typing import Callable, List, Optional, Tuple

from bet_framework.WebScraper import WebScraper, ScrapeMode

CURRENT_TIME = datetime.now()

SKIP_PATTERNS: List[Tuple[str, str]] = [  # TODO false skipping
    (r"\bU\d{2}s?\b", "Youth team"),
    (r"\bW\b", "Women's team"),
    (r"\bII\b", "Reserve team II"),
    (r"\bIII\b", "Reserve team III"),
    (r"\bB\b", "B team"),
    (r"\bC\b", "C team"),
    (r"\b(Am)\b", "Amateur"),
    (r"\bRes\b", "Reserve team"),
]


class BaseMatchFinder():
    """Base class for match finders.

    Subclasses implement:
        get_matches_urls()  — return list of URLs to scrape
        get_matches(urls)   — main runner, typically calls scrape_urls()
        _parse_page(url, html) — callback to parse a single page

    Each crawler sets MAX_CONCURRENCY to control parallelism.
    """

    def __init__(self, add_match_callback: Callable):
        super().__init__()
        self.add_match_callback = add_match_callback

    @abstractmethod
    def get_matches_urls(self):
        """Return list of URLs to scrape."""
        raise NotImplementedError()

    @abstractmethod
    def get_matches(self, urls):
        """Main scraping entrypoint."""
        raise NotImplementedError()

    @abstractmethod
    def _parse_page(self, url, html):
        """Parse a single scraped page. Used as callback for scrape_urls()."""
        raise NotImplementedError()

    def scrape_urls(self, urls, callback, mode=ScrapeMode.FAST, max_concurrency=1):
        """Scrape URLs with concurrency, calling callback(url, html) for each page.

        This is the main bridge between crawlers and the scraping engine.
        Crawlers just call this with their _parse_page and MAX_CONCURRENCY.
        """
        WebScraper.scrape(urls, callback, mode=mode, max_concurrency=max_concurrency)

    def add_match(self, match, force: bool = False) -> bool:
        """Add a match via callback after skip-pattern and date checks."""
        try:
            if not force:
                reason = self.skip_match_by_patterns(match.home_team, match.away_team)
                if reason:
                    print(f"SKIPPED by pattern: {match.home_team} vs {match.away_team} ({reason})")
                    return False
                if match.datetime is not None and not self.validate_match_date(match.datetime):
                    print(f"SKIPPED by date: {match.home_team} vs {match.away_team} ({match.datetime})")
                    return False
            self.add_match_callback(match)
            return True
        except Exception as e:
            print(f"Error while adding match: {e}")
            return False

    def skip_match_by_patterns(self, home_team_name: str, away_team_name: str, skip_patterns: Optional[List[Tuple[str, str]]] = None) -> Optional[str]:
        """Return the reason for skipping when any pattern matches either team."""
        patterns = skip_patterns if skip_patterns is not None else SKIP_PATTERNS
        return next((reason for pattern, reason in patterns
                     if re.search(pattern, home_team_name, re.I) or re.search(pattern, away_team_name, re.I)), None)

    def validate_match_date(self, match_datetime):
        """Keep only today's matches and future matches."""
        today_start = CURRENT_TIME.replace(hour=0, minute=0, second=0, microsecond=0)
        return match_datetime >= today_start