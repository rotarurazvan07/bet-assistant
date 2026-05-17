from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import get_logger

logger = get_logger(__name__)
from itertools import takewhile

from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.leagues import *
from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

ONE_MILLION_PREDICTIONS_NAME = "onemillionpredictions"
ONE_MILLION_PREDICTIONS_URL = "https://onemillionpredictions.com"
MAX_CONCURRENCY = 1

TOP_LEAGUES = {
    "https://onemillionpredictions.com/england-premier-league/predictions/": PREMIER_LEAGUE,
    "https://onemillionpredictions.com/italy-serie-a/predictions/": SERIE_A,
    "https://onemillionpredictions.com/spain-la-liga/predictions/": LA_LIGA,
    "https://onemillionpredictions.com/germany-bundesliga/predictions/": BUNDESLIGA,
    "https://onemillionpredictions.com/france-ligue-1/predictions/": LIGUE_1,
    "https://onemillionpredictions.com/netherland-eredivisie/predictions/": EREDIVISIE,
    "https://onemillionpredictions.com/portugal-primeira-liga/predictions/": LIGA_PORTUGAL,
    "https://onemillionpredictions.com/argentina-liga-profesional/predictions/": LIGA_PROFESIONAL,
    "https://onemillionpredictions.com/brazil-serie-a/predictions/": SERIE_A_BRAZIL,
    "https://onemillionpredictions.com/mexico-liga-mx/predictions/": LIGA_MX,
    "https://onemillionpredictions.com/usa-mls/predictions/": MLS,
    "https://onemillionpredictions.com/uefa-champions-league/predictions/": CHAMPIONS_LEAGUE,
    "https://onemillionpredictions.com/uefa-europa-league/predictions/": EUROPA_LEAGUE,
    "https://onemillionpredictions.com/uefa-europa-conference-league/predictions/": CONFERENCE_LEAGUE,
}


class OneMillionPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        if self.top_leagues_only:
            return list(TOP_LEAGUES.keys())
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
            if self.top_leagues_only:
                matches_container = list(
                    takewhile(lambda tr: "Matchday" not in tr.text, soup.find_all("tbody")[1].find_all("tr"))
                )
            else:
                matches_container = soup.find_all("tbody")[2].find_all("tr")

            for match_tr in matches_container:
                try:
                    cells = match_tr.find_all("td")
                    dt_tag = cells[0].find(class_="fulldatetime")
                    if dt_tag:
                        dt_str = dt_tag.get_text(strip=True)
                        dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(hour=0, minute=0, second=0, microsecond=0)

                        teams = list(cells[1].stripped_strings)
                        home_team = teams[0]
                        away_team = teams[1]

                        score_text = cells[2].get_text(strip=True)

                        predictions = [
                            Score(
                                ONE_MILLION_PREDICTIONS_NAME,
                                int(score_text.split(":")[0]),
                                int(score_text.split(":")[1]),
                            )
                        ]
                        odds = None

                        league = TOP_LEAGUES.get(url) if self.top_leagues_only and url in TOP_LEAGUES else None
                        self.add_match(Match(home_team, away_team, dt_obj, predictions, odds, league=league))

                except Exception as e:
                    logger.error(f"SKIPPED [{url}]: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
