from abc import abstractmethod
from datetime import datetime, timedelta
import threading
import time
import re
from typing import Callable, Iterable, List, Optional, Tuple

from bet_framework.SettingsManager import settings_manager
from bet_framework.WebScraper import WebScraper

CURRENT_TIME = datetime.now()

SKIP_PATTERNS: List[Tuple[str, str]] = [ # TODO false skipping
    (r"\bU\d{2}s?\b", "Youth team"),
    (r"\bW\b", "Women's team"),
    (r"\bII\b", "Reserve team II"),
    (r"\bIII\b", "Reserve team III"),
    (r"\bB\b", "B team"),
    (r"\bC\b", "C team"),
    (r"\b(Am)\b", "Amateur"),
]


class BaseMatchFinder():
    """Base class for match finders providing shared helpers and defaults.

    This class intentionally does not change finder logic — it provides
    utilities that concrete finders can use to reduce duplication.
    """

    def __init__(self, add_match_callback: Callable):
        super().__init__()
        self.add_match_callback = add_match_callback
        # Common state used by finders
        # TODO - useless
        self._scanned_matches = 0
        self._stop_logging = False
        self.web_scraper: Optional[WebScraper] = None

    @abstractmethod
    def get_matches(self):
        """Subclasses must implement the scraping entrypoint."""
        raise NotImplementedError()

    def add_match(self, match, force: bool = False) -> bool:
        """Wrapper to add a match using the configured callback after applying
        standard checks (skip patterns and date validation).

        If `force` is True the checks are skipped and the callback is always
        invoked. Returns True when the match was passed to the callback,
        False when it was skipped.
        """
        try:
            # Extract team names if present
            home_name = None
            away_name = None
            try:
                home_name = match.home_team.name
            except Exception:
                pass
            try:
                away_name = match.away_team.name
            except Exception:
                pass

            # Skip by patterns (e.g., youth, reserve teams)
            if not force and home_name and away_name:
                reason = self.skip_match_by_patterns(home_name, away_name)
                if reason:
                    # Best-effort log; don't raise if skipped
                    print(f"SKIPPED by pattern: {home_name} vs {away_name} ({reason})")
                    return False

            # Validate date (keep only today's matches by default)
            if not force:
                try:
                    match_dt = match.datetime
                except Exception:
                    match_dt = None
                if match_dt is not None and not self.validate_match_date(match_dt):
                    print(f"SKIPPED by date: {home_name} vs {away_name} ({match_dt})")
                    return False

            # Passed checks - invoke the configured callback
            self.add_match_callback(match)
            return True
        except Exception as e:
            # Don't let errors in the wrapper break finders; print and skip
            print(f"Error while adding match: {e}")
            return False

    # --- Helpers -------------------------------------------------
    def get_web_scraper(self,
                        profile: Optional[str] = None,
                        headless: Optional[bool] = None,
                        stealth_mode: Optional[bool] = None,
                        max_retries: Optional[int] = None,
                        min_request_delay: Optional[float] = None,
                        detection_keywords: Optional[List[str]] = None,
                        **kwargs) -> WebScraper:
        """Create or return a shared WebScraper using defaults merged with
        values from `config/web_scraper_config.yaml` (if loaded into
        SettingsManager) and any explicit overrides.
        """
        # Load defaults from settings manager if present. Be flexible with common
        # naming: either 'web_scraper', 'web_scraper_config' or older 'webdriver'.
        cfg = settings_manager.get_config('web_scraper_config')

        # If the loaded config nests web_scraper under a top-level key, normalize it
        if isinstance(cfg, dict) and 'web_scraper' in cfg:
            cfg = cfg.get('web_scraper') or {}

        # apply base config overrides
        headless = cfg.get('headless', headless)
        stealth_mode = cfg.get('stealth_mode', stealth_mode)
        max_retries = cfg.get('max_retries', max_retries)
        min_request_delay = cfg.get('min_request_delay', min_request_delay)
        detection_keywords = cfg.get('detection_keywords', detection_keywords)

        # apply profile-specific overrides when provided (e.g., 'slow' or 'fast')
        if profile and isinstance(cfg, dict):
            profile_cfg = cfg.get('profiles', {}).get(profile) or cfg.get(profile) or {}
            if isinstance(profile_cfg, dict):
                headless = profile_cfg.get('headless', headless)
                stealth_mode = profile_cfg.get('stealth_mode', stealth_mode)
                max_retries = profile_cfg.get('max_retries', max_retries)
                min_request_delay = profile_cfg.get('min_request_delay', min_request_delay)
                detection_keywords = profile_cfg.get('detection_keywords', detection_keywords)

        self.web_scraper = WebScraper(
            headless=headless,
            stealth_mode=stealth_mode,
            max_retries=max_retries,
            min_request_delay=min_request_delay,
            detection_keywords=detection_keywords,
            **kwargs
        )

        return self.web_scraper

    def destroy_scraper_thread(self):
        """Safely destroy the thread-local browser for this finder if present."""
        try:
            if self.web_scraper:
                self.web_scraper.destroy_current_thread()
        except Exception:
            # Best-effort cleanup; don't raise during thread cleanup
            pass

    def run_workers(self, items: Iterable, worker_fn: Callable, num_threads: int):
        """Run `worker_fn` across `items` using `num_threads` worker threads.

        `worker_fn` is called as worker_fn(items_slice, thread_id).
        This helper will start a progress logging thread that calls
        `_log_progress(items)` if the subclass implements it.
        """
        items = list(items)
        self._scanned_matches = 0
        self._stop_logging = False

        # Optionally create a shared scraper (finder may override afterwards)
        if self.web_scraper is None:
            self.get_web_scraper()

        # Start progress logging thread if subclass provides _log_progress
        info_thread = None
        if hasattr(self, '_log_progress'):
            info_thread = threading.Thread(target=self._log_progress, args=(items,))
            info_thread.start()

        # Start workers
        threads = []
        total = len(items)
        for i in range(num_threads):
            slice_start = int(i * total / num_threads)
            slice_end = int((i + 1) * total / num_threads)
            items_slice = items[slice_start:slice_end]
            thread = threading.Thread(target=worker_fn, args=(items_slice, i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Stop logging
        self._stop_logging = True
        if info_thread:
            info_thread.join()

    def skip_match_by_patterns(self, home_team_name: str, away_team_name: str, skip_patterns: Optional[List[Tuple[str, str]]] = None) -> Optional[str]:
        """Return the reason for skipping a match when any pattern matches either team.

        Returns the matched reason string, or None if no pattern matched.
        """
        patterns = skip_patterns if skip_patterns is not None else SKIP_PATTERNS
        matched = next((reason for pattern, reason in patterns
                        if re.search(pattern, home_team_name, re.I) or re.search(pattern, away_team_name, re.I)), None)
        return matched

    # keep only todays matches
    def validate_match_date(self, match_datetime):
        today_start = CURRENT_TIME.replace(hour=0, minute=0, second=0, microsecond=0)

        if match_datetime < today_start:
            return False
        return True