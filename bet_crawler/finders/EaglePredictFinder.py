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
        soup = BeautifulSoup(html, "html.parser")

        MONTHS = {
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

        seen = set()
        current_date = None

        for node in soup.descendants:
            if not isinstance(node, NavigableString):
                continue

            text = node.strip()
            if not text:
                continue

            # --- DATE ---
            m = re.match(r"\w{3}\s*-\s*(\d{1,2})\s+(\w{3})\s+(\d{4})", text)
            if m:
                d, mth, y = m.groups()
                current_date = (int(y), MONTHS[mth], int(d))
                continue

            # --- SCORE ---
            if "Correct Score:" not in text:
                continue

            score_match = re.search(r"(\d+)\s*-\s*(\d+)", text)
            if not score_match:
                continue

            # --- container ---
            container = node.parent
            for _ in range(10):
                if not container:
                    break
                if len(container.find_all("img")) >= 2:
                    break
                container = container.parent

            if not container:
                continue

            # --- teams ---
            teams = []
            for img in container.find_all("img"):
                alt = img.get("alt", "").replace(" Logo", "").strip()
                if alt and alt not in teams:
                    teams.append(alt)
                if len(teams) == 2:
                    break

            if len(teams) < 2:
                continue

            home, away = teams

            # --- time ---
            local_time = None
            for t in container.stripped_strings:
                if re.fullmatch(r"\d{2}:\d{2}", t):
                    local_time = t
                    break

            if not (current_date and local_time):
                continue

            h, m = map(int, local_time.split(":"))
            dt = datetime(current_date[0], current_date[1], current_date[2], h, m)

            key = (home.lower(), away.lower(), dt)
            if key in seen:
                continue
            seen.add(key)

            # --- callback ---
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
