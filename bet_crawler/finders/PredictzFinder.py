from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup

from bet_framework.core.Match import *
from scrape_kit import ScrapeMode, scrape
from scrape_kit import fetch

from .BaseMatchFinder import BaseMatchFinder

PREDICTZ_URL = "https://www.predictz.com/"
PREDICTZ_NAME = "predictz"
MAX_CONCURRENCY = 3

EXCLUDED = [
    "https://www.predictz.com/predictions/england/community-shield/",
    "https://www.predictz.com/predictions/england/fa-cup/",
    "https://www.predictz.com/predictions/england/efl-cup/",
    "https://www.predictz.com/predictions/england/womens-super-league/",
    "https://www.predictz.com/predictions/scotland/scottish-cup/",
    "https://www.predictz.com/predictions/scotland/scottish-league-cup/",
    "https://www.predictz.com/predictions/spain/copa-del-rey/",
    "https://www.predictz.com/predictions/spain/supercopa-de-espana/",
    "https://www.predictz.com/predictions/germany/dfb-pokal/",
    "https://www.predictz.com/predictions/italy/coppa-italia/",
    "https://www.predictz.com/predictions/france/coupe-de-france/",
    "https://www.predictz.com/predictions/france/coupe-de-la-ligue/",
    "https://www.predictz.com/predictions/brazil/copa-do-brasil/",
    "https://www.predictz.com/predictions/usa/leagues-cup/",
]


class PredictzFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        page = fetch(PREDICTZ_URL, stealthy_headers=False)
        soup = BeautifulSoup(page, "html.parser")
        league_urls = []
        for optgroup in soup.find(class_="dd nav-select").find_all("optgroup")[6:]:
            league_urls += [
                opt.get("value")
                for opt in optgroup.find_all("option")
                if opt.get("value") not in EXCLUDED
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

            if "This could be due to games currently in play" in html:
                logger.info(f"No matches in {url}")
                return

            match_datetime = None
            for entry in soup.find_all(class_="pzcnth"):
                if entry.find("h2"):
                    date_str = entry.find("h2").get_text()
                    clean = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str).replace(
                        ",", ""
                    )
                    match_datetime = next(
                        dt
                        for y in range(datetime.now().year - 1, datetime.now().year + 2)
                        for dt in [datetime.strptime(f"{clean} {y}", "%A %B %d %Y")]
                        if dt.strftime("%A") in date_str
                    ).replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    home_team = entry.find(class_="fixt").get_text().split(" vs ")[0]
                    away_team = entry.find(class_="fixt").get_text().split(" vs ")[1]

                    score_text = entry.find("td").get_text()[-3:]
                    scores = [
                        Score(
                            PREDICTZ_NAME,
                            int(score_text.split("-")[0]),
                            int(score_text.split("-")[1]),
                        )
                    ]

                    try:
                        odds = Odds(
                            home=entry.find_all(class_="odds")[0].get_text(),
                            draw=entry.find_all(class_="odds")[1].get_text(),
                            away=entry.find_all(class_="odds")[2].get_text(),
                            over=None,
                            under=None,
                            btts_y=None,
                            btts_n=None,
                        )
                    except (AttributeError, IndexError):
                        odds = None

                    self.add_match(
                        Match(home_team, away_team, match_datetime, scores, odds)
                    )

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")


