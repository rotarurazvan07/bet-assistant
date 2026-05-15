from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/today/"
WINDRAWWIN_NAME = "windrawwin"


class WinDrawWinFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URL."""
        return [WINDRAWWIN_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse either discovery page or league page."""
        if url == WINDRAWWIN_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_league_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract league URLs from discovery page and scrape them."""
        try:
            links = page.select(".wt-league-link a")
            if not links:
                links = page.select("a[href*='/predictions/league/']")

            urls = [
                "https://www.windrawwin.com" + link.attr("href")
                for link in links
                if link.attr("href")
            ]

            if urls:
                logger.info(f"Found {len(urls)} WinDrawWin league URLs")
                self.collect_urls(urls)
            else:
                logger.warning("No WinDrawWin league URLs found, parsing current page")
                if not self._discovery_mode:
                    self._parse_league_page(WINDRAWWIN_URL, page)
        except Exception as e:
            logger.error(f"Error discovering WinDrawWin leagues: {e}")

    def _parse_league_page(self, url: str, page: Page) -> None:
        try:
            # WinDrawWin league page rows
            rows = page.find(".wt-match-row")
            if not rows:
                rows = page.find("table tr")

            for row in rows:
                try:
                    home_team = row.find(".wt-home-team").text().strip()
                    away_team = row.find(".wt-away-team").text().strip()
                    
                    score_text = row.find(".wt-score-prediction").text().strip()
                    if "-" in score_text:
                        home_p, away_p = score_text.split("-")
                        predictions = [Score(WINDRAWWIN_NAME, float(home_p), float(away_p))]
                    else:
                        continue

                    # Date
                    date_text = row.find(".wt-match-date").text().strip()
                    try:
                        match_date = datetime.strptime(date_text, "%d %b %Y")
                    except ValueError:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0)

                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
