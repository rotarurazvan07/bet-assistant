from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *
from bet_framework.core.leagues import *

from .BaseMatchFinder import BaseMatchFinder

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"
MAX_CONCURRENCY = 1

TOP_LEAGUES = {
    "https://www.windrawwin.com/tips/champions-league/": CHAMPIONS_LEAGUE,
    "https://www.windrawwin.com/tips/europa-league/": EUROPA_LEAGUE,
    "https://www.windrawwin.com/tips/europa-conference-league/": CONFERENCE_LEAGUE,
    "https://www.windrawwin.com/tips/england-premier-league/": PREMIER_LEAGUE,
    "https://www.windrawwin.com/tips/italy-serie-a/": SERIE_A,
    "https://www.windrawwin.com/tips/spain-la-liga/": LA_LIGA,
    "https://www.windrawwin.com/tips/germany-bundesliga/": BUNDESLIGA,
    "https://www.windrawwin.com/tips/france-ligue-1/": LIGUE_1,
    "https://www.windrawwin.com/tips/belgium-first-division-a/": JUPILER_PRO_LEAGUE,  # Jupiler Pro League
    "https://www.windrawwin.com/tips/england-championship/": CHAMPIONSHIP,
    "https://www.windrawwin.com/tips/portugal-primeira-liga/": LIGA_PORTUGAL,
    "https://www.windrawwin.com/tips/brazil-serie-a/": SERIE_A_BRAZIL,
    "https://www.windrawwin.com/tips/usa-major-league-soccer/": MLS,  # MLS
    "https://www.windrawwin.com/tips/netherlands-eredivisie/": EREDIVISIE,
    "https://www.windrawwin.com/tips/denmark-superliga/": SUPERLIGA_DENMARK,
    "https://www.windrawwin.com/tips/poland-ekstraklasa/": EKSTRAKLASA,
    "https://www.windrawwin.com/tips/argentina-liga-profesional/": LIGA_PROFESIONAL,
    "https://www.windrawwin.com/tips/japan-j-league/": J1_LEAGUE,  # J1 League
    "https://www.windrawwin.com/tips/turkey-super-lig/": SUPER_LIG,
    "https://www.windrawwin.com/tips/sweden-allsvenskan/": ALLSVENSKAN,
    "https://www.windrawwin.com/tips/croatia-1-hnl/": HNL,  # HNL
    "https://www.windrawwin.com/tips/mexico-liga-mx/": LIGA_MX,
    "https://www.windrawwin.com/tips/spain-segunda-division/": SEGUNDA_DIVISION,
    "https://www.windrawwin.com/tips/norway-eliteserien/": ELITESERIEN,
    "https://www.windrawwin.com/tips/austria-bundesliga/": BUNDESLIGA_AUSTRIA,
    "https://www.windrawwin.com/tips/switzerland-super-league/": SUPER_LEAGUE_SWITZERLAND,
    "https://www.windrawwin.com/tips/italy-serie-b/": SERIE_B,
    "https://www.windrawwin.com/tips/germany-2-bundesliga/": BUNDESLIGA_2,
    "https://www.windrawwin.com/tips/france-ligue-2/": LIGUE_2,
    "https://www.windrawwin.com/tips/scotland-premiership/": SCOTTISH_PREMIERSHIP,
}


class WinDrawWinFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        if self.top_leagues_only:
            return list(TOP_LEAGUES.keys())
        else:
            page = fetch(WINDRAWWIN_URL, stealthy_headers=True)
            soup = BeautifulSoup(page, "html.parser")

            all_trs = soup.find("div", class_="widetable").find_all("tr")
            start = next(i for i, r in enumerate(all_trs) if "Cup and International Leagues" in r.text) + 1
            league_urls = []
            for tr in all_trs[start:]:
                anchors = tr.find_all("a")
                if anchors:
                    league_urls.append(anchors[-1]["href"])

            logger.info(f"Found {len(league_urls)} leagues to scrape")
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

            current_date = None
            matches_div = soup.find("div", class_="wdwtablest mb30")
            if matches_div is None:
                logger.info(f"SKIPPED [{url}]: No matches")
                return

            for match_div in matches_div.contents[2:]:
                try:
                    if match_div.has_attr("class") and "wttrdt" in match_div["class"]:
                        date_str = re.sub(r"(?<=\d)(st|nd|rd|th)", "", match_div.get_text())
                        date_str = date_str.replace("Today, ", "").replace("Tomorrow, ", "")
                        current_date = datetime.strptime(date_str, "%A, %B %d, %Y").replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                        continue

                    inner = match_div.contents[:-1]
                    home_team = inner[0].find("div").get_text()
                    away_team = inner[1].find("div").get_text()

                    score_text = inner[-1].get_text()
                    home = float(score_text.split("-")[0])
                    away = float(score_text.split("-")[1])
                    predictions = [Score(WINDRAWWIN_NAME, home, away)]

                    mo_tag = match_div.find("div", class_="wtmo")
                    ou_tag = match_div.find("div", class_="wtou")
                    bt_tag = match_div.find("div", class_="wtbt")

                    odds = Odds(
                        home=mo_tag.contents[1].get_text() if mo_tag else None,
                        draw=mo_tag.contents[2].get_text() if mo_tag else None,
                        away=mo_tag.contents[3].get_text() if mo_tag else None,
                        over_25=ou_tag.contents[1].get_text() if ou_tag else None,
                        under_25=ou_tag.contents[2].get_text() if ou_tag else None,
                        btts_y=bt_tag.contents[1].get_text() if bt_tag else None,
                        btts_n=bt_tag.contents[2].get_text() if bt_tag else None,
                    )

                    league = TOP_LEAGUES.get(url) if self.top_leagues_only and url in TOP_LEAGUES else None
                    self.add_match(Match(home_team, away_team, current_date, predictions, odds, league=league))

                except Exception as e:
                    logger.error(f"SKIPPED [{url}]: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
