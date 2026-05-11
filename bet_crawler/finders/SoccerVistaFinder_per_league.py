from scrape_kit import get_logger

logger = get_logger(__name__)
import datetime
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

SOCCERVISTA_URL = "https://www.soccervista.com"
SOCCERVISTA_NAME = "soccervista"
MAX_CONCURRENCY = 10


class SoccerVistaFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        html = fetch(SOCCERVISTA_URL, stealthy_headers=True)
        soup = BeautifulSoup(html, "html.parser")

        links = [
            link["href"] for link in soup.find("h3", string=lambda t: t and "Top Leagues" in t).parent.find_all("a", href=True)
        ][:-2]

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as ex:
            results = list(
                ex.map(
                    lambda l: (
                        [
                            opt["value"]
                            for opt in BeautifulSoup(fetch(SOCCERVISTA_URL + l) or "", "html.parser")
                            .find("select", id="tournamentPage")
                            .find_all("option")
                        ]
                        if fetch(SOCCERVISTA_URL + l)
                        else []
                    ),
                    links,
                )
            )

        league_urls = [SOCCERVISTA_URL + url for urls in results for url in urls]
        logger.info(f"{len(league_urls)} leagues to scrape")
        return league_urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            container = soup.find("h2", string=lambda t: t and "Upcoming Predictions" in t)
            matches = container.parent.find("tbody").find_all("tr") if container else []

            for match_tr in matches:
                try:
                    home_team = match_tr.find_all("td")[1].find_all("span")[-1].get_text()
                    away_team = match_tr.find_all("td")[3].find_all("span")[0].get_text()
                    try:
                        date_str = match_tr.find_all("td")[0].get_text()
                        match_datetime = min(
                            (
                                datetime.strptime(f"{date_str} {y}", "%d %b %Y")
                                for y in [
                                    datetime.now().year - 1,
                                    datetime.now().year,
                                    datetime.now().year + 1,
                                ]
                            ),
                            key=lambda d: abs(d - datetime.now()),
                        ).replace(hour=0, minute=0, second=0, microsecond=0)
                    except Exception:
                        logger.info(f"{home_team} vs {away_team}: Match ongoing")
                        continue

                    score_text = match_tr.find_all("td")[-1].get_text()
                    scores = [
                        Score(
                            SOCCERVISTA_NAME,
                            int(score_text.split(":")[0]),
                            int(score_text.split(":")[1]),
                        )
                    ]

                    self.add_match(
                        Match(
                            home_team=home_team,
                            away_team=away_team,
                            datetime=match_datetime,
                            predictions=scores,
                            odds=None,
                            result_url=SOCCERVISTA_URL + match_tr.find("a").get("href").replace("/fr/", "/"),
                        )
                    )

                except Exception as e:
                    logger.error(f"SKIPPED [{url}]: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
