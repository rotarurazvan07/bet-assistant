import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

FOREBET_URL = "https://www.forebet.com"
FOREBET_ALL_PREDICTIONS_URL = "https://www.forebet.com/en/football-predictions"
FOREBET_NAME = "forebet"
MAX_CONCURRENCY = 1


class ForebetFinder(BaseMatchFinder):
    """Forebet uses interactive browser (JS execution to load more matches).
    get_matches overrides the standard flow since it needs a live session.
    """

    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        return [FOREBET_URL]

    def get_matches(self, urls=None):
        """Load predictions page, execute JS to expand, then parse."""
        with WebScraper.browser(solve_cloudflare=True) as session:
            print("Loading predictions page...")
            session.fetch(FOREBET_ALL_PREDICTIONS_URL)

            print("Loading more matches...")
            for i in range(11, 30):
                try:
                    session.execute_script(f'ltodrows("1x2", {i}, "");')
                    time.sleep(2)
                except Exception as e:
                    print(f"Error loading more at index {i}: {e}")
                    break

            html = session.execute_script("return document.documentElement.outerHTML")

        self._parse_page(FOREBET_ALL_PREDICTIONS_URL, html)

    def _parse_page(self, url, html):
        soup = BeautifulSoup(html, 'html.parser')
        all_anchors = soup.find("div", id="body-main").find_all(class_="rcnt")
        print(f"Found {len(all_anchors)} matches to scan")

        for anchor in all_anchors:
            try:
                home_team = anchor.find("div", class_="tnms").find("span", class_="homeTeam").get_text()
                away_team = anchor.find("div", class_="tnms").find("span", class_="awayTeam").get_text()

                if anchor.find("div", class_="scoreLnk").get_text().strip():
                    print(f"SKIPPED [{home_team} vs {away_team}]: Match ongoing")
                    continue

                match_date = anchor.find("span", class_="date_bah").get_text()
                match_date = datetime.strptime(match_date, "%d/%m/%Y %H:%M") + timedelta(hours=7)

                home = float(anchor.find("div", class_="ex_sc").get_text().split("-")[0])
                away = float(anchor.find("div", class_="ex_sc").get_text().split("-")[1])
                predictions = [Score(FOREBET_NAME, home, away)]

                odds_tags = [o.get_text() for o in anchor.find("div", class_="haodd").find_all("span")]
                odds = Odds(
                    home=float(odds_tags[0]) if odds_tags[0] not in ("", " - ") else None,
                    draw=float(odds_tags[1]) if odds_tags[1] not in ("", " - ") else None,
                    away=float(odds_tags[2]) if odds_tags[2] not in ("", " - ") else None,
                    over=None, under=None, btts_y=None, btts_n=None
                )

                self.add_match(Match(home_team, away_team, match_date, predictions, odds))

            except Exception as e:
                print(f"SKIPPED: Parse error - {e}")