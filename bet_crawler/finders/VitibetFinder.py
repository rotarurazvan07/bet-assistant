from datetime import datetime, timedelta

from bs4 import BeautifulSoup, Tag
from scrape_kit import get_logger

logger = get_logger(__name__)

from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

VITIBET_URL = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"
VITIBET_NAME = "vitibet"
MAX_CONCURRENCY = 3

EXCLUDED = {
    "/index.php?clanek=tips&sekce=fotbal&liga=champions2&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=champions3&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=champions4&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=euro_national_league&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=southamerica&lang=en",
    "/index.php?clanek=euro-2008&liga=euro&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=africancup&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=angliezeny&lang=en",
    "/index.php?clanek=tips&sekce=fotbal&liga=euro2024&lang=en",
}


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
                if any(ex in href for ex in EXCLUDED):
                    continue
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

            matches_table = soup.find("table", class_="tabulkaquick")
            if not matches_table:
                logger.info(f"SKIPPED [{url}]: No matches table")
                return

            for match_tag in matches_table.find_all("tr")[2:]:
                try:
                    tds = match_tag.find_all("td")
                    if tds[5].get_text() == "?" or tds[7].get_text() == "?":
                        continue

                    today = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    day, month = map(int, tds[0].get_text().split("."))
                    candidate = datetime(today.year, month, day)
                    if candidate - today > timedelta(days=300):
                        candidate = candidate.replace(year=today.year - 1)
                    elif today - candidate > timedelta(days=300):
                        candidate = candidate.replace(year=today.year + 1)

                    predictions = [
                        Score(
                            VITIBET_NAME,
                            float(tds[5].get_text()),
                            float(tds[7].get_text()),
                        )
                    ]
                    self.add_match(
                        Match(
                            tds[2].get_text(),
                            tds[3].get_text(),
                            candidate,
                            predictions,
                            None,
                        )
                    )

                except Exception as e:
                    logger.info(f"SKIPPED [{url}]: {e}")

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
