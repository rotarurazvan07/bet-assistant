from scrape_kit import get_logger

logger = get_logger(__name__)

import re
from datetime import datetime

from bs4 import BeautifulSoup
from scrape_kit import ScrapeMode, fetch, scrape
from dataclasses import dataclass, fields
from bet_framework.core.Match import *
import json
from .BaseMatchFinder import BaseMatchFinder

WINDRAWWIN_NAME = "windrawwin"
WINDRAWWIN_URL = "https://www.windrawwin.com/predictions/"
MAX_CONCURRENCY = 3


class WinDrawWinFinder(BaseMatchFinder):
    def __init__(self, add_match_callback) -> None:
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        page = fetch(WINDRAWWIN_URL, stealthy_headers=True)
        soup = BeautifulSoup(page, "html.parser")

        all_trs = soup.find("div", class_="widetable").find_all("tr")
        start = next(i for i, r in enumerate(all_trs) if "European Leagues" in r.text) + 1
        league_urls = []
        for tr in all_trs[start:]:
            anchors = tr.find_all("a")
            if anchors:
                league_urls.append(anchors[-1]["href"])

        logger.info(f"Found {len(league_urls)} leagues to scrape")
        matches_urls=[]
        for url in league_urls:
            page = fetch(url, stealthy_headers=True)
            soup = BeautifulSoup(page, "html.parser")
            fixtures = soup.find_all("div", class_="wtfixt")
            for fixture in fixtures:
                match_url = fixture.find("a").get("href")
                matches_urls.append(match_url)

        logger.info(f"Found {len(matches_urls)} matches to scrape")
        return matches_urls

    def get_matches(self, urls) -> None:
        scrape(
            urls,
            self._parse_page,
            mode=ScrapeMode.STEALTH,
            max_concurrency=MAX_CONCURRENCY,
        )

    def _parse_page(self, url, html) -> None:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            if "Voting Is Now Closed" in html:
                logger.error(f"Skipping {url} as voting is closed")
                return
            # Extract teams
            home_team, away_team = "Unknown", "Unknown"
            h1 = soup.find('h1', class_='h1sm')
            teams_text = h1.get_text().strip().split(" v ") if h1 else []
            home_team = teams_text[0].strip()
            away_team = teams_text[1].strip()

            start_date = next((json.loads(s.string)['startDate'] for s in soup.find_all('script', type='application/ld+json')
                            if s.string and 'SportsEvent' in s.string and 'startDate' in s.string), None)
            date_time = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)

            # Extract predictions from feature tip
            score_text = soup.find('div', class_='featurescore').get_text().strip()
            home_score = float(score_text.split('-')[0].strip())
            away_score = float(score_text.split('-')[1].strip())
            predictions = [Score(WINDRAWWIN_NAME, home_score, away_score)]

            # Extract odds
            market_map = {
                'MATCH WINNER': ['home', 'draw', 'away'],
                'BOTH TEAMS TO SCORE': ['btts_y', 'btts_n'],
                'OVER/UNDER 2.5 GOALS': ['over_25', 'under_25'],
                'OVER/UNDER 1.5 GOALS': ['over_15', 'under_15']
            }

            # 2. Collect data into a dictionary first
            odds_data = {}

            for header_text, attr_names in market_map.items():
                div = soup.find('div', class_='feature2', string=header_text)
                if div:
                    parent = div.find_parent('div', class_='compareoddswrapper')
                    links = parent.find_all('a', class_='btnstsm')
                    if len(links) == len(attr_names):
                        for i, attr in enumerate(attr_names):
                            try:
                                odds_data[attr] = float(links[i].get_text(strip=True))
                            except (ValueError, TypeError):
                                logger.error(f"Could not parse odds for {attr} in {url}")
                                continue

            # 3. Create the object in "one shot" if we found any data
            # We unpack odds_data into the constructor; missing fields will use dataclass defaults
            odds = Odds(**odds_data) if odds_data else None

            # Create the Match object
            match = Match(
                home_team=home_team,
                away_team=away_team,
                datetime=date_time,
                predictions=predictions,
                odds=odds
            )

            self.add_match(match)

        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
