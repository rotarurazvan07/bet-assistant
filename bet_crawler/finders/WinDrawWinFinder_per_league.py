import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"

TOP_LEAGUES = [
    "https://www.windrawwin.com/tips/champions-league/",
    "https://www.windrawwin.com/tips/europa-league/",
    "https://www.windrawwin.com/tips/europa-conference-league/",
    "https://www.windrawwin.com/tips/england-premier-league/",
    "https://www.windrawwin.com/tips/italy-serie-a/",
    "https://www.windrawwin.com/tips/spain-la-liga/",
    "https://www.windrawwin.com/tips/germany-bundesliga/",
    "https://www.windrawwin.com/tips/france-ligue-1/",
    "https://www.windrawwin.com/tips/belgium-first-division-a/",
    "https://www.windrawwin.com/tips/england-championship/",
    "https://www.windrawwin.com/tips/portugal-primeira-liga/",
    "https://www.windrawwin.com/tips/brazil-serie-a/",
    "https://www.windrawwin.com/tips/usa-major-league-soccer/",
    "https://www.windrawwin.com/tips/netherlands-eredivisie/",
    "https://www.windrawwin.com/tips/denmark-superliga/",
    "https://www.windrawwin.com/tips/poland-ekstraklasa/",
    "https://www.windrawwin.com/tips/argentina-liga-profesional/",
    "https://www.windrawwin.com/tips/japan-j-league/",
    "https://www.windrawwin.com/tips/turkey-super-lig/",
    "https://www.windrawwin.com/tips/sweden-allsvenskan/",
    "https://www.windrawwin.com/tips/croatia-1-hnl/",
    "https://www.windrawwin.com/tips/mexico-liga-mx/",
    "https://www.windrawwin.com/tips/spain-segunda-division/",
    "https://www.windrawwin.com/tips/norway-eliteserien/",
    "https://www.windrawwin.com/tips/austria-bundesliga/",
    "https://www.windrawwin.com/tips/switzerland-super-league/",
    "https://www.windrawwin.com/tips/italy-serie-b/",
    "https://www.windrawwin.com/tips/germany-2-bundesliga/",
    "https://www.windrawwin.com/tips/france-ligue-2/",
    "https://www.windrawwin.com/tips/scotland-premiership/",
]


class WinDrawWinFinder_per_league(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return predictions page for league discovery."""
        return [WINDRAWWIN_URL]

    def get_match_urls(self) -> list[str]:
        """Return league URLs directly or discover them."""
        if self.top_leagues_only:
            return TOP_LEAGUES
        self.scrape()
        return self.collected_urls if self.collected_urls else TOP_LEAGUES

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse discovery or league page."""
        if url == WINDRAWWIN_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_league_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract league URLs from predictions page."""
        try:
            table_div = page.find("div.widetable")
            if not table_div:
                logger.warning("No WinDrawWin league table found")
                return
            rows = table_div.select("tr")
            start = None
            for i, r in enumerate(rows):
                if "Cup and International Leagues" in r.text():
                    start = i + 1
                    break
            if start is None:
                logger.warning("No WinDrawWin league URLs found, parsing current page")
                return
            league_urls = []
            for tr in rows[start:]:
                links = tr.select("a")
                if links:
                    href = links[-1].attr("href")
                    if href:
                        league_urls.append(href if href.startswith("http") else "https://www.windrawwin.com" + href)
            if league_urls:
                logger.info(f"Found {len(league_urls)} WinDrawWin leagues")
                self.collect_urls(league_urls)
        except Exception as e:
            logger.error(f"Error discovering leagues: {e}")

    def _parse_league_page(self, url: str, page: Page) -> None:
        """Parse match predictions from a league tips page."""
        try:
            matches_div = page.find("div.wdwtablest.mb30")
            if not matches_div:
                logger.debug(f"No matches on {url}")
                return
            current_date = None
            children = matches_div.children()
            for child in children:
                try:
                    classes = child.classes or []
                    # Date row
                    if "wttrdt" in classes:
                        date_text = re.sub(r"(?<=\d)(st|nd|rd|th)", "", child.text())
                        date_text = date_text.replace("Today, ", "").replace("Tomorrow, ", "")
                        try:
                            current_date = datetime.strptime(date_text.strip(), "%A, %B %d, %Y")
                        except ValueError:
                            current_date = self.parse_date_robust(date_text.strip())
                        continue
                    # Match row: extract teams and score from children
                    inner = child.children()
                    if len(inner) < 3:
                        continue
                    home_el = inner[0].find("div")
                    away_el = inner[1].find("div")
                    if not home_el or not away_el:
                        continue
                    home_team = home_el.text().strip()
                    away_team = away_el.text().strip()
                    score_text = inner[-1].text().strip()
                    if "-" not in score_text:
                        continue
                    home_score = float(score_text.split("-")[0])
                    away_score = float(score_text.split("-")[1])
                    predictions = [Score(WINDRAWWIN_NAME, home_score, away_score)]
                    # Odds (optional)
                    odds = None
                    mo = child.find("div.wtmo")
                    ou = child.find("div.wtou")
                    bt = child.find("div.wtbt")
                    if mo:
                        mo_children = mo.children()
                        if len(mo_children) >= 4:
                            try:
                                odds = Odds(
                                    home=mo_children[1].text().strip(),
                                    draw=mo_children[2].text().strip(),
                                    away=mo_children[3].text().strip(),
                                    over_25=ou.children()[1].text().strip() if ou and len(ou.children()) >= 3 else None,
                                    under_25=ou.children()[2].text().strip() if ou and len(ou.children()) >= 3 else None,
                                    btts_y=bt.children()[1].text().strip() if bt and len(bt.children()) >= 3 else None,
                                    btts_n=bt.children()[2].text().strip() if bt and len(bt.children()) >= 3 else None,
                                )
                            except Exception:
                                pass
                    match_date = current_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    self.add_match(Match(home_team, away_team, match_date, predictions, odds))
                except Exception as e:
                    logger.debug(f"Skipping match: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")