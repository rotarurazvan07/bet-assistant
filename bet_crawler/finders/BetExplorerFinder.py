import json
import threading
from datetime import datetime, timedelta, timezone

from scrape_kit import browser, fetch, get_logger, Page

from bet_framework.core.Match import Match, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

BETEXPLORER_NAME = "betexplorer"
BETEXPLORER_URL = "https://www.betexplorer.com"

TOP_LEAGUES = [
    "https://www.betexplorer.com/football/uefa-champions-league/",
    "https://www.betexplorer.com/football/uefa-europa-league/",
    "https://www.betexplorer.com/football/uefa-europa-conference-league/",
    "https://www.betexplorer.com/football/england/premier-league/",
    "https://www.betexplorer.com/football/italy/serie-a/",
    "https://www.betexplorer.com/football/spain/laliga/",
    "https://www.betexplorer.com/football/germany/bundesliga/",
    "https://www.betexplorer.com/football/france/ligue-1/",
    "https://www.betexplorer.com/football/belgium/jupiler-pro-league/",
    "https://www.betexplorer.com/football/england/championship/",
    "https://www.betexplorer.com/football/portugal/liga-portugal/",
    "https://www.betexplorer.com/football/brazil/serie-a-betano/",
    "https://www.betexplorer.com/football/usa/mls/",
    "https://www.betexplorer.com/football/netherlands/eredivisie/",
    "https://www.betexplorer.com/football/denmark/superliga/",
    "https://www.betexplorer.com/football/poland/ekstraklasa/",
    "https://www.betexplorer.com/football/argentina/liga-profesional/",
    "https://www.betexplorer.com/football/japan/j1-league/",
    "https://www.betexplorer.com/football/turkey/super-lig/",
    "https://www.betexplorer.com/football/sweden/allsvenskan/",
    "https://www.betexplorer.com/football/croatia/hnl/",
    "https://www.betexplorer.com/football/mexico/liga-mx/",
    "https://www.betexplorer.com/football/spain/laliga2/",
    "https://www.betexplorer.com/football/norway/eliteserien/",
    "https://www.betexplorer.com/football/austria/bundesliga/",
    "https://www.betexplorer.com/football/switzerland/super-league/",
    "https://www.betexplorer.com/football/italy/serie-b/",
    "https://www.betexplorer.com/football/germany/2-bundesliga/",
    "https://www.betexplorer.com/football/france/ligue-2/",
    "https://www.betexplorer.com/football/scotland/premiership/",
]


class BetExplorerFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)
        self._add_match_lock = threading.Lock()

    def get_urls(self) -> list[str]:
        """Return discovery URLs for scraping."""
        return TOP_LEAGUES if self.top_leagues_only else [BETEXPLORER_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Not used - this finder uses browser for match scraping."""
        pass

    def get_match_urls(self) -> list[str]:
        """Override to return discovered match URLs for distributed scraping."""
        discovery_urls = self.get_urls()
        return self._discover_match_urls(discovery_urls)

    def _discover_match_urls(self, discovery_urls: list[str]) -> list[str]:
        """Extract match URLs from discovery pages using fetch()."""
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
                    is_scheduled = (
                        status == "Scheduled"
                        or status == "EventScheduled"
                        or (isinstance(status, dict) and "Scheduled" in str(status))
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

    def scrape(self, urls: list[str] | None = None) -> None:
        """Override scrape to handle discovery + browser-based match scraping."""
        if urls is None:
            urls = self._discover_match_urls(self.get_urls())

        if not urls:
            logger.warning("No match URLs discovered")
            return

        logger.info(f"Total {len(urls)} match URLs to scrape")

        # 1 worker for browser stability
        chunk_size = 10
        for i in range(0, len(urls), chunk_size):
            batch = urls[i : i + chunk_size]
            self._process_batch(batch)

    def _process_batch(self, urls: list[str]) -> None:
        with browser(solve_cloudflare=True, headless=True) as session:
            for url in urls:
                try:
                    page = session.fetch(url)
                    
                    # BetExplorer specific team selectors
                    teams = page.find(".list-details__item__title")
                    if len(teams) < 2:
                        # Fallback
                        teams = page.find("h1") # Sometimes in h1
                        if not teams: continue
                        
                    home_team = teams[0].text().strip()
                    away_team = teams[1].text().strip() if len(teams) > 1 else ""
                    
                    # Date
                    date_tag = page.find("#match-date")
                    if date_tag:
                        date_str = date_tag[0].text().strip()
                        # Format "DD.MM.YYYY - HH:MM"
                        try:
                            date_part = date_str.split(" - ")[0]
                            match_date = datetime.strptime(date_part, "%d.%m.%Y").replace(hour=0, minute=0, second=0)
                        except:
                            match_date = datetime.now().replace(hour=0, minute=0, second=0)
                    else:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0)

                    odds_data = {}
                    
                    # 1X2
                    if session.click('#bettype_menu_best li[title="1X2"]'):
                        p = Page.from_html(session.page.content())
                        avg_odds = p.find(".oddsComparisonAll__average_text")
                        if len(avg_odds) >= 3:
                            odds_data['1'] = avg_odds[0].text().strip()
                            odds_data['X'] = avg_odds[1].text().strip()
                            odds_data['2'] = avg_odds[2].text().strip()

                    # BTTS
                    if session.click('#bettype_menu_best li[title="Both Teams To Score"]'):
                        p = Page.from_html(session.page.content())
                        avg_odds = p.find(".oddsComparisonAll__average_text")
                        if len(avg_odds) >= 2:
                            odds_data['btts_y'] = avg_odds[0].text().strip()
                            odds_data['btts_n'] = avg_odds[1].text().strip()

                    # DC
                    if session.click('#bettype_menu_best li[title="Double Chance"]'):
                        p = Page.from_html(session.page.content())
                        avg_odds = p.find(".oddsComparisonAll__average_text")
                        if len(avg_odds) >= 3:
                            odds_data['dc_1x'] = avg_odds[0].text().strip()
                            odds_data['dc_12'] = avg_odds[1].text().strip()
                            odds_data['dc_x2'] = avg_odds[2].text().strip()

                    # Over/Under
                    if session.click('#bettype_menu_best li[title="Over/Under"]'):
                        # Need to click "All" for all handicaps
                        session.click(".oddsComparison__ul.bestOddsComparison li#all")
                        p = Page.from_html(session.page.content())
                        handicaps = p.find("[data-all-handicap]")
                        for h in handicaps:
                            h_val = h.attr("data-all-handicap")
                            cells = h.find(".oddsComparisonAll__average_text")
                            if len(cells) >= 2:
                                if h_val == "2.50":
                                    odds_data['over_25'] = cells[0].text().strip()
                                    odds_data['under_25'] = cells[1].text().strip()
                                elif h_val == "1.50":
                                    odds_data['over_15'] = cells[0].text().strip()
                                    odds_data['under_15'] = cells[1].text().strip()

                    def to_float(val):
                        if not val or val == "-": return None
                        try: return float(val)
                        except: return None

                    odds = Odds(
                        home=to_float(odds_data.get('1')),
                        draw=to_float(odds_data.get('X')),
                        away=to_float(odds_data.get('2')),
                        over_15=to_float(odds_data.get('over_15')),
                        under_15=to_float(odds_data.get('under_15')),
                        over_25=to_float(odds_data.get('over_25')),
                        under_25=to_float(odds_data.get('under_25')),
                        btts_y=to_float(odds_data.get('btts_y')),
                        btts_n=to_float(odds_data.get('btts_n')),
                        dc_1x=to_float(odds_data.get('dc_1x')),
                        dc_12=to_float(odds_data.get('dc_12')),
                        dc_x2=to_float(odds_data.get('dc_x2')),
                    )

                    with self._add_match_lock:
                        self.add_match(Match(home_team, away_team, match_date, None, odds))

                except Exception as e:
                    logger.error(f"Error parsing {url}: {e}")
                    continue
