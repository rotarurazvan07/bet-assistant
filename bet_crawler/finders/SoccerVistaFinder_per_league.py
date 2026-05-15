from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

SOCCERVISTA_URL = "https://www.soccervista.com/"
SOCCERVISTA_NAME = "soccervista"


class SoccerVistaFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URL."""
        return [SOCCERVISTA_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse either discovery page or league page."""
        if url == SOCCERVISTA_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_league_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract league URLs from discovery page and scrape them."""
        try:
            links = page.select(".leaguelist a")
            if not links:
                links = page.select("a[href*='/betting-tips/']")

            urls = [
                "https://www.soccervista.com" + link.attr("href")
                for link in links
                if link.attr("href")
            ]

            if self.top_leagues_only:
                urls = urls[:20]

            if urls:
                logger.info(f"Found {len(urls)} SoccerVista league URLs")
                self.collect_urls(urls)
            else:
                logger.warning("No SoccerVista league URLs found")
        except Exception as e:
            logger.error(f"Error discovering SoccerVista leagues: {e}")

    def _parse_league_page(self, url: str, page: Page) -> None:
        try:
            # SoccerVista league page has matches in a table
            rows = page.find("table.main tr")
            if not rows:
                rows = page.find(".match-row")

            for row in rows:
                try:
                    # SoccerVista layout parsing
                    cols = row.find("td")
                    if len(cols) < 6:
                        continue

                    home_team = cols[2].text().strip()
                    away_team = cols[3].text().strip()
                    
                    score_text = cols[5].text().strip() # Prediction column
                    if ":" in score_text:
                        home_p, away_p = score_text.split(":")
                        predictions = [Score(SOCCERVISTA_NAME, float(home_p), float(away_p))]
                    elif "-" in score_text:
                        home_p, away_p = score_text.split("-")
                        predictions = [Score(SOCCERVISTA_NAME, float(home_p), float(away_p))]
                    else:
                        continue

                    match_date = datetime.now().replace(hour=0, minute=0, second=0)

                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
