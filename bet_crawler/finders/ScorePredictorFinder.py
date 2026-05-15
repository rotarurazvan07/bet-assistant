from datetime import datetime, timedelta

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

SCOREPREDICTOR_URL = "https://scorepredictor.net/"
SCOREPREDICTOR_NAME = "scorepredictor"

TOP_LEAGUES = [
    "https://scorepredictor.net/index.php?section=football&season=ChampionsLeague",
    "https://scorepredictor.net/index.php?section=football&season=EuropaLeague",
    "https://scorepredictor.net/index.php?section=football&season=England",
    "https://scorepredictor.net/index.php?section=football&season=Italy",
    "https://scorepredictor.net/index.php?section=football&season=Spain",
    "https://scorepredictor.net/index.php?section=football&season=Germany",
    "https://scorepredictor.net/index.php?section=football&season=France",
    "https://scorepredictor.net/index.php?section=football&season=Belgium",
    "https://scorepredictor.net/index.php?section=football&season=England2",
    "https://scorepredictor.net/index.php?section=football&season=Portugal",
    "https://scorepredictor.net/index.php?section=football&season=Netherlands",
    "https://scorepredictor.net/index.php?section=football&season=Denmark",
    "https://scorepredictor.net/index.php?section=football&season=Poland",
    "https://scorepredictor.net/index.php?section=football&season=Turkey",
    "https://scorepredictor.net/index.php?section=football&season=Sweden",
    "https://scorepredictor.net/index.php?section=football&season=Croatia",
    "https://scorepredictor.net/index.php?section=football&season=Spain2",
    "https://scorepredictor.net/index.php?section=football&season=Norway",
    "https://scorepredictor.net/index.php?section=football&season=Austria",
    "https://scorepredictor.net/index.php?section=football&season=Switzerland",
    "https://scorepredictor.net/index.php?section=football&season=Italy2",
    "https://scorepredictor.net/index.php?section=football&season=Germany2",
    "https://scorepredictor.net/index.php?section=football&season=France2",
    "https://scorepredictor.net/index.php?section=football&season=Scotland",
    "https://scorepredictor.net/index.php?section=football&season=ConferenceLeague",
]


class ScorePredictorFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URL."""
        return [SCOREPREDICTOR_URL + "index.php?section=football"]

    def get_match_urls(self) -> list[str]:
        """Return league URLs directly or discover them."""
        if self.top_leagues_only:
            return TOP_LEAGUES
        self.scrape()
        return self.collected_urls if self.collected_urls else TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse discovery or league page."""
        if "section=football" in url and "season=" not in url:
            self._parse_discovery_page(page)
        else:
            self._parse_league_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract league URLs from category page."""
        try:
            cat_div = page.find(".block_categories")
            if not cat_div:
                return
            links = cat_div.select("a")
            league_urls = []
            for link in links:
                href = link.attr("href")
                if href:
                    league_urls.append(SCOREPREDICTOR_URL + href if not href.startswith("http") else href)
            if league_urls:
                logger.info(f"Found {len(league_urls)} ScorePredictor leagues")
                self.collect_urls(league_urls)
        except Exception as e:
            logger.error(f"Error discovering leagues: {e}")

    def _parse_league_page(self, url: str, page: Page) -> None:
        """Parse match predictions from league table."""
        try:
            if page.contains("No matches within next 5 days"):
                return
            table = page.find(".table_dark")
            if not table:
                logger.warning(f"No prediction table found on {url}")
                return
            rows = table.select("tr")
            if len(rows) < 2:
                return
            for row in rows[1:]:
                try:
                    cols = row.select("td")
                    if len(cols) < 5:
                        continue
                    date_str = cols[0].text().strip()
                    home_team = cols[1].text().strip()
                    home_score_str = cols[2].text().strip()
                    away_score_str = cols[3].text().strip()
                    away_team = cols[4].text().strip()
                    if not home_score_str.isdigit() or not away_score_str.isdigit():
                        continue
                    # Parse date (DD.MM format, infer year)
                    try:
                        parts = date_str.split(".")
                        day, month = int(parts[0]), int(parts[1])
                        year = self.infer_year(month, day)
                        match_date = datetime(year, month, day)
                    except (ValueError, IndexError):
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    predictions = [Score(SCOREPREDICTOR_NAME, float(home_score_str), float(away_score_str))]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping row: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")