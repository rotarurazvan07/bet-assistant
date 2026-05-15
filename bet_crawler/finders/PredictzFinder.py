from datetime import datetime
import re

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score, Odds

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

PREDICTZ_URL = "https://www.predictz.com/"
PREDICTZ_NAME = "predictz"

TOP_LEAGUES = [
    "https://www.predictz.com/predictions/europe/champions-league/",
    "https://www.predictz.com/predictions/europe/europa-league/",
    "https://www.predictz.com/predictions/europe/europa-conference-league/",
    "https://www.predictz.com/predictions/england/premier-league/",
    "https://www.predictz.com/predictions/italy/serie-a/",
    "https://www.predictz.com/predictions/spain/la-liga/",
    "https://www.predictz.com/predictions/germany/bundesliga/",
    "https://www.predictz.com/predictions/france/ligue-1/",
    "https://www.predictz.com/predictions/belgium/first-division-a/",
    "https://www.predictz.com/predictions/england/championship/",
    "https://www.predictz.com/predictions/portugal/primeira-liga/",
    "https://www.predictz.com/predictions/brazil/serie-a/",
    "https://www.predictz.com/predictions/usa/major-league-soccer/",
    "https://www.predictz.com/predictions/netherlands/eredivisie/",
    "https://www.predictz.com/predictions/denmark/superliga/",
    "https://www.predictz.com/predictions/poland/ekstraklasa/",
    "https://www.predictz.com/predictions/argentina/liga-profesional/",
    "https://www.predictz.com/predictions/japan/j-league/",
    "https://www.predictz.com/predictions/turkey/super-lig/",
    "https://www.predictz.com/predictions/sweden/allsvenskan/",
]


class PredictzFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        """Return discovery URL or top leagues."""
        if self.top_leagues_only:
            return TOP_LEAGUES
        return [PREDICTZ_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse either discovery page or league page."""
        if url == PREDICTZ_URL:
            self._parse_discovery_page(page)
        else:
            self._parse_league_page(url, page)

    def _parse_discovery_page(self, page: Page) -> None:
        """Extract league URLs from discovery page and scrape them."""
        try:
            nav_select = page.find(".dd.nav-select")
            if not nav_select:
                logger.warning("Nav select not found, falling back to TOP_LEAGUES")
                self.collect_urls(TOP_LEAGUES)
                return

            options = nav_select.select("option")
            league_urls = [
                opt.attr("value")
                for opt in options
                if opt.attr("value") and "/predictions/" in opt.attr("value")
            ]

            if league_urls:
                logger.info(f"Found {len(league_urls)} leagues to scrape")
                self.collect_urls(league_urls)
            else:
                logger.warning("No league URLs found, falling back to TOP_LEAGUES")
                self.collect_urls(TOP_LEAGUES)
        except Exception as e:
            logger.warning(f"Failed to parse discovery page: {e}, falling back to TOP_LEAGUES")
            self.collect_urls(TOP_LEAGUES)

    def _parse_league_page(self, url: str, page: Page) -> None:
        try:
            if "This could be due to games currently in play" in page.content:
                logger.debug(f"No matches in {url}")
                return

            match_datetime = None
            # Find the match containers
            entries = page.find(".pzcnth")
            
            for entry in entries:
                try:
                    # Date header
                    h2 = entry.find("h2")
                    if h2:
                        date_str = h2[0].text().strip()
                        # Clean ordinal suffixes (1st, 2nd, etc.)
                        clean = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str).replace(",", "")
                        
                        # Try to find valid year
                        current_year = datetime.now().year
                        for y in [current_year, current_year + 1]:
                            try:
                                dt = datetime.strptime(f"{clean} {y}", "%A %B %d %Y")
                                if dt.strftime("%A") in date_str:
                                    match_datetime = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                                    break
                            except ValueError:
                                continue
                        continue

                    # Match row
                    fixture_tag = entry.find(".fixt")
                    if not fixture_tag:
                        continue
                        
                    teams = fixture_tag[0].text().split(" vs ")
                    if len(teams) < 2:
                        continue
                        
                    home_team = teams[0].strip()
                    away_team = teams[1].strip()

                    # Prediction score
                    tds = entry.find("td")
                    if not tds:
                        continue
                        
                    score_text = tds[0].text().strip()[-3:]
                    if "-" in score_text:
                        home_p, away_p = score_text.split("-")
                        predictions = [Score(PREDICTZ_NAME, int(home_p), int(away_p))]
                    else:
                        continue

                    # Odds
                    odds_elements = entry.find(".odds")
                    odds = None
                    if len(odds_elements) >= 3:
                        try:
                            odds = Odds(
                                home=float(odds_elements[0].text().strip()),
                                draw=float(odds_elements[1].text().strip()),
                                away=float(odds_elements[2].text().strip())
                            )
                        except (ValueError, TypeError):
                            pass

                    self.add_match(Match(home_team, away_team, match_datetime, predictions, odds))

                except Exception as e:
                    logger.debug(f"Skipping entry in {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
