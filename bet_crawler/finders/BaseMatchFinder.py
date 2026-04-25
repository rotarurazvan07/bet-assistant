from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

SKIP_PATTERNS: list[tuple[str, str]] = [  # TODO false skipping
    (r"\bU\d{2}s?\b", "Youth team"),
    (r"\bW\b", "Women's team"),
    (r"\bII\b", "Reserve team II"),
    (r"\b2\b", "Reserve team 2"),
    (r"\bIII\b", "Reserve team III"),
    (r"\bB\b", "B team"),
    (r"\bC\b", "C team"),
    (r"\b(Am)\b", "Amateur"),
    (r"\bRes\b", "Reserve team"),
]

_LOCAL_TZ = "Europe/Bucharest" # this needs to be set because different datacenter computers can be everywhere.
# CURRENT_TIME is now computed dynamically in validate_match_date to avoid stale time
# logger.info(f"Detected System Timezone: {_LOCAL_TZ}")


class BaseMatchFinder:
    @staticmethod
    def _detect_local_timezone() -> str:
        """Detect the local timezone as an IANA timezone string."""
        # Try to use tzlocal if available
        try:
            from tzlocal import get_localzone
            return str(get_localzone())
        except:
            logger.warning("tzlocal not available")
            return None

    """Base class for match finders.

    Subclasses implement:
        get_matches_urls()  — return list of URLs to scrape
        get_matches(urls)   — main runner, typically calls scrape_urls()
        _parse_page(url, html) — callback to parse a single page

    Subclasses should set TIMEZONE to the source timezone of the scraped data:
        TIMEZONE = "UTC"             — WhoScored (UTC timestamps)
        TIMEZONE = "Asia/Bangkok"    — Forebet (UTC+7 displayed times)
        TIMEZONE = "Europe/London"   — UK-based sites

    If TIMEZONE is None, no normalisation is applied (legacy behaviour).
    """

    TIMEZONE: str | None = None  # Subclasses override

    def __init__(self, add_match_callback: Callable) -> None:
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

    # ─────────────────────────── Datetime normalisation ───────────────────────

    def normalise_datetime(self, dt: datetime) -> datetime:
        if self.TIMEZONE is None:
            return dt

        source_tz = ZoneInfo(self.TIMEZONE)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=source_tz)

        local_dt = dt.astimezone(ZoneInfo(_LOCAL_TZ))

        logger.info(f"Normalised datetime from {dt} ({self.TIMEZONE}) to {local_dt}")

        return local_dt.replace(tzinfo=None)

    # ─────────────────────────── Match processing ─────────────────────────────

    def add_match(self, match, force: bool = False) -> bool:
        """Add a match via callback after skip-pattern and date checks."""
        try:
            # Normalise the datetime before any validation
            if match.datetime is not None:
                match.datetime = self.normalise_datetime(match.datetime)

            if not force:
                reason = self.skip_match_by_patterns(match.home_team, match.away_team)
                if reason:
                    logger.info(f"SKIPPED by pattern: {match.home_team} vs {match.away_team} ({reason})")
                    return False
                if match.datetime is not None and not self.validate_match_date(match.datetime):
                    logger.info(f"SKIPPED by date: {match.home_team} vs {match.away_team} ({match.datetime})")
                    return False
            logger.info(
                f"ADDED: {match.predictions[0].source}: {match.home_team} vs {match.away_team} ({match.datetime}) {match.predictions[0].home}-{match.predictions[0].away}"
            )
            self.add_match_callback(match)
            return True
        except Exception as e:
            logger.error(f"Error while adding match: {e}")
            return False

    def skip_match_by_patterns(
        self,
        home_team_name: str,
        away_team_name: str,
        skip_patterns: list[tuple[str, str]] | None = None,
    ) -> str | None:
        """Return the reason for skipping when any pattern matches either team."""
        patterns = skip_patterns if skip_patterns is not None else SKIP_PATTERNS
        return next(
            (
                reason
                for pattern, reason in patterns
                if re.search(pattern, home_team_name, re.I) or re.search(pattern, away_team_name, re.I)
            ),
            None,
        )

    def validate_match_date(self, match_datetime):
        """Keep only today's matches and future matches."""
        # Compute current time dynamically to avoid stale time across midnight
        now = datetime.now(ZoneInfo(_LOCAL_TZ)).replace(tzinfo=None)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return match_datetime >= today_start
