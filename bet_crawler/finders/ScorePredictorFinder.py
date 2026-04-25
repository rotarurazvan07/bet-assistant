from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from scrape_kit import get_logger

logger = get_logger(__name__)

from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

SCOREPREDICTOR_URL = "https://scorepredictor.net/"
SCOREPREDICTOR_NAME = "scorepredictor"
MAX_CONCURRENCY = 3

EXCLUDED = [
    "index.php?section=football&season=ChampionsLeague",
    "index.php?section=football&season=EuropaLeague",
    "index.php?section=football&season=ConferenceLeague",
    "#",
]


class ScorePredictorFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        html = fetch(SCOREPREDICTOR_URL + "index.php?section=football")
        soup = BeautifulSoup(html, "html.parser")

        league_urls = [
            SCOREPREDICTOR_URL + a.get("href")
            for a in soup.find(class_="block_categories").find_all("a")[3:]
            if a.get("href") != "#"
        ]

        logger.info(f"{len(league_urls)} leagues to scrape")
        return league_urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.FAST,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            soup = BeautifulSoup(html, "html.parser")

            if "No matches within next 5 days" in html:
                logger.info(f"No matches in {url}")
                return

            for entry in soup.find(class_="table_dark").find_all("tr")[1:]:
                try:
                    # Parse date
                    date_str = entry.find_all("td")[0].get_text().strip()
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    day, month = map(int, date_str.split("."))
                    candidate = datetime(today.year, month, day).replace(hour=0, minute=0, second=0, microsecond=0)
                    if candidate - today > timedelta(days=300):
                        candidate = candidate.replace(year=today.year - 1)
                    elif today - candidate > timedelta(days=300):
                        candidate = candidate.replace(year=today.year + 1)

                    # Parse team names
                    home_team = entry.find_all("td")[1].get_text().strip()
                    away_team = entry.find_all("td")[4].get_text().strip()

                    # Parse scores with error handling
                    home_score_text = entry.find_all("td")[2].get_text().strip()
                    away_score_text = entry.find_all("td")[3].get_text().strip()

                    # Check if scores are valid integers
                    if not home_score_text.isdigit() or not away_score_text.isdigit():
                        logger.warning(
                            f"Skipping match {home_team} vs {away_team} on {url} due to invalid score data: '{home_score_text}' - '{away_score_text}'"
                        )
                        continue

                    scores = [
                        Score(
                            SCOREPREDICTOR_NAME,
                            int(home_score_text),
                            int(away_score_text),
                        )
                    ]

                    self.add_match(
                        Match(home_team, away_team, candidate.replace(hour=0, minute=0, second=0, microsecond=0), scores, None)
                    )

                except ValueError as e:
                    # Handle individual match parsing errors
                    logger.error(f"Skipping match on {url} due to parsing error: {e}")
                    continue
                except Exception as e:
                    # Handle any other unexpected errors for individual matches
                    logger.error(f"Skipping match on {url} due to unexpected error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
