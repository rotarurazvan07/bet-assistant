"""Match finder for soccervista.com per-match pages."""

from bet_crawler.crawler_logging import exception_event, get_logger, log_event

logger = get_logger(__name__)

import json
import re
from dataclasses import fields
from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape

from bet_framework.core.Match import *
from bet_framework.markets.catalog import MARKET_BY_KEY

from .BaseMatchFinder import BaseMatchFinder

SOCCERVISTA_URL = "https://www.soccervista.com"
SOCCERVISTA_NAME = "soccervista"
MAX_CONCURRENCY = 5


class SoccerVistaFinder_per_match(BaseMatchFinder):
    """Scrapes soccervista match pages via browser sessions."""

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        """Wire the finder contract for soccervista (see BaseMatchFinder)."""
        super().__init__(add_match_callback, **runtime_settings)

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
                    logger.warning(
                        "Skipping SoccerVista league listing with missing tournament selector: %s",
                        link,
                        extra={
                            "event": "source.discovery.candidate_skipped",
                            "outcome": "warning",
                            "reason_code": "tournament_selector_missing",
                            "source_key": "soccervista",
                            "url": link,
                        },
                    )

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
                    if isinstance(data, dict) and data.get("@type") == [
                        "Event",
                        "SportsEvent",
                    ]:
                        url = data.get("url").replace("/fr/", "/")
                        if url:
                            matches_url.append(url)
                            # matches_url.append(SOCCERVISTA_URL + url)
                except Exception as e:
                    logger.warning(
                        "Skipping malformed SoccerVista JSON-LD candidate on %s: %s",
                        league_url,
                        e,
                        extra={
                            "event": "source.discovery.candidate_skipped",
                            "outcome": "warning",
                            "reason_code": "json_ld_parse_failed",
                            "source_key": "soccervista",
                            "url": league_url,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                    )
                    continue

        logger.info(f"{len(matches_url)} matches to scrape")
        return matches_url

    def get_matches(self, urls) -> None:
        """Open soccervista match pages via browser and emit matches."""
        scrape(
            urls,
            self._parse_page_with_log_context,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        """Parse one soccervista match page and emit via callback."""
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
            exception_event(
                logger,
                event="source.page.failed",
                reason_code="page_parse_failed",
                message=f"Failed to parse SoccerVista match page {url}: {e}",
                source_key="soccervista",
                url=url,
            )

    def _extract_match_metadata(self, soup):
        """Extract teams and kickoff datetime from a match anchor."""
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
            except (json.JSONDecodeError, TypeError) as exc:
                log_event(
                    logger,
                    event="source.match_metadata.invalid",
                    outcome="warning",
                    reason_code="json_ld_metadata_invalid",
                    level=30,
                    message=f"Ignoring malformed SoccerVista match metadata: {exc}",
                    source_key="soccervista",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                continue

        return home_team, away_team, match_datetime

    def _extract_predictions(self, soup):
        """Extract source score predictions from the page."""
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
            logger.error(
                "No correct score prediction found in the page",
                extra={
                    "event": "match.prediction_missing",
                    "outcome": "error",
                    "reason_code": "correct_score_prediction_missing",
                    "source_key": "soccervista",
                },
            )
            return None

    def _extract_odds(self, soup):
        """Extract 1X2 odds from the page; None legs when absent."""
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
            "odds-link-yes": MARKET_BY_KEY["btts_yes"].key,
            "odds-link-no": MARKET_BY_KEY["btts_no"].key,
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
                log_event(
                    logger,
                    event="match.odds_field_unavailable",
                    outcome="warning",
                    reason_code="odds_field_parse_failed",
                    level=30,
                    message=f"Odds field {attr_name} could not be extracted from {class_name}: {e}",
                    source_key="soccervista",
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                continue
        valid_field_names = {f.name for f in fields(Odds)}
        final_payload = {k: v for k, v in extracted_data.items() if k in valid_field_names}
        return Odds(**final_payload)
