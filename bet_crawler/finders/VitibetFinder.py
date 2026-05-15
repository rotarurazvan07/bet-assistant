from datetime import datetime, timedelta

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

VITIBET_URL = "https://www.vitibet.com/index.php?clanek=analyzy&sekce=fotbal&lang=en"
VITIBET_NAME = "vitibet"


class VitibetFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        urls = [f"{VITIBET_URL}&day={i}" for i in range(self.num_days_ahead + 1)]
        logger.info(f"{len(urls)} urls to scrape")
        return urls

    def _parse_page(self, url: str, page: Page) -> None:
        try:
            rows = page.select("table.prediction tr")
            if not rows:
                logger.warning(f"No table rows found for {url}")
                return

            # Skip header row
            for row in rows[1:]:
                try:
                    cols = row.select("td")
                    if len(cols) < 5:
                        continue

                    date_str = cols[0].text().strip()
                    home_team = cols[1].text().strip()
                    away_team = cols[2].text().strip()
                    
                    try:
                        home_score = float(cols[3].text().strip())
                        away_score = float(cols[4].text().strip())
                    except (ValueError, IndexError):
                        # Some rows might be headers or empty
                        continue

                    # Try to parse date (Vitibet format: DD.MM.YYYY)
                    try:
                        match_date = datetime.strptime(date_str, "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
                    except ValueError:
                        # Fallback to current date + offset from URL if date column is weird
                        day_offset = int(url.split("day=")[-1]) if "day=" in url else 0
                        match_date = (datetime.now() + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)

                    predictions = [Score(VITIBET_NAME, home_score, away_score)]
                    self.add_match(Match(home_team, away_team, match_date, predictions))

                except Exception as e:
                    logger.debug(f"Skipping row in {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
