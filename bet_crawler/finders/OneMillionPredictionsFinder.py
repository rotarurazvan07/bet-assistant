from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import get_logger

logger = get_logger(__name__)
from itertools import takewhile

from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

ONE_MILLION_PREDICTIONS_NAME = "onemillionpredictions"
ONE_MILLION_PREDICTIONS_URL = "https://onemillionpredictions.com"
MAX_CONCURRENCY = 1

TOP_LEAGUES = [
    "https://onemillionpredictions.com/england-premier-league/predictions/",
    "https://onemillionpredictions.com/italy-serie-a/predictions/",
    "https://onemillionpredictions.com/spain-la-liga/predictions/",
    "https://onemillionpredictions.com/germany-bundesliga/predictions/",
    "https://onemillionpredictions.com/france-ligue-1/predictions/",
    "https://onemillionpredictions.com/netherland-eredivisie/predictions/",
    "https://onemillionpredictions.com/portugal-primeira-liga/predictions/",
    "https://onemillionpredictions.com/argentina-liga-profesional/predictions/",
    "https://onemillionpredictions.com/brazil-serie-a/predictions/",
    "https://onemillionpredictions.com/mexico-liga-mx/predictions/",
    "https://onemillionpredictions.com/usa-mls/predictions/",
    "https://onemillionpredictions.com/uefa-champions-league/predictions/",
    "https://onemillionpredictions.com/uefa-europa-league/predictions/",
    "https://onemillionpredictions.com/uefa-europa-conference-league/predictions/",
]


class OneMillionPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        if self.top_leagues_only:
            return TOP_LEAGUES
        else:
            page = fetch(ONE_MILLION_PREDICTIONS_URL, stealthy_headers=True)
            soup = BeautifulSoup(page, "html.parser")
            table = soup.find("table", attrs={"aria-label": "Predictions by Days"})
            links = [a["href"] + "correct-score/" for a in table.find_all("a")][1:]
            logger.info(f"Found {len(links)} leagues to scrape")
            return links

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
            tbodys = soup.find_all("tbody")
            matches_container = []

            if self.top_leagues_only:
                if len(tbodys) > 1:
                    matches_container = list(
                        takewhile(lambda tr: "Matchday" not in tr.text, tbodys[1].find_all("tr"))
                    )
            else:
                if len(tbodys) > 2:
                    matches_container = tbodys[2].find_all("tr")

            if not matches_container:
                logger.warning(f"No match container found in {url}. Table structure may have changed.")
                return

            for idx, match_tr in enumerate(matches_container, start=1):
                try:
                    cells = match_tr.find_all("td")
                    if len(cells) < 3:
                        continue

                    dt_tag = cells[0].find(class_="fulldatetime")
                    if not dt_tag:
                        continue

                    dt_str = dt_tag.get_text(strip=True)
                    try:
                        dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(hour=0, minute=0, second=0, microsecond=0)
                    except ValueError:
                        logger.error(f"Match #{idx}: Date parse error '{dt_str}'")
                        continue

                    teams = list(cells[1].stripped_strings)
                    if len(teams) < 2:
                        continue

                    home_team = teams[0]
                    away_team = teams[1]

                    score_text = cells[2].get_text(strip=True)
                    if ":" not in score_text:
                        logger.debug(f"SKIPPED [{home_team} vs {away_team}]: Invalid score prediction format '{score_text}'")
                        continue

                    try:
                        home_pred, away_pred = score_text.split(":", 1)
                        predictions = [Score(ONE_MILLION_PREDICTIONS_NAME, int(home_pred.strip()), int(away_pred.strip()))]
                    except ValueError:
                        logger.error(f"SKIPPED [{home_team} vs {away_team}]: Score parse error on '{score_text}'")
                        continue

                    self.add_match(Match(home_team, away_team, dt_obj, predictions, None))

                except Exception as e:
                    logger.error(f"SKIPPED [{url}] Match #{idx}: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
