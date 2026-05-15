from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

WINDRAWWIN_URL = "https://www.windrawwin.com/"
WINDRAWWIN_NAME = "windrawwin"


class WinDrawWinFinder_per_match(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URL."""
        return [WINDRAWWIN_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse either discovery page or match page."""
        if url == WINDRAWWIN_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_match_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract match URLs from discovery page and scrape them."""
        try:
            links = page.select("a[href*='/predictions/match/']")
            urls = [
                "https://www.windrawwin.com" + link.attr("href")
                for link in links
                if link.attr("href")
            ]

            if urls:
                logger.info(f"Found {len(urls)} WinDrawWin match URLs")
                self.collect_urls(urls)
            else:
                logger.warning("No WinDrawWin match URLs found")
        except Exception as e:
            logger.error(f"Error discovering WinDrawWin matches: {e}")

    def _parse_match_page(self, url: str, page: Page) -> None:
        try:
            # Match detail page parsing
            home_team = page.find(".wt-match-home").text().strip()
            away_team = page.find(".wt-match-away").text().strip()
            
            if not home_team:
                # Fallback
                title = page.find("title").text()
                if " vs " in title:
                    home_team = title.split(" vs ")[0].strip()
                    away_team = title.split(" vs ")[1].split("Prediction")[0].strip()

            # Prediction score
            score_element = page.select(".wt-predicted-score")
            if score_element:
                score_text = score_element[0].text().strip()
                if "-" in score_text:
                    home_p, away_p = score_text.split("-")
                    predictions = [Score(WINDRAWWIN_NAME, float(home_p), float(away_p))]
                else:
                    return
            else:
                return

            # Date
            date_element = page.select(".wt-match-date-time")
            if date_element:
                date_text = date_element[0].text().strip()
                try:
                    match_date = datetime.strptime(date_text, "%d %b %Y %H:%M")
                except ValueError:
                    match_date = datetime.now()
            else:
                match_date = datetime.now()

            self.add_match(Match(home_team, away_team, match_date, predictions, None))

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
