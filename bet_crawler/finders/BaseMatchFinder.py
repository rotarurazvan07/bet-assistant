from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

from scrape_kit import BaseFinder, Page, get_logger

logger = get_logger(__name__)


class BaseMatchFinder(BaseFinder):
    """Base class for match finders, extending scrape_kit.BaseFinder.

    Subclasses implement:
        get_urls()          — return list of URLs to scrape
        _parse_page(url, page) — callback to parse a single Page object

    Subclasses should set TIMEZONE to the source timezone of the scraped data:
        TIMEZONE = "UTC"             — WhoScored (UTC timestamps)
        TIMEZONE = "Asia/Bangkok"    — Forebet (UTC+7 displayed times)
    """

    TIMEZONE: str | None = None  # Subclasses override

    def __init__(
        self,
        add_match_callback: Callable,
        **runtime_settings,
    ) -> None:
        """Initialize the finder with runtime settings.

        Expected settings in runtime_settings:
            contributes_odds (bool)
            top_leagues_only (bool)
            num_days_ahead (int)
            local_timezone (str)
            skip_patterns (tuple[tuple[str, str], ...])
        """
        super().__init__(add_match_callback, **runtime_settings)
        self.contributes_odds = runtime_settings.get("contributes_odds", False)
        self.top_leagues_only = runtime_settings.get("top_leagues_only", False)
        self.num_days_ahead = runtime_settings.get("num_days_ahead", 1)
        self.local_timezone = runtime_settings.get("local_timezone", "UTC")
        self.skip_patterns = tuple(runtime_settings.get("skip_patterns", ()))
        # Discovery mode for distributed scraping
        self._discovery_mode = False
        self._discovered_urls: list[str] = []

    @abstractmethod
    def get_urls(self) -> list[str]:
        """Return list of URLs to scrape."""
        raise NotImplementedError()

    @abstractmethod
    def _parse_page(self, url: str, page: Page) -> None:
        """Parse a single Page object."""
        raise NotImplementedError()

    # ─────────────────────────── Discovery mode for distributed scraping ──────

    def get_match_urls(self) -> list[str]:
        """Discover and return all final match URLs for distributed scraping.
        
        This method runs scrape() in discovery mode, collecting URLs instead
        of parsing matches. Used by prepare_scrape for distributed workers.
        """
        self._discovery_mode = True
        self._discovered_urls = []
        try:
            self.scrape()
        finally:
            self._discovery_mode = False
        urls = self._discovered_urls
        self._discovered_urls = []
        return urls

    def collect_urls(self, urls: list[str]) -> None:
        """In discovery mode, collect URLs. Otherwise, scrape them.
        
        Subclasses should call this in _parse_discovery_page instead of
        directly calling self.scrape(urls).
        """
        if self._discovery_mode:
            self._discovered_urls.extend(urls)
        else:
            self.scrape(urls)

    # ─────────────────────────── Datetime normalisation ───────────────────────

    def normalise_datetime(self, dt: datetime) -> datetime:
        if self.TIMEZONE is None:
            return dt

        source_tz = ZoneInfo(self.TIMEZONE)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=source_tz)

        local_dt = dt.astimezone(ZoneInfo(self.local_timezone))

        logger.debug(f"Normalised datetime from {dt} ({self.TIMEZONE}) to {local_dt}")

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
                    logger.debug(f"SKIPPED by pattern: {match.home_team} vs {match.away_team} ({reason})")
                    return False
                if match.datetime is not None and not self.validate_match_date(match.datetime):
                    logger.debug(f"SKIPPED by date: {match.home_team} vs {match.away_team} ({match.datetime})")
                    return False
                if not self.contributes_odds:
                    match.odds = None  # ensure odds are not added by non-odds finders

            log_msg = f"ADDED: {match.home_team} vs {match.away_team} ({match.datetime})"
            if match.predictions:
                log_msg = f"ADDED: {match.predictions[0].source}: {match.home_team} vs {match.away_team} ({match.datetime}) {match.predictions[0].home}-{match.predictions[0].away}"
            logger.info(log_msg)

            self.add_result(match)
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

    def validate_match_date(self, match_datetime: datetime) -> bool:
        """Keep today's matches through the configured number of days ahead."""
        now = datetime.now(ZoneInfo(self.local_timezone))
        today = now.date()
        match_date = match_datetime.date()
        max_date = today + timedelta(days=self.num_days_ahead)
        return today <= match_date <= max_date

    @staticmethod
    def _detect_local_timezone() -> str | None:
        """Detect the local timezone as an IANA timezone string."""
        try:
            from tzlocal import get_localzone

            return str(get_localzone())
        except Exception:
            logger.warning("tzlocal not available")
            return None
