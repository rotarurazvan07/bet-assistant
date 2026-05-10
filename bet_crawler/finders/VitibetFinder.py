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


class VitibetFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
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
