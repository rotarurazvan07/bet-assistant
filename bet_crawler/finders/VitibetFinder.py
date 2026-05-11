import re
from datetime import datetime

from bs4 import BeautifulSoup, Tag
from scrape_kit import get_logger

logger = get_logger(__name__)

from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

VITIBET_URL = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"
VITIBET_NAME = "vitibet"
MAX_CONCURRENCY = 3

TOP_LEAGUES = [
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=2&lang=en",     # Champions League
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=3&lang=en",     # Europa League
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=848&lang=en",   # Conference League
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=39&lang=en",    # Premier League
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=135&lang=en",   # Serie A
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=140&lang=en",   # LaLiga
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=78&lang=en",    # Bundesliga
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=61&lang=en",    # Ligue 1
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=144&lang=en",   # Jupiler Pro League
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=40&lang=en",    # Championship
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=94&lang=en",    # Primeira Liga
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=71&lang=en",    # Brazil Serie A
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=253&lang=en",   # MLS
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=88&lang=en",    # Eredivisie
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=119&lang=en",   # Denmark Superliga
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=106&lang=en",   # Ekstraklasa
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=128&lang=en",   # Argentina Liga Profesional
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=98&lang=en",    # Japan J1 League
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=203&lang=en",   # Süper Lig
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=113&lang=en",   # Allsvenskan
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=210&lang=en",   # Croatia HNL
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=262&lang=en",   # Liga MX
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=141&lang=en",   # Segunda Division
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=103&lang=en",   # Eliteserien
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=218&lang=en",   # Austria Bundesliga
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=207&lang=en",   # Switzerland Super League
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=136&lang=en",   # Serie B
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=79&lang=en",    # 2. Bundesliga
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=62&lang=en",    # Ligue 2
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=179&lang=en",   # Scotland Premiership
]

class VitibetFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_matches_urls(self):
        if self.top_leagues_only:
            return TOP_LEAGUES
        else:
            html = fetch(VITIBET_URL, stealthy_headers=True)
            soup = BeautifulSoup(html, "html.parser")

            kokos_tag = soup.find("ul", id="primarne").find("kokos")
            league_urls = []
            for sibling in kokos_tag.find_next_siblings():
                if isinstance(sibling, Tag) and sibling.name == "li":
                    link = sibling.find("a")
                    if not link:
                        continue
                    href = link.get("href", "")
                    league_urls.append("https://www.vitibet.com" + href)

            logger.info(f"Found {len(league_urls)} leagues to scrape")
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

            for match_link in soup.find_all("a", class_="upcoming-match-wrapper"):
                try:
                    prev_date_div = match_link.find_previous("div", style=lambda x: x and "background: linear-gradient" in x)
                    date_span = prev_date_div.find("span", string=re.compile(r"\d{2}\.\d{2}\.\d{4}"))
                    date_str = date_span.text.strip()
                    match_datetime = datetime.strptime(date_str, "%d.%m.%Y").replace(hour=0, minute=0, second=0)

                    # Home team
                    home_div = match_link.find("div", class_="mc-team")
                    home_team = home_div.find("span").text.strip()

                    # Away team
                    away_divs = match_link.find_all("div", class_="mc-team")
                    away_team = away_divs[1].find("span").text.strip()

                    # Score prediction
                    score_div = match_link.find("div", class_="mc-score")
                    predictions = [
                        Score(
                            VITIBET_NAME,
                            float(score_div.text.strip().split(" : ")[0]),
                            float(score_div.text.strip().split(" : ")[1]),
                        )
                    ]

                    self.add_match(
                        Match(
                            home_team=home_team,
                            away_team=away_team,
                            datetime=match_datetime,
                            predictions=predictions,
                            odds=None,
                        )
                    )

                except Exception as e:
                    logger.error(f"SKIPPED [{url}]: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
