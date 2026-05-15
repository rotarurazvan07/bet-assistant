import re
from datetime import datetime

from scrape_kit import get_logger, Page

from bet_framework.core.Match import Match, Score

from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

EAGLEPREDICT_URL = "https://eaglepredict.com/predictions/correct-score/"
EAGLEPREDICT_NAME = "eaglepredict"


class EaglePredictFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)

    def get_urls(self) -> list[str]:
        return [EAGLEPREDICT_URL]

    def get_match_urls(self) -> list[str]:
        return [EAGLEPREDICT_URL]

    def _parse_page(self, url: str, page: Page) -> None:
        """Parse correct score predictions from EaglePredict."""
        try:
            # EaglePredict uses match cards/blocks with team images and scores
            # Look for containers with match info
            match_blocks = page.select("div.single-match, div.match-card, div.prediction-card, article.post")
            if not match_blocks:
                # Fallback: try to find any container with team images
                match_blocks = page.select("div.match, div.game, div.fixture")
            if not match_blocks:
                logger.debug(f"No match blocks on {url}")
                # Try parsing from raw text as fallback
                self._parse_from_text(url, page)
                return
            for block in match_blocks:
                try:
                    # Try to get teams from img alt attributes
                    imgs = block.select("img")
                    teams = []
                    for img in imgs:
                        alt = img.attr("alt")
                        if alt and alt.strip():
                            teams.append(alt.strip())
                    if len(teams) < 2:
                        # Try from text spans/divs
                        team_els = block.select("span.team, div.team, h4, h5")
                        for el in team_els:
                            t = el.text().strip()
                            if t:
                                teams.append(t)
                    if len(teams) < 2:
                        continue
                    home_team = teams[0]
                    away_team = teams[1]
                    # Score prediction
                    block_text = block.text()
                    m = re.search(r"Correct\s*Score[:\s]*(\d+)\s*[-:]\s*(\d+)", block_text, re.IGNORECASE)
                    if not m:
                        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", block_text)
                    if not m:
                        continue
                    home_score = float(m.group(1))
                    away_score = float(m.group(2))
                    # Date
                    date_match = re.search(r"(\d{1,2})\s+(\w{3,})\s+(\d{4})", block_text)
                    if date_match:
                        match_date = self.parse_date_robust(date_match.group(0))
                    else:
                        match_date = None
                    if not match_date:
                        match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    predictions = [Score(EAGLEPREDICT_NAME, home_score, away_score)]
                    self.add_match(Match(home_team, away_team, match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping block: {e}")
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")

    def _parse_from_text(self, url: str, page: Page) -> None:
        """Fallback: parse matches from page text using patterns."""
        try:
            text = page.text_content
            # Find all "Team1 vs Team2" followed by score
            matches_found = re.findall(
                r"(.+?)\s+vs\s+(.+?)\s*.*?Correct\s*Score[:\s]*(\d+)\s*[-:]\s*(\d+)",
                text, re.IGNORECASE
            )
            for home, away, hs, as_ in matches_found:
                try:
                    predictions = [Score(EAGLEPREDICT_NAME, float(hs), float(as_))]
                    match_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    self.add_match(Match(home.strip(), away.strip(), match_date, predictions, None))
                except Exception as e:
                    logger.debug(f"Skipping text match: {e}")
        except Exception as e:
            logger.debug(f"Text fallback failed: {e}")