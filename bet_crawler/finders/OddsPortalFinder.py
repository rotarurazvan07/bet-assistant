import json
import threading
from datetime import datetime, timedelta, timezone

from scrape_kit import get_logger, Page, fetch

from bet_framework.core.Match import Match, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

ODDSPORTAL_NAME = "oddsportal"

TOP_LEAGUES = [
    "https://www.oddsportal.com/football/europe/champions-league/",
    "https://www.oddsportal.com/football/europe/europa-league/",
    "https://www.oddsportal.com/football/europe/europa-conference-league/",
    "https://www.oddsportal.com/football/england/premier-league/",
    "https://www.oddsportal.com/football/italy/serie-a/",
    "https://www.oddsportal.com/football/spain/laliga/",
    "https://www.oddsportal.com/football/germany/bundesliga/",
    "https://www.oddsportal.com/football/france/ligue-1/",
    "https://www.oddsportal.com/football/belgium/jupiler-pro-league/",
    "https://www.oddsportal.com/football/england/championship/",
    "https://www.oddsportal.com/football/portugal/liga-portugal/",
    "https://www.oddsportal.com/football/brazil/serie-a/",
    "https://www.oddsportal.com/football/usa/mls/",
    "https://www.oddsportal.com/football/netherlands/eredivisie/",
    "https://www.oddsportal.com/football/denmark/superliga/",
    "https://www.oddsportal.com/football/poland/ekstraklasa/",
    "https://www.oddsportal.com/football/argentina/liga-profesional/",
    "https://www.oddsportal.com/football/japan/j1-league/",
    "https://www.oddsportal.com/football/turkey/super-lig/",
    "https://www.oddsportal.com/football/sweden/allsvenskan/",
    "https://www.oddsportal.com/football/croatia/1-hnl/",
    "https://www.oddsportal.com/football/mexico/liga-mx/",
    "https://www.oddsportal.com/football/spain/laliga2/",
    "https://www.oddsportal.com/football/norway/eliteserien/",
    "https://www.oddsportal.com/football/austria/bundesliga/",
    "https://www.oddsportal.com/football/switzerland/super-league/",
    "https://www.oddsportal.com/football/italy/serie-b/",
    "https://www.oddsportal.com/football/germany/2-bundesliga/",
    "https://www.oddsportal.com/football/france/ligue-2/",
    "https://www.oddsportal.com/football/scotland/premiership/",
]


class OddsPortalFinder(BaseMatchFinder):
    """OddsPortal finder with discovery in prepare_scrape phase.

    prepare_scrape: fetches league pages via HTTP, extracts match URLs from JSON-LD.
    scrape: uses browser mode to scrape individual match pages for odds.
    """

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)
        self._add_match_lock = threading.Lock()

    def get_urls(self) -> list[str]:
        """Not used directly - discovery happens in get_match_urls."""
        return TOP_LEAGUES

    def get_match_urls(self) -> list[str]:
        """Discovery phase: fetch league pages and extract match URLs from JSON-LD."""
        urls = []
        today = datetime.now(timezone.utc).date()
        max_date = today + timedelta(days=self.num_days_ahead)

        for league_url in TOP_LEAGUES if self.top_leagues_only else TOP_LEAGUES:
            try:
                page = fetch(league_url, stealthy_headers=True)
                if not page:
                    continue
                links = []
                for script in page.select('script[type="application/ld+json"]'):
                    try:
                        data = json.loads(script.text())
                        events = data if isinstance(data, list) else [data]
                        for event in events:
                            if not isinstance(event, dict):
                                continue
                            if not event.get("url") or not event.get("startDate"):
                                continue
                            status = event.get("eventStatus")
                            is_scheduled = (
                                status == "Scheduled"
                                or (
                                    isinstance(status, dict)
                                    and (
                                        status.get("name") == "EventScheduled"
                                        or status.get("@id") == "https://schema.org/EventScheduled"
                                    )
                                )
                            )
                            if not is_scheduled:
                                continue
                            ev_date = datetime.fromisoformat(
                                event["startDate"].replace("Z", "+00:00")
                            ).date()
                            if today <= ev_date <= max_date:
                                ev_url = event["url"]
                                if not ev_url.startswith("http"):
                                    ev_url = "https://www.oddsportal.com" + ev_url
                                links.append(ev_url)
                    except (json.JSONDecodeError, ValueError):
                        continue
                urls.extend(list(dict.fromkeys(links)))
                logger.info(f"Found {len(links)} match URLs on {league_url} (total: {len(urls)})")
            except Exception as e:
                logger.error(f"Failed to scrape {league_url}: {e}")
        logger.info(f"Total URLs found: {len(urls)}")
        return list(set(urls))

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse individual match page for teams, date, and odds."""
        try:
            # Teams
            home_el = page.find("div[data-testid='game-host'] a")
            away_el = page.find("div[data-testid='game-guest'] a")
            if not home_el or not away_el:
                home_el = page.find("div[data-testid='game-host']")
                away_el = page.find("div[data-testid='game-guest']")
            if not home_el or not away_el:
                logger.debug(f"No teams found on {url}")
                return
            home_team = home_el.text().strip()
            away_team = away_el.text().strip()
            if not home_team or not away_team:
                return
            # Date
            time_items = page.select("div[data-testid='game-time-item'] p")
            match_date = None
            if time_items:
                date_text = " ".join(t.text().strip() for t in time_items)
                match_date = self.parse_date_robust(date_text)
            if not match_date:
                match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # 1X2 Odds
            odds_containers = page.select("div[data-testid='odd-container'] p")
            odds_data = {}
            if len(odds_containers) >= 3:
                try:
                    odds_data["home"] = float(odds_containers[0].text().strip())
                    odds_data["draw"] = float(odds_containers[1].text().strip())
                    odds_data["away"] = float(odds_containers[2].text().strip())
                except (ValueError, TypeError):
                    pass
            odds = Odds(**odds_data) if odds_data else None
            with self._add_match_lock:
                self.add_match(Match(home_team, away_team, match_date, [], odds))
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")