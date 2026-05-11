import re
from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scrape_kit import get_logger

logger = get_logger(__name__)

class BaseMatchFinder:
    @staticmethod
    def _detect_local_timezone() -> str:
        """Detect the local timezone as an IANA timezone string."""
        # Try to use tzlocal if available
        try:
            from tzlocal import get_localzone

            return str(get_localzone())
        except Exception:
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

    def __init__(
        self,
        add_match_callback: Callable,
        *,
        contributes_odds: bool,
        num_days_ahead: int,
        local_timezone: str,
        skip_patterns: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    ) -> None:
        super().__init__()
        self.add_match_callback = add_match_callback
        self.contributes_odds = contributes_odds
        self.num_days_ahead = num_days_ahead
        self.local_timezone = local_timezone
        self.skip_patterns = tuple(skip_patterns)

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

        local_dt = dt.astimezone(ZoneInfo(self.local_timezone))

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
                if not self.contributes_odds:
                    match.odds = None  # ensure odds are not added by non-odds finders
            logger.info(
                f"ADDED: {match.predictions[0].source}: {match.home_team} vs {match.away_team} ({match.datetime}) {match.predictions[0].home}-{match.predictions[0].away}"
            ) if match.predictions else logger.info(f"ADDED: {match.home_team} vs {match.away_team} ({match.datetime})")
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
        patterns = skip_patterns if skip_patterns is not None else self.skip_patterns
        return next(
            (
                reason
                for pattern, reason in patterns
                if re.search(pattern, home_team_name, re.I) or re.search(pattern, away_team_name, re.I)
            ),
            None,
        )

    def validate_match_date(self, match_datetime):
        """Keep today's matches through the configured number of days ahead."""
        # Compute current time dynamically to avoid stale time across midnight
        now = datetime.now(ZoneInfo(self.local_timezone)).replace(tzinfo=None)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        max_datetime = today_start + timedelta(days=self.num_days_ahead + 1)
        return today_start <= match_datetime < max_datetime
