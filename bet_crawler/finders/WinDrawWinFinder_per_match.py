import json
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"


class WinDrawWinFinder_per_match(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return predictions page for league discovery."""
        return [WINDRAWWIN_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse discovery page or individual match page."""
        if url == WINDRAWWIN_URL or "/predictions/" in url:
            self._parse_discovery_page(url, page)
        else:
            self._parse_match_page(url, page)

    def _parse_discovery_page(self, url: str, page: Page) -> None:
        """Extract league URLs, then match URLs from league pages."""
        try:
            table_div = page.find("div.widetable")
            if not table_div:
                return
            rows = table_div.select("tr")
            start = None
            for i, r in enumerate(rows):
                if "European Leagues" in r.text():
                    start = i + 1
                    break
            if start is None:
                return
            league_urls = []
            for tr in rows[start:]:
                links = tr.select("a")
                if links:
                    href = links[-1].attr("href")
                    if href:
                        league_urls.append(href if href.startswith("http") else "https://www.windrawwin.com" + href)
            # Now extract match URLs from fixtures on league pages
            match_urls = []
            fixtures = page.select("div.wtfixt a")
            for f in fixtures:
                href = f.attr("href")
                if href:
                    match_urls.append(href if href.startswith("http") else "https://www.windrawwin.com" + href)
            if match_urls:
                self.collect_urls(match_urls)
            elif league_urls:
                self.collect_urls(league_urls)
        except Exception as e:
            logger.error(f"Error in discovery: {e}")

    def _parse_match_page(self, url: str, page: Page) -> None:
        """Parse individual match page for predictions and odds."""
        try:
            if page.contains("Voting Is Now Closed"):
                logger.debug(f"Voting closed on {url}")
                return
            # Teams from h1
            h1 = page.find("h1.h1sm")
            if not h1:
                return
            teams_text = h1.text().strip().split(" v ")
            if len(teams_text) < 2:
                return
            home_team = teams_text[0].strip()
            away_team = teams_text[1].strip()
            # Date from JSON-LD
            match_date = None
            scripts = page.select("script[type='application/ld+json']")
            for script in scripts:
                text = script.text()
                if "SportsEvent" in text and "startDate" in text:
                    try:
                        data = json.loads(text)
                        start_date = data.get("startDate", "")
                        match_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S%z").replace(
                            tzinfo=None, hour=0, minute=0, second=0, microsecond=0
                        )
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break
            if not match_date:
                match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # Score prediction
            score_el = page.find("div.featurescore")
            if not score_el:
                return
            score_text = score_el.text().strip()
            if "-" not in score_text:
                return
            home_score = float(score_text.split("-")[0].strip())
            away_score = float(score_text.split("-")[1].strip())
            predictions = [Score(WINDRAWWIN_NAME, home_score, away_score)]
            # Odds
            market_map = {
                "MATCH WINNER": ["home", "draw", "away"],
                "BOTH TEAMS TO SCORE": ["btts_y", "btts_n"],
                "OVER/UNDER 2.5 GOALS": ["over_25", "under_25"],
                "OVER/UNDER 1.5 GOALS": ["over_15", "under_15"],
            }
            odds_data = {}
            for header_text, attr_names in market_map.items():
                header = page.find_by_text("div.feature2", header_text)
                if not header:
                    continue
                parent = header.parent()
                if not parent:
                    continue
                # Walk up to find compareoddswrapper
                wrapper = parent
                for _ in range(5):
                    if wrapper and "compareoddswrapper" in (wrapper.classes or []):
                        break
                    wrapper = wrapper.parent() if wrapper else None
                if not wrapper:
                    continue
                btns = wrapper.select("a.btnstsm")
                if len(btns) == len(attr_names):
                    for i, attr in enumerate(attr_names):
                        try:
                            odds_data[attr] = float(btns[i].text().strip())
                        except (ValueError, TypeError):
                            pass
            odds = Odds(**odds_data) if odds_data else None
            self.add_match(Match(home_team, away_team, match_date, predictions, odds))
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")