from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

SOCCERVISTA_URL = "https://www.soccervista.com/"
SOCCERVISTA_NAME = "soccervista"


class SoccerVistaFinder_per_match(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URL."""
        return [SOCCERVISTA_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse either discovery page or match page."""
        if url == SOCCERVISTA_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_match_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract match URLs from discovery page and scrape them."""
        try:
            links = page.select("a[href*='/prediction-']")
            urls = [
                "https://www.soccervista.com" + link.attr("href")
                for link in links
                if link.attr("href")
            ]

            if urls:
                logger.info(f"Found {len(urls)} SoccerVista match URLs")
                self.collect_urls(urls)
            else:
                logger.warning("No SoccerVista match URLs found")
        except Exception as e:
            logger.error(f"Error discovering SoccerVista matches: {e}")

    def _parse_match_page(self, url: str, page: Page) -> None:
        try:
            # Match detail page parsing
            # Home/Away teams usually in h1 or specific div
            home_team = page.find(".home-team-name").text().strip()
            away_team = page.find(".away-team-name").text().strip()
            
            if not home_team or not away_team:
                # Fallback to title parsing
                title = page.find("title").text()
                if " vs " in title:
                    parts = title.split(" vs ")
                    home_team = parts[0].split("prediction")[-1].strip()
                    away_team = parts[1].split("-")[0].strip()

            # Prediction score
            prediction_div = page.select(".score-prediction")
            if prediction_div:
                score_text = prediction_div[0].text().strip()
                if ":" in score_text:
                    home_p, away_p = score_text.split(":")
                    predictions = [Score(SOCCERVISTA_NAME, float(home_p), float(away_p))]
                else:
                    return
            else:
                return

            # Date
            date_text = page.find(".match-date").text().strip()
            try:
                match_date = datetime.strptime(date_text, "%d %b %Y")
            except ValueError:
                match_date = datetime.now().replace(hour=0, minute=0, second=0)

            self.add_match(Match(home_team, away_team, match_date, predictions))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
