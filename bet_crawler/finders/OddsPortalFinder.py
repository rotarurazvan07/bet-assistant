import json
import threading
from datetime import datetime, timedelta, timezone

from scrape_kit import browser, fetch, get_logger, Page

from bet_framework.core.Match import Match, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

ODDSPORTAL_NAME = "oddsportal"
ODDSPORTAL_URL = "https://www.oddsportal.com"

TOP_LEAGUES = [
    "https://www.oddsportal.com/football/europe/champions-league/",
    "https://www.oddsportal.com/football/europe/europa-league/",
    "https://www.oddsportal.com/football/europe/conference-league/",
    "https://www.oddsportal.com/football/england/premier-league/",
    "https://www.oddsportal.com/football/italy/serie-a/",
    "https://www.oddsportal.com/football/spain/laliga/",
    "https://www.oddsportal.com/football/germany/bundesliga/",
    "https://www.oddsportal.com/football/france/ligue-1/",
    "https://www.oddsportal.com/football/belgium/jupiler-pro-league/",
    "https://www.oddsportal.com/football/england/championship/",
    "https://www.oddsportal.com/football/portugal/liga-portugal/",
    "https://www.oddsportal.com/football/brazil/serie-a-betano/",
    "https://www.oddsportal.com/football/usa/mls/",
    "https://www.oddsportal.com/football/netherlands/eredivisie/",
    "https://www.oddsportal.com/football/denmark/superliga/",
    "https://www.oddsportal.com/football/poland/ekstraklasa/",
    "https://www.oddsportal.com/football/argentina/liga-profesional/",
    "https://www.oddsportal.com/football/japan/j1-league/",
    "https://www.oddsportal.com/football/turkey/super-lig/",
    "https://www.oddsportal.com/football/sweden/allsvenskan/",
    "https://www.oddsportal.com/football/croatia/hnl/",
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
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)
        self._add_match_lock = threading.Lock()

    def get_urls(self) -> list[str]:
        """Return discovery URLs for scraping."""
        return TOP_LEAGUES if self.top_leagues_only else [ODDSPORTAL_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Not used - this finder overrides scrape() for browser-based processing."""
        pass

    def get_match_urls(self) -> list[str]:
        """Override to return discovered match URLs for distributed scraping."""
        discovery_urls = self.get_urls()
        return self._discover_match_urls(discovery_urls)

    def scrape(self, urls: list[str] | None = None) -> None:
        """Override scrape to handle discovery + browser-based match scraping."""
        discovery_urls = urls if urls is not None else self.get_urls()

        # Phase 1: Discover match URLs from listing pages
        match_urls = self._discover_match_urls(discovery_urls)
        if not match_urls:
            logger.warning("No match URLs discovered")
            return

        logger.info(f"Total {len(match_urls)} match URLs to scrape")

        # Phase 2: Scrape match pages with browser (interactive)
        chunk_size = 10
        for i in range(0, len(match_urls), chunk_size):
            batch = match_urls[i : i + chunk_size]
            self._process_batch(batch)

    def _discover_match_urls(self, discovery_urls: list[str]) -> list[str]:
        """Extract match URLs from discovery/listing pages using fetch()."""
        all_urls = []
        today = datetime.now(timezone.utc).date()
        max_date = today + timedelta(days=self.num_days_ahead)

        for url in discovery_urls:
            try:
                page = fetch(url)
                links = self._extract_match_links_from_page(page, today, max_date)
                unique_links = list(dict.fromkeys(links))
                all_urls.extend(unique_links)
                logger.info(f"Found {len(unique_links)} match URLs on {url}")
            except Exception as e:
                logger.error(f"Failed to discover matches on {url}: {e}")

        return list(set(all_urls))

    def _extract_match_links_from_page(self, page: Page, today, max_date) -> list[str]:
        """Extract match URLs from JSON-LD on a listing page."""
        links = []
        scripts = page.select('script[type="application/ld+json"]')

        for script in scripts:
            try:
                data = json.loads(script.text())
                events = data if isinstance(data, list) else [data]
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    ev_url = event.get("url")
                    start_date = event.get("startDate")
                    status = event.get("eventStatus")
                    is_scheduled = status == "Scheduled" or (
                        isinstance(status, dict)
                        and status.get("@id") == "https://schema.org/EventScheduled"
                    )
                    if ev_url and start_date and is_scheduled:
                        ev_date = datetime.fromisoformat(
                            start_date.replace("Z", "+00:00")
                        ).date()
                        if today <= ev_date <= max_date:
                            links.append(ev_url)
            except (json.JSONDecodeError, ValueError):
                continue
        return links

    def _process_batch(self, urls: list[str]) -> None:
        """Process a batch of match URLs using browser session."""
        with browser(solve_cloudflare=True, headless=True) as session:
            for url in urls:
                try:
                    self._scrape_match_page(session, url)
                except Exception as e:
                    logger.error(f"Error parsing {url}: {e}")

    def _scrape_match_page(self, session, url: str) -> None:
        """Scrape a single match page for odds data."""
        page = session.fetch(url)

        host_tag = page.select('[data-testid="game-host"] a')
        guest_tag = page.select('[data-testid="game-guest"] a')
        time_tag = page.select('[data-testid="game-time-item"] p')

        if not host_tag or not guest_tag:
            logger.warning(f"Failed to find teams on {url}")
            return

        home_team = host_tag[0].text().strip()
        away_team = guest_tag[0].text().strip()

        date_text = time_tag[1].text().strip().rstrip(",") if len(time_tag) > 1 else ""
        try:
            match_date = datetime.strptime(date_text, "%d %B %Y").replace(hour=0, minute=0, second=0)
        except ValueError:
            match_date = datetime.now().replace(hour=0, minute=0, second=0)

        odds_data = self._collect_odds_data(session)
        odds = self._build_odds(odds_data)

        with self._add_match_lock:
            self.add_match(Match(home_team, away_team, match_date, None, odds))

    def _collect_odds_data(self, session) -> dict:
        """Collect odds data by clicking through tabs."""
        odds_data = {}

        # 1X2 Odds
        if session.click("li.odds-item", "1X2"):
            p = Page.from_html(session.page.content())
            cells = p.select('[data-testid="odd-container"]')
            if len(cells) >= 3:
                odds_data["1"] = cells[0].text().strip()
                odds_data["X"] = cells[1].text().strip()
                odds_data["2"] = cells[2].text().strip()

        # BTTS
        if session.click("li.odds-item", "Both Teams to Score"):
            p = Page.from_html(session.page.content())
            cells = p.select('[data-testid="odd-container"]')
            if len(cells) >= 2:
                odds_data["btts_y"] = cells[0].text().strip()
                odds_data["btts_n"] = cells[1].text().strip()

        # Double Chance
        if session.click("li.odds-item", "Double Chance"):
            p = Page.from_html(session.page.content())
            cells = p.select('[data-testid="odd-container"]')
            if len(cells) >= 3:
                odds_data["dc_1x"] = cells[0].text().strip()
                odds_data["dc_12"] = cells[1].text().strip()
                odds_data["dc_x2"] = cells[2].text().strip()

        # Over/Under
        if session.click("li.odds-item", "Over/Under"):
            p = Page.from_html(session.page.content())
            rows = p.select('[data-testid="over-under-collapsed-row"]')
            for row in rows:
                opt = row.select('[data-testid="over-under-collapsed-option-box"]')
                conts = row.select('[data-testid="odd-container-default"]')
                if opt and len(conts) >= 2:
                    name = opt[0].text().strip()
                    over = conts[0].text().strip()
                    under = conts[1].text().strip()
                    if "+2.5" in name:
                        odds_data["over_25"] = over
                        odds_data["under_25"] = under
                    elif "+1.5" in name:
                        odds_data["over_15"] = over
                        odds_data["under_15"] = under

        return odds_data

    def _build_odds(self, odds_data: dict) -> Odds:
        """Build Odds object from collected data."""
        def to_float(val):
            if not val or val == "-":
                return None
            try:
                return float(val)
            except ValueError:
                return None

        return Odds(
            home=to_float(odds_data.get("1")),
            draw=to_float(odds_data.get("X")),
            away=to_float(odds_data.get("2")),
            over_15=to_float(odds_data.get("over_15")),
            under_15=to_float(odds_data.get("under_15")),
            over_25=to_float(odds_data.get("over_25")),
            under_25=to_float(odds_data.get("under_25")),
            btts_y=to_float(odds_data.get("btts_y")),
            btts_n=to_float(odds_data.get("btts_n")),
            dc_1x=to_float(odds_data.get("dc_1x")),
            dc_12=to_float(odds_data.get("dc_12")),
            dc_x2=to_float(odds_data.get("dc_x2")),
        )
