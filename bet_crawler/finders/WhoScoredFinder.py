import json
import re
from datetime import datetime, timezone

from scrape_kit import browser, get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

WHOSCORED_URL = "https://www.whoscored.com/"
WHOSCORED_NAME = "whoscored"


class WhoScoredFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Get match URLs via browser (needs JS rendering for Cloudflare)."""
        try:
            with browser(solve_cloudflare=True, headless=True) as session:
                page = session.fetch(WHOSCORED_URL + "previews")
                # Find all links containing 'matches'
                links = page.find("a[href*='/matches/']")
                urls = [WHOSCORED_URL.rstrip("/") + link.attr("href") for link in links if link.attr("href")]
                
                logger.info(f"Found {len(urls)} WhoScored matches to scrape")
                return list(set(urls))
        except Exception as e:
            logger.error(f"Failed to discover WhoScored matches: {e}")
            return []

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            html = page.raw_html
            
            # 1. Look for the embedded JSON config
            match_json = re.search(r"matchHeaderJson: JSON\.parse\(\'(.*?)\'\),", html)
            if not match_json:
                logger.debug(f"Could not find matchHeaderJson on {url}")
                return

            data = json.loads(match_json.group(1))
            home_team = data.get("HomeTeamName")
            away_team = data.get("AwayTeamName")

            # StartTimeUtc format: /Date(1772290800000)/
            ts_str = data.get("StartTimeUtc", "").strip("/Date()")
            if ts_str:
                ts = int(ts_str) / 1000
                match_datetime = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
                match_datetime = match_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                match_datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # 2. Extract score predictions from DOM
            scores_tags = page.find("#preview-prediction .predicted-score")
            if len(scores_tags) >= 2:
                try:
                    home_p = scores_tags[0].text().strip()
                    away_p = scores_tags[1].text().strip()
                    predictions = [Score(WHOSCORED_NAME, float(home_p), float(away_p))]
                    
                    self.add_match(Match(home_team, away_team, match_datetime, predictions))
                except (ValueError, TypeError):
                    logger.debug(f"Invalid scores on {url}")
            
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
