"""Match finder for soccervista.com league pages."""

from bet_crawler.crawler_logging import exception_event, get_logger, log_event

logger = get_logger(__name__)
import datetime
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.leagues import *
from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

SOCCERVISTA_URL = "https://www.soccervista.com"
SOCCERVISTA_NAME = "soccervista"
MAX_CONCURRENCY = 10

TOP_LEAGUES = {
    "https://www.soccervista.com/europe/champions-league/xGrwqq16/": CHAMPIONS_LEAGUE,
    "https://www.soccervista.com/europe/europa-league/ClDjv3V5/": EUROPA_LEAGUE,
    "https://www.soccervista.com/europe/conference-league/GfRbsVWM/": CONFERENCE_LEAGUE,
    "https://www.soccervista.com/england/championship/2DSCa5fE/": CHAMPIONSHIP,
    "https://www.soccervista.com/italy/serie-b/6oug4RRc/": SERIE_B,
    "https://www.soccervista.com/spain/laliga2/vZiPmPJi/": SEGUNDA_DIVISION,
    "https://www.soccervista.com/germany/2-bundesliga/tKH71vSe/": BUNDESLIGA_2,
    "https://www.soccervista.com/france/ligue-2/Y35Jer59/": LIGUE_2,
    "https://www.soccervista.com/england/premier-league/dYlOSQOD/": PREMIER_LEAGUE,
    "https://www.soccervista.com/spain/laliga/QVmLl54o/": LA_LIGA,
    "https://www.soccervista.com/germany/bundesliga/W6BOzpK2/": BUNDESLIGA,
    "https://www.soccervista.com/italy/serie-a/COuk57Ci/": SERIE_A,
    "https://www.soccervista.com/france/ligue-1/KIShoMk3/": LIGUE_1,
    "https://www.soccervista.com/belgium/jupiler-pro-league/dG2SqPrf/": JUPILER_PRO_LEAGUE,
    "https://www.soccervista.com/portugal/liga-portugal/UmMRoGzp/": LIGA_PORTUGAL,
    "https://www.soccervista.com/brazil/serie-a-betano/Yq4hUnzQ/": SERIE_A_BRAZIL,
    "https://www.soccervista.com/usa/mls/CQv5qrFt/": MLS,
    "https://www.soccervista.com/netherlands/eredivisie/Or1bBrWD/": EREDIVISIE,
    "https://www.soccervista.com/denmark/superliga/O6W7GIaF/": SUPERLIGA_DENMARK,
    "https://www.soccervista.com/poland/ekstraklasa/lrMHUHDc/": EKSTRAKLASA,
    "https://www.soccervista.com/argentina/liga-profesional/naYhNOaA/": LIGA_PROFESIONAL,
    "https://www.soccervista.com/japan/j1-league/pAq4eRQ9/": J1_LEAGUE,
    "https://www.soccervista.com/turkey/super-lig/Opdcd08Q/": SUPER_LIG,
    "https://www.soccervista.com/sweden/allsvenskan/nXxWpLmT/": ALLSVENSKAN,
    "https://www.soccervista.com/croatia/hnl/nqMxclRN/": HNL,
    "https://www.soccervista.com/mexico/liga-mx/bm2Vlsfl/": LIGA_MX,
    "https://www.soccervista.com/norway/eliteserien/GOvB22xg/": ELITESERIEN,
    "https://www.soccervista.com/austria/bundesliga/rJg7S7Me/": BUNDESLIGA_AUSTRIA,
    "https://www.soccervista.com/switzerland/super-league/KAjTCI1l/": SUPER_LEAGUE_SWITZERLAND,
    "https://www.soccervista.com/scotland/premiership/tGwiyvJ1/": SCOTTISH_PREMIERSHIP,
}


class SoccerVistaFinder_per_league(BaseMatchFinder):
    """Scrapes soccervista league prediction listings."""

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        """Wire the finder contract (see BaseMatchFinder)."""
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        """Return soccervista league listing URLs."""
        if self.top_leagues_only:
            return list(TOP_LEAGUES.keys())
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
        """Scrape all soccervista league URLs and emit matches via callback."""
        scrape(
            urls,
            self._parse_page_with_log_context,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        """Parse one soccervista league page and emit matches via callback."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            container = soup.find("h2", string=lambda t: t and "Upcoming Predictions" in t)
            if container is None:
                log_event(
                    logger,
                    event="source.page.structure_missing",
                    outcome="warning",
                    reason_code="upcoming_predictions_container_missing",
                    level=30,
                    message=f"SoccerVista league page has no Upcoming Predictions section: {url}",
                    source_key="soccervista",
                    url=url,
                )
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
                    except ValueError as exc:
                        date_text = match_tr.find_all("td")[0].get_text(strip=True)
                        if any(token in date_text.casefold() for token in ("live", "ongoing", "in play", "'")):
                            logger.info("%s vs %s: Match ongoing", home_team, away_team)
                        else:
                            logger.warning(
                                "Skipping %s vs %s: invalid/unrecognized date %r (%s)",
                                home_team,
                                away_team,
                                date_text,
                                exc,
                                extra={
                                    "event": "match.skipped",
                                    "outcome": "warning",
                                    "reason_code": "invalid_match_date",
                                    "source_key": "soccervista",
                                    "url": url,
                                    "error_type": type(exc).__name__,
                                },
                            )
                        continue

                    score_text = match_tr.find_all("td")[-1].get_text()
                    scores = [
                        Score(
                            SOCCERVISTA_NAME,
                            int(score_text.split(":")[0]),
                            int(score_text.split(":")[1]),
                        )
                    ]

                    league = TOP_LEAGUES.get(url) if self.top_leagues_only and url in TOP_LEAGUES else None
                    self.add_match(
                        Match(
                            home_team=home_team,
                            away_team=away_team,
                            datetime=match_datetime,
                            predictions=scores,
                            odds=None,
                            league=league,
                            result_url=SOCCERVISTA_URL + match_tr.find("a").get("href").replace("/fr/", "/"),
                        )
                    )

                except Exception as e:
                    exception_event(
                        logger,
                        event="match.parse.failed",
                        reason_code="candidate_parse_failed",
                        message=f"Skipping malformed SoccerVista candidate on {url}: {e}",
                        source_key="soccervista",
                        url=url,
                    )
                    continue

        except Exception as e:
            exception_event(
                logger,
                event="source.page.failed",
                reason_code="page_parse_failed",
                message=f"Failed to parse SoccerVista league page {url}: {e}",
                source_key="soccervista",
                url=url,
            )
