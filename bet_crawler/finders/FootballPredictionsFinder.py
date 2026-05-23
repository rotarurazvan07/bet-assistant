from scrape_kit import ScrapeMode, get_logger, scrape

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.core.leagues import *
from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

FOOTBALLPREDICTIONS_URL = "https://footballpredictions.com/"
FOOTBALLPREDICTIONS_NAME = "footballpredictions"
MAX_CONCURRENCY = 1

TOP_LEAGUES = {
    "https://footballpredictions.com/footballpredictions/championsleaguepredictions/": CHAMPIONS_LEAGUE,
    "https://footballpredictions.com/footballpredictions/europaleaguepredictions/": EUROPA_LEAGUE,
    "https://footballpredictions.com/footballpredictions/europa-conference-league-predictions/": CONFERENCE_LEAGUE,
    "https://footballpredictions.com/footballpredictions/premierleaguepredictions/": PREMIER_LEAGUE,
    "https://footballpredictions.com/footballpredictions/serieapredictions/": SERIE_A,
    "https://footballpredictions.com/footballpredictions/primeradivisionpredictions/": LA_LIGA,
    "https://footballpredictions.com/footballpredictions/bundesligapredictions/": BUNDESLIGA,
    "https://footballpredictions.com/footballpredictions/ligue1predictions/": LIGUE_1,
    "https://footballpredictions.com/footballpredictions/belgium-pro-league-predictions/": JUPILER_PRO_LEAGUE,
    "https://footballpredictions.com/footballpredictions/championshippredictions/": CHAMPIONSHIP,
    "https://footballpredictions.com/footballpredictions/portugal-primeira-liga-predictions/": LIGA_PORTUGAL,
    "https://footballpredictions.com/footballpredictions/mlspredictions/": MLS,
    "https://footballpredictions.com/footballpredictions/netherlands-eredivisie-predictions/": EREDIVISIE,
    "https://footballpredictions.com/footballpredictions/sweden-allsvenskan-predictions/": ALLSVENSKAN,
    "https://footballpredictions.com/footballpredictions/segunda-division-predictions/": SEGUNDA_DIVISION,
    "https://footballpredictions.com/footballpredictions/norway-eliteserien-predictions/": ELITESERIEN,
    "https://footballpredictions.com/footballpredictions/serie-b-predictions/": SERIE_B,
    "https://footballpredictions.com/footballpredictions/bundesliga-2-predictions/": BUNDESLIGA_2,
    "https://footballpredictions.com/footballpredictions/scottish-premiership-predictions/": SCOTTISH_PREMIERSHIP,
}


class FootballPredictionsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        return list(TOP_LEAGUES.keys())

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.FAST,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        soup = BeautifulSoup(html, "html.parser")
        # Select all rows in the table body that contain match data (skip header)
        all_anchors = soup.select("table.table-tips tbody tr:has(td)")  # tr elements with <td> (data rows)
        logger.info(f"Found {len(all_anchors)} matches to scan")

        for row in all_anchors:
            try:
                # --- Team names ---
                team_wrappers = row.find_all("span", class_="table-tips__team-wrapper")
                home_team = team_wrappers[0].find("span").get_text(strip=True)
                away_team = team_wrappers[1].find("span").get_text(strip=True)

                # --- Date and time ---
                date_wrapper = row.find("span", class_="table-tips__date-time-wrapper")
                match_date_str = date_wrapper["data-datetime"]  # e.g. "2026-05-11T20:00:00+01:00"
                match_date = datetime.fromisoformat(match_date_str).replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=None
                )

                # --- Correct score prediction ---
                tips_td = row.find_all("td")[1]
                # Find the <li> containing "Correct Score:" text
                score_item = tips_td.find("li", string=re.compile(r"Correct Score:"))
                score_text = score_item.get_text(strip=True)  # "Correct Score: 2-1"
                home_goals, away_goals = map(int, score_text.split(": ")[1].split("-"))

                # Build prediction object (Score is assumed to be defined elsewhere)
                prediction = Score(FOOTBALLPREDICTIONS_NAME, home_goals, away_goals)

                # Add match to the collector
                league = TOP_LEAGUES.get(url) if self.top_leagues_only and url in TOP_LEAGUES else None
                self.add_match(Match(home_team, away_team, match_date, [prediction], None, league=league))

            except Exception as e:
                logger.error(f"SKIPPED: Parse error - {e}")
