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

TOP_LEAGUES = [
    "https://www.soccervista.com/europe/champions-league/xGrwqq16/",
    "https://www.soccervista.com/europe/europa-league/ClDjv3V5/",
    "https://www.soccervista.com/europe/conference-league/GfRbsVWM/",
    "https://www.soccervista.com/england/championship/2DSCa5fE/",
    "https://www.soccervista.com/italy/serie-b/6oug4RRc/",
    "https://www.soccervista.com/spain/laliga2/vZiPmPJi/",
    "https://www.soccervista.com/germany/2-bundesliga/tKH71vSe/",
    "https://www.soccervista.com/france/ligue-2/Y35Jer59/",
    "https://www.soccervista.com/england/premier-league/dYlOSQOD/",
    "https://www.soccervista.com/spain/laliga/QVmLl54o/",
    "https://www.soccervista.com/germany/bundesliga/W6BOzpK2/",
    "https://www.soccervista.com/italy/serie-a/COuk57Ci/",
    "https://www.soccervista.com/france/ligue-1/KIShoMk3/",
    "https://www.soccervista.com/belgium/jupiler-pro-league/dG2SqPrf/",
    "https://www.soccervista.com/portugal/liga-portugal/UmMRoGzp/",
    "https://www.soccervista.com/brazil/serie-a-betano/Yq4hUnzQ/",
    "https://www.soccervista.com/usa/mls/CQv5qrFt/",
    "https://www.soccervista.com/netherlands/eredivisie/Or1bBrWD/",
    "https://www.soccervista.com/denmark/superliga/O6W7GIaF/",
    "https://www.soccervista.com/poland/ekstraklasa/lrMHUHDc/",
    "https://www.soccervista.com/argentina/liga-profesional/naYhNOaA/",
    "https://www.soccervista.com/japan/j1-league/pAq4eRQ9/",
    "https://www.soccervista.com/turkey/super-lig/Opdcd08Q/",
    "https://www.soccervista.com/sweden/allsvenskan/nXxWpLmT/",
    "https://www.soccervista.com/croatia/hnl/nqMxclRN/",
    "https://www.soccervista.com/mexico/liga-mx/bm2Vlsfl/",
    "https://www.soccervista.com/norway/eliteserien/GOvB22xg/",
    "https://www.soccervista.com/austria/bundesliga/rJg7S7Me/",
    "https://www.soccervista.com/switzerland/super-league/KAjTCI1l/",
    "https://www.soccervista.com/scotland/premiership/tGwiyvJ1/",
]


class SoccerVistaFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        if self.top_leagues_only:
            return TOP_LEAGUES
        else:
            html = fetch(SOCCERVISTA_URL, stealthy_headers=True)
            soup = BeautifulSoup(html, "html.parser")

            links = [
                link["href"]
                for link in soup.find("h3", string=lambda t: t and "Top Leagues" in t).parent.find_all("a", href=True)
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

            matches = []
            if container and container.parent:
                tbody = container.parent.find("tbody")
                if tbody:
                    matches = tbody.find_all("tr")

            for idx, match_tr in enumerate(matches, start=1):
                try:
                    tds = match_tr.find_all("td")
                    if len(tds) < 5:
                        logger.debug(f"Match #{idx}: Skipping - insufficient table cells")
                        continue

                    home_spans = tds[1].find_all("span")
                    away_spans = tds[3].find_all("span")
                    if not home_spans or not away_spans:
                        logger.debug(f"Match #{idx}: Skipping - missing team names")
                        continue

                    home_team = home_spans[-1].get_text(strip=True)
                    away_team = away_spans[0].get_text(strip=True)

                    date_str = tds[0].get_text(strip=True)
                    try:
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
                        logger.info(f"{home_team} vs {away_team}: Match date format invalid, marking as ongoing/skipped")
                        continue

                    score_text = tds[-1].get_text(strip=True)
                    if ":" not in score_text:
                        logger.debug(f"SKIPPED [{home_team} vs {away_team}]: Invalid score prediction format '{score_text}'")
                        continue

                    try:
                        home_pred, away_pred = score_text.split(":")
                        scores = [Score(SOCCERVISTA_NAME, int(home_pred.strip()), int(away_pred.strip()))]
                    except ValueError:
                        logger.error(f"SKIPPED [{home_team} vs {away_team}]: Score parse error on '{score_text}'")
                        continue

                    result_url = None
                    link_elem = match_tr.find("a")
                    if link_elem and link_elem.get("href"):
                        result_url = SOCCERVISTA_URL + link_elem.get("href").replace("/fr/", "/")

                    self.add_match(
                        Match(
                            home_team=home_team,
                            away_team=away_team,
                            datetime=match_datetime,
                            predictions=scores,
                            odds=None,
                            result_url=result_url,
                        )
                    )

                except Exception as e:
                    logger.error(f"SKIPPED [{url}] Match #{idx}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
