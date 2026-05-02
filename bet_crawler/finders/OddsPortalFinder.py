from scrape_kit import get_logger

logger = get_logger(__name__)

from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

ODDSPORTAL_URL = ""
ODDSPORTAL_NAME = "oddsportal"
MAX_CONCURRENCY = 1


class OddsPortalFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        urls = []
        logger.info(f"{len(urls)} urls to scrape")
        return urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            pass

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
