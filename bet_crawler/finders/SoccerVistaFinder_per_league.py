from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

SOCCERVISTA_URL = "https://www.soccervista.com"
SOCCERVISTA_NAME = "soccervista"

TOP_LEAGUES = [
    "https://www.soccervista.com/soccer-predictions-champions-league-702.html",
    "https://www.soccervista.com/soccer-predictions-europa-league-703.html",
    "https://www.soccervista.com/soccer-predictions-conference-league-883.html",
    "https://www.soccervista.com/soccer-predictions-championship-706.html",
    "https://www.soccervista.com/soccer-predictions-serie-b-734.html",
    "https://www.soccervista.com/soccer-predictions-laliga2-753.html",
    "https://www.soccervista.com/soccer-predictions-2-bundesliga-724.html",
    "https://www.soccervista.com/soccer-predictions-ligue-2-716.html",
    "https://www.soccervista.com/soccer-predictions-premier-league-704.html",
    "https://www.soccervista.com/soccer-predictions-laliga-705.html",
    "https://www.soccervista.com/soccer-predictions-bundesliga-707.html",
    "https://www.soccervista.com/soccer-predictions-serie-a-708.html",
    "https://www.soccervista.com/soccer-predictions-ligue-1-709.html",
    "https://www.soccervista.com/soccer-predictions-jupiler-pro-league-710.html",
    "https://www.soccervista.com/soccer-predictions-liga-portugal-711.html",
    "https://www.soccervista.com/soccer-predictions-serie-a-betano-798.html",
    "https://www.soccervista.com/soccer-predictions-mls-712.html",
    "https://www.soccervista.com/soccer-predictions-eredivisie-713.html",
    "https://www.soccervista.com/soccer-predictions-superliga-714.html",
    "https://www.soccervista.com/soccer-predictions-ekstraklasa-715.html",
    "https://www.soccervista.com/soccer-predictions-liga-profesional-795.html",
    "https://www.soccervista.com/soccer-predictions-j1-league-717.html",
    "https://www.soccervista.com/soccer-predictions-super-lig-718.html",
    "https://www.soccervista.com/soccer-predictions-allsvenskan-719.html",
    "https://www.soccervista.com/soccer-predictions-hnl-720.html",
    "https://www.soccervista.com/soccer-predictions-liga-mx-721.html",
    "https://www.soccervista.com/soccer-predictions-eliteserien-722.html",
    "https://www.soccervista.com/soccer-predictions-bundesliga-723.html",
    "https://www.soccervista.com/soccer-predictions-super-league-725.html",
    "https://www.soccervista.com/soccer-predictions-premiership-726.html",
]


class SoccerVistaFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return main page for league discovery."""
        return [SOCCERVISTA_URL]

    def get_match_urls(self) -> list[str]:
        """Return league URLs directly or discover them."""
        if self.top_leagues_only:
            return TOP_LEAGUES
        self.scrape()
        return self.collected_urls if self.collected_urls else TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse discovery or league page."""
        if url == SOCCERVISTA_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_league_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract league URLs from main page."""
        try:
            links = page.select("a[href*='soccer-predictions']")
            league_urls = []
            for link in links:
                href = link.attr("href")
                if href:
                    full = href if href.startswith("http") else SOCCERVISTA_URL + "/" + href.lstrip("/")
                    if full not in league_urls:
                        league_urls.append(full)
            if league_urls:
                logger.info(f"Found {len(league_urls)} SoccerVista leagues")
                self.collect_urls(league_urls)
            else:
                logger.warning("No SoccerVista league URLs found")
        except Exception as e:
            logger.error(f"Error discovering leagues: {e}")

    def _parse_league_page(self, url: str, page: Page) -> None:
        """Parse match predictions from a league page."""
        try:
            # Find "Upcoming Predictions" section
            heading = page.find_by_text("h2", "Upcoming Predictions")
            if not heading:
                logger.debug(f"No upcoming predictions on {url}")
                return
            # Find the table after the heading
            rows = page.select("table tr")
            if not rows:
                return
            for row in rows:
                try:
                    cols = row.select("td")
                    if len(cols) < 5:
                        continue
                    # Home team: last span in td[1]
                    home_spans = cols[1].select("span")
                    home_team = home_spans[-1].text().strip() if home_spans else cols[1].text().strip()
                    # Away team: last span in td[2]
                    away_spans = cols[2].select("span")
                    away_team = away_spans[-1].text().strip() if away_spans else cols[2].text().strip()
                    if not home_team or not away_team:
                        continue
                    # Date from td[0]
                    date_str = cols[0].text().strip()
                    match_date = self.parse_date_robust(date_str)
                    if not match_date:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    # Score from last column
                    score_text = cols[-1].text().strip()
                    if ":" not in score_text:
                        continue
                    parts = score_text.split(":")
                    home_score = float(parts[0].strip())
                    away_score = float(parts[1].strip())
                    predictions = [Score(SOCCERVISTA_NAME, home_score, away_score)]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping row: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")