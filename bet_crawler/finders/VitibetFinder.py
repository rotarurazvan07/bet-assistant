import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

VITIBET_URL = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"
VITIBET_NAME = "vitibet"

TOP_LEAGUES = [
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=2&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=3&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=848&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=39&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=135&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=140&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=78&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=61&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=144&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=40&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=94&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=71&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=253&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=88&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=119&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=106&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=128&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=98&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=203&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=113&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=210&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=262&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=141&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=103&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=218&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=207&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=136&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=79&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=62&lang=en",
    "https://www.vitibet.com/index.php?clanek=leagues&sekce=fotbal&liga=179&lang=en",
]


class VitibetFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URL for league extraction."""
        return [VITIBET_URL]

    def get_match_urls(self) -> list[str]:
        """Return league URLs directly (or discover all leagues)."""
        if self.top_leagues_only:
            return TOP_LEAGUES
        self.scrape()
        return self.collected_urls if self.collected_urls else TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse league pages or discovery page."""
        if url == VITIBET_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_league_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract league URLs from quicktips page."""
        try:
            nav = page.find_by_id("primarne")
            if not nav:
                return
            links = nav.select("li a")
            league_urls = []
            for link in links:
                href = link.attr("href")
                if href and "clanek=leagues" in href:
                    league_urls.append("https://www.vitibet.com" + href)
            if league_urls:
                logger.info(f"Found {len(league_urls)} leagues")
                self.collect_urls(league_urls)
        except Exception as e:
            logger.error(f"Error discovering leagues: {e}")

    def _parse_league_page(self, url: str, page: Page) -> None:
        """Parse match predictions from a league page."""
        try:
            match_links = page.select("a.upcoming-match-wrapper")
            if not match_links:
                logger.debug(f"No matches on {url}")
                return
            for match_el in match_links:
                try:
                    # Date: walk prev siblings to find gradient div
                    date_str = None
                    cur = match_el.prev_sibling()
                    while cur:
                        style = cur.attr("style") or ""
                        if "linear-gradient" in style:
                            text = cur.text()
                            m = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
                            if m:
                                date_str = m.group(0)
                            break
                        cur = cur.prev_sibling()
                    if date_str:
                        match_date = datetime.strptime(date_str, "%d.%m.%Y")
                    else:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    # Teams
                    team_divs = match_el.select("div.mc-team")
                    if len(team_divs) < 2:
                        continue
                    home_team = team_divs[0].find("span").text().strip()
                    away_team = team_divs[1].find("span").text().strip()
                    # Score
                    score_div = match_el.find("div.mc-score")
                    if not score_div:
                        continue
                    score_text = score_div.text().strip()
                    if " : " not in score_text:
                        continue
                    parts = score_text.split(" : ")
                    home_score = float(parts[0])
                    away_score = float(parts[1])
                    predictions = [Score(VITIBET_NAME, home_score, away_score)]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.error(f"SKIPPED [{url}]: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")