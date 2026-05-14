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
        try:
            page = Page.from_url(SOCCERVISTA_URL)
            # Find league links
            links = page.find(".leaguelist a")
            if not links:
                links = page.find("a[href*='/betting-tips/']")
                
            urls = ["https://www.soccervista.com" + link.attr("href") for link in links if link.attr("href")]
            
            if self.top_leagues_only:
                # Filter or keep top ones
                urls = urls[:20]
                
            logger.info(f"Found {len(urls)} SoccerVista league URLs")
            return urls
        except Exception as e:
            logger.error(f"Error discovering SoccerVista leagues: {e}")
            return []

    def _parse_page(self, url: str, page: Page) -> None:
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
