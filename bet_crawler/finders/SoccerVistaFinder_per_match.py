import json
import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

SOCCERVISTA_URL = "https://www.soccervista.com"
SOCCERVISTA_NAME = "soccervista"

TOP_LEAGUES = [
    "https://www.soccervista.com/soccer-predictions-champions-league-702.html",
    "https://www.soccervista.com/soccer-predictions-europa-league-703.html",
    "https://www.soccervista.com/soccer-predictions-conference-league-883.html",
    "https://www.soccervista.com/soccer-predictions-premier-league-704.html",
    "https://www.soccervista.com/soccer-predictions-laliga-705.html",
    "https://www.soccervista.com/soccer-predictions-bundesliga-707.html",
    "https://www.soccervista.com/soccer-predictions-serie-a-708.html",
    "https://www.soccervista.com/soccer-predictions-ligue-1-709.html",
]


class SoccerVistaFinder_per_match(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return league URLs for match URL discovery."""
        return TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse league page (discovery) or match page."""
        if "soccer-predictions-" in url:
            self._parse_league_for_matches(url, page)
        else:
            self._parse_match_page(url, page)

    def _parse_league_for_matches(self, url: str, page: Page) -> None:
        """Extract match URLs from JSON-LD on league page."""
        try:
            match_urls = []
            scripts = page.select("script[type='application/ld+json']")
            for script in scripts:
                text = script.text()
                if "SportsEvent" not in text:
                    continue
                try:
                    data = json.loads(text)
                    events = data if isinstance(data, list) else [data]
                    for event in events:
                        event_url = event.get("url", "")
                        if event_url:
                            full = event_url if event_url.startswith("http") else SOCCERVISTA_URL + event_url
                            match_urls.append(full)
                except json.JSONDecodeError:
                    pass
            # Also try extracting from links
            if not match_urls:
                links = page.select("a[href*='match']")
                for link in links:
                    href = link.attr("href")
                    if href:
                        full = href if href.startswith("http") else SOCCERVISTA_URL + "/" + href.lstrip("/")
                        match_urls.append(full)
            if match_urls:
                logger.info(f"Found {len(match_urls)} match URLs from {url}")
                self.collect_urls(match_urls)
        except Exception as e:
            logger.error(f"Error extracting match URLs from {url}: {e}")

    def _parse_match_page(self, url: str, page: Page) -> None:
        """Parse individual match page for predictions and odds."""
        try:
            # Extract from JSON-LD
            home_team, away_team, match_date = None, None, None
            scripts = page.select("script[type='application/ld+json']")
            for script in scripts:
                text = script.text()
                if "SportsEvent" not in text:
                    continue
                try:
                    data = json.loads(text)
                    home_team = data.get("homeTeam", {}).get("name")
                    away_team = data.get("awayTeam", {}).get("name")
                    start = data.get("startDate", "")
                    if start:
                        match_date = datetime.strptime(start, "%Y-%m-%dT%H:%M").replace(second=0, microsecond=0)
                except (json.JSONDecodeError, ValueError):
                    pass
                break
            if not home_team or not away_team:
                return
            if not match_date:
                match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # Predictions from script text
            predictions = []
            all_scripts = page.select("script")
            for script in all_scripts:
                text = script.text()
                m = re.search(r"correctScorePrediction.*?(\d+)\s*[-:]\s*(\d+)", text)
                if m:
                    predictions = [Score(SOCCERVISTA_NAME, float(m.group(1)), float(m.group(2)))]
                    break
            if not predictions:
                return
            # Odds from CSS classes
            odds_map = {
                "odds-link-1": "home", "odds-link-X": "draw", "odds-link-2": "away",
                "odds-link-over": "over_25", "odds-link-under": "under_25",
                "odds-link-btts-yes": "btts_y", "odds-link-btts-no": "btts_n",
            }
            odds_data = {}
            for css_class, attr in odds_map.items():
                el = page.find(f".{css_class}")
                if el:
                    try:
                        odds_data[attr] = float(el.text().strip())
                    except (ValueError, TypeError):
                        pass
            odds = Odds(**odds_data) if odds_data else None
            self.add_match(Match(home_team, away_team, match_date, predictions, odds))
        except Exception as e:
            logger.error(f"Error parsing match {url}: {e}")