from scrape_kit import fetch, get_logger

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString

from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

EAGLEPREDICT_URL = "https://eaglepredict.com/predictions/correct-score/"
EAGLEPREDICT_NAME = "eaglepredict"
MAX_CONCURRENCY = 1


class EaglePredictFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        return [EAGLEPREDICT_URL]

    def get_matches(self, urls=None) -> None:
        page = fetch(EAGLEPREDICT_URL, stealthy_headers=False)
        self._parse_page(None, page)

    def _parse_page(self, _, html) -> None:
        """Parse the EaglePredict page and extract match data."""
        soup = BeautifulSoup(html, "html.parser")
        MONTHS = self._get_month_mapping()
        seen = set()
        current_date = None

        for node in soup.descendants:
            if not isinstance(node, NavigableString):
                continue

            text = node.strip()
            if not text:
                continue

            # Check for date
            date_info = self._extract_date(text, MONTHS)
            if date_info:
                current_date = date_info
                continue

            # Check for score
            if "Correct Score:" not in text:
                continue

            score_match = re.search(r"(\d+)\s*-\s*(\d+)", text)
            if not score_match:
                continue

            # Find container with team images
            container = self._find_match_container(node)
            if not container:
                continue

            # Extract teams
            teams = self._extract_teams(container)
            if len(teams) < 2:
                continue

            home, away = teams

            # Extract time
            local_time = self._extract_time(container)
            if not (current_date and local_time):
                continue

            dt = self._build_datetime(current_date, local_time)

            key = (home.lower(), away.lower(), dt)
            if key in seen:
                continue
            seen.add(key)

            # Create and add match
            self._create_and_add_match(home, away, dt, score_match)

    def _get_month_mapping(self) -> dict[str, int]:
        """Return mapping of month abbreviations to numbers."""
        return {
            "Jan": 1,
            "Feb": 2,
            "Mar": 3,
            "Apr": 4,
            "May": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12,
        }

    def _extract_date(self, text: str, months: dict[str, int]) -> tuple[int, int, int] | None:
        """Extract date tuple (year, month, day) from text. Returns None if not a date."""
        m = re.match(r"\w{3}\s*-\s*(\d{1,2})\s+(\w{3})\s+(\d{4})", text)
        if m:
            d, mth, y = m.groups()
            return (int(y), months[mth], int(d))
        return None

    def _find_match_container(self, node) -> any:
        """Find the container element that holds the match information (with team images)."""
        container = node.parent
        for _ in range(10):
            if not container:
                break
            if len(container.find_all("img")) >= 2:
                break
            container = container.parent
        return container

    def _extract_teams(self, container) -> list[str]:
        """Extract team names from image alt attributes in the container."""
        teams = []
        for img in container.find_all("img"):
            alt = img.get("alt", "").replace(" Logo", "").strip()
            if alt and alt not in teams:
                teams.append(alt)
            if len(teams) == 2:
                break
        return teams

    def _extract_time(self, container) -> str | None:
        """Extract time string (HH:MM) from container. Returns None if not found."""
        for t in container.stripped_strings:
            if re.fullmatch(r"\d{2}:\d{2}", t):
                return t
        return None

    def _build_datetime(self, date_tuple: tuple[int, int, int], time_str: str) -> datetime:
        """Build datetime object from date tuple and time string."""
        h, m = map(int, time_str.split(":"))
        return datetime(date_tuple[0], date_tuple[1], date_tuple[2], h, m)

    def _create_and_add_match(self, home: str, away: str, dt: datetime, score_match) -> None:
        """Create Match object and add it via callback."""
        self.add_match(
            Match(
                home,
                away,
                dt,
                [
                    Score(
                        EAGLEPREDICT_NAME,
                        score_match.group(1),
                        score_match.group(2),
                    )
                ],
                odds=None,
                result_url=None,
            )
        )
