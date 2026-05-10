from scrape_kit import get_logger

logger = get_logger(__name__)

import json
import re
from dataclasses import fields
from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

SOCCERVISTA_URL = "https://www.soccervista.com"
SOCCERVISTA_NAME = "soccervista"
MAX_CONCURRENCY = 5


class SoccerVistaFinder_per_match(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        """Get league URLs via fast HTTP."""
        html = fetch(SOCCERVISTA_URL, stealthy_headers=True)
        soup = BeautifulSoup(html, "html.parser")

        league_urls = []
        leagues_tag = soup.find("h3", string=lambda t: t and "Top Leagues" in t).parent
        all_links = [link["href"] for link in leagues_tag.find_all("a", href=True)][:-2]
        for link in all_links:
            html = fetch(SOCCERVISTA_URL + link)
            soup = BeautifulSoup(html, "html.parser")
            if html:
                try:
                    league_urls += [opt["value"] for opt in soup.find("select", id="tournamentPage").find_all("option")]
                except AttributeError:
                    logger.info(f"Can't parse: {link}")

        league_urls = [SOCCERVISTA_URL + url for url in league_urls]

        logger.info(f"{len(league_urls)} leagues to scrape")

        matches_url = []
        for league_url in league_urls:
            html = fetch(league_url, stealthy_headers=True)
            soup = BeautifulSoup(html, "html.parser")

            # Extract match URLs from JSON-LD structured data
            json_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_scripts:
                try:
                    import json

                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == ["Event", "SportsEvent"]:
                        url = data.get("url").replace("/fr/", "/")
                        if url:
                            matches_url.append(url)
                            # matches_url.append(SOCCERVISTA_URL + url)
                except Exception as e:
                    logger.debug(f"Failed to parse JSON-LD script: {e}")
                    continue

        logger.info(f"{len(matches_url)} matches to scrape")
        return matches_url

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

            home_team, away_team, match_datetime = self._extract_match_metadata(soup)
            scores = self._extract_predictions(soup)
            odds = self._extract_odds(soup)

            if not home_team or not away_team or not match_datetime:
                raise ValueError("Missing home or away team or match datetime")
            if not scores:
                raise ValueError("Missing predictions")

            self.add_match(
                Match(
                    home_team=home_team,
                    away_team=away_team,
                    datetime=match_datetime,
                    predictions=scores,
                    odds=odds,
                    result_url=url,
                )
            )

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")

    def _extract_match_metadata(self, soup):
        home_team = None
        away_team = None
        match_datetime = None

        # Extract and parse in one flow
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                event_type = data.get("@type", "")

                # Check if it's a SportsEvent (handling both string and list types)
                if "SportsEvent" in (event_type if isinstance(event_type, list) else [event_type]):
                    home_team = data.get("homeTeam", {}).get("name")
                    away_team = data.get("awayTeam", {}).get("name")
                    start_date = next(
                        (
                            json.loads(s.string)["startDate"]
                            for s in soup.find_all("script", type="application/ld+json")
                            if s.string and "SportsEvent" in s.string and "startDate" in s.string
                        ),
                        None,
                    )
                    match_datetime = datetime.strptime(start_date, "%Y-%m-%dT%H:%M").replace(
                        tzinfo=None, hour=0, minute=0, second=0, microsecond=0
                    )

                    break
            except (json.JSONDecodeError, TypeError):
                continue

        return home_team, away_team, match_datetime

    def _extract_predictions(self, soup):
        script_text = " ".join(script.string for script in soup.find_all("script") if script.string)
        script_text = script_text.replace("\\u0022", '"')

        correct_score_match = re.search(
            r'"correctScorePrediction"\s*:\s*\{[^}]*"score"\s*:\s*"(?P<home>\d+):(?P<away>\d+)"',
            script_text,
        )
        if correct_score_match:
            return [
                Score(
                    SOCCERVISTA_NAME,
                    correct_score_match.group("home"),
                    correct_score_match.group("away"),
                )
            ]
        else:
            logger.error("No correct score prediction found in the page")
            return None

    def _extract_odds(self, soup):
        market_map = {
            "odds-link-1": "home",
            "odds-link-X": "draw",
            "odds-link-2": "away",
            "odds-link-over-0.5": "over_05",
            "odds-link-under-0.5": "under_05",
            "odds-link-over-1.5": "over_15",
            "odds-link-under-1.5": "under_15",
            "odds-link-over-2.5": "over_25",
            "odds-link-under-2.5": "under_25",
            "odds-link-over-3.5": "over_35",
            "odds-link-under-3.5": "under_35",
            "odds-link-over-4.5": "over_45",
            "odds-link-under-4.5": "under_45",
            "odds-link-yes": "btts_y",
            "odds-link-no": "btts_n",
        }

        extracted_data = {}

        for class_name, attr_name in market_map.items():
            try:
                element = soup.find("a", class_=class_name)
                if element:
                    value = element.get_text(strip=True)
                    if value and value != "-":
                        extracted_data[attr_name] = value
            except Exception as e:
                logger.error(f"Error extracting {attr_name} for class {class_name}: {e}")
                continue
        valid_field_names = {f.name for f in fields(Odds)}
        final_payload = {k: v for k, v in extracted_data.items() if k in valid_field_names}
        return Odds(**final_payload)
