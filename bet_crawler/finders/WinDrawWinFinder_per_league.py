from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"
MAX_CONCURRENCY = 1

TOP_LEAGUES = [
    "https://www.windrawwin.com/tips/champions-league/",
    "https://www.windrawwin.com/tips/europa-league/",
    "https://www.windrawwin.com/tips/europa-conference-league/",
    "https://www.windrawwin.com/tips/england-premier-league/",
    "https://www.windrawwin.com/tips/italy-serie-a/",
    "https://www.windrawwin.com/tips/spain-la-liga/",
    "https://www.windrawwin.com/tips/germany-bundesliga/",
    "https://www.windrawwin.com/tips/france-ligue-1/",
    "https://www.windrawwin.com/tips/belgium-first-division-a/",  # Jupiler Pro League
    "https://www.windrawwin.com/tips/england-championship/",
    "https://www.windrawwin.com/tips/portugal-primeira-liga/",
    "https://www.windrawwin.com/tips/brazil-serie-a/",
    "https://www.windrawwin.com/tips/usa-major-league-soccer/",  # MLS
    "https://www.windrawwin.com/tips/netherlands-eredivisie/",
    "https://www.windrawwin.com/tips/denmark-superliga/",
    "https://www.windrawwin.com/tips/poland-ekstraklasa/",
    "https://www.windrawwin.com/tips/argentina-liga-profesional/",
    "https://www.windrawwin.com/tips/japan-j-league/",  # J1 League
    "https://www.windrawwin.com/tips/turkey-super-lig/",
    "https://www.windrawwin.com/tips/sweden-allsvenskan/",
    "https://www.windrawwin.com/tips/croatia-1-hnl/",  # HNL
    "https://www.windrawwin.com/tips/mexico-liga-mx/",
    "https://www.windrawwin.com/tips/spain-segunda-division/",
    "https://www.windrawwin.com/tips/norway-eliteserien/",
    "https://www.windrawwin.com/tips/austria-bundesliga/",
    "https://www.windrawwin.com/tips/switzerland-super-league/",
    "https://www.windrawwin.com/tips/italy-serie-b/",
    "https://www.windrawwin.com/tips/germany-2-bundesliga/",
    "https://www.windrawwin.com/tips/france-ligue-2/",
    "https://www.windrawwin.com/tips/scotland-premiership/",
]


class WinDrawWinFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        if self.top_leagues_only:
            return TOP_LEAGUES
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
                    if len(inner) < 2:
                        continue

                    home_div = inner[0].find("div")
                    away_div = inner[1].find("div")
                    if not home_div or not away_div:
                        continue

                    home_team = home_div.get_text(strip=True)
                    away_team = away_div.get_text(strip=True)

                    score_text = inner[-1].get_text(strip=True)
                    if "-" not in score_text:
                        continue

                    try:
                        home = float(score_text.split("-")[0])
                        away = float(score_text.split("-")[1])
                    except ValueError:
                        continue

                    predictions = [Score(WINDRAWWIN_NAME, home, away)]

                    mo_tag = match_div.find("div", class_="wtmo")
                    ou_tag = match_div.find("div", class_="wtou")
                    bt_tag = match_div.find("div", class_="wtbt")

                    def safe_get(tag, idx):
                        return tag.contents[idx].get_text(strip=True) if tag and len(tag.contents) > idx else None

                    odds = Odds(
                        home=safe_get(mo_tag, 1),
                        draw=safe_get(mo_tag, 2),
                        away=safe_get(mo_tag, 3),
                        over_25=safe_get(ou_tag, 1),
                        under_25=safe_get(ou_tag, 2),
                        btts_y=safe_get(bt_tag, 1),
                        btts_n=safe_get(bt_tag, 2),
                    )

                    self.add_match(Match(home_team, away_team, current_date, predictions, odds))

                except Exception as e:
                    logger.error(f"SKIPPED [{url}]: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
