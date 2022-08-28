import random
import re
import threading
import time
from datetime import datetime

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.core.Tip import Tip
from bet_framework.WebScraper import WebScraper

FOOTBALLBETTINGTIPS_URL = "https://www.footballbettingtips.org/"
FOOTBALLBETTINGTIPS_NAME = "FootballBettingTips"


class FootballBettingTipsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self.web_scraper = None

    def get_matches(self):
        try:
            self.get_web_scraper(profile='slow')
            self.web_scraper.custom_cookies = [{"name" :"PHPSESSID", "value" :"kse1hmbd8hp4376e0qi3pkfkds", "domain":FOOTBALLBETTINGTIPS_URL, "path":"/"}, {"domain":FOOTBALLBETTINGTIPS_URL, "path":"/", "name":"cf_clearance","value":"3.xvccJzPcJRy9eYSNeRbpRsbQqmdw0OJqdxa6NiOS8-1766613032-1.2.1.1-DliIBfsnVxyONDUI.FH7U777u81jW8rtSLiiMeWycGxP63eOWde3CNJIBdw0mxitN6N7IBB55hEFgZlJNdKn.gHfUW_P2Dehu_k1RtRltJEOjzxjX8b9cCET4b88IkQ6jUSVuP0rEw_2sQj8eAb.hmQ2rZPnPB11BeyCHVqCRzhGlwbJGHTvgmdJVMPOoawbPdgtAXmOCkUiUTZJlCUhCoEAakJLnWNbBBcEAPiRuLo"}]
            html = self.web_scraper.load_page(FOOTBALLBETTINGTIPS_URL, additional_wait=4.0)
            soup = BeautifulSoup(html, 'html.parser')

            predictions = [a.find("a")['href'] for a in soup.find_all("h3")[:2]]
            for pred_url in predictions:
                html = self.web_scraper.fast_http_request(FOOTBALLBETTINGTIPS_URL + pred_url)
                soup = BeautifulSoup(html, 'html.parser')
                match_datetime = soup.find_all('h2')[-1].get_text()
                match_datetime = datetime.strptime(match_datetime, "%A, %d %B %Y")

                matches_table = soup.find("table", class_="results").find_all("tr")
                for match_html in matches_table:
                    if match_html.find("a"):
                        home_team_name = match_html.find("a").get_text().split(" - ")[0]
                        away_team_name = match_html.find("a").get_text().split(" - ")[1]

                        home_team = Team(home_team_name, None, None, None)
                        away_team = Team(away_team_name, None, None, None)

                        score = match_html.find_all("td")[-2].get_text()
                        score = re.search(r"(\d+:\d+)", score).group(1)
                        score = Score(FOOTBALLBETTINGTIPS_NAME, score.split(":")[0], score.split(":")[1])

                        scores = [score]
                        probabilities = None
                        tips = []

                        result = "Home Win" if scores[0].home > scores[0].away else "Draw" if scores[0].home == scores[0].away else "Away Win"
                        # Promote fixed confidence to 0-100 scale
                        confidence = 100
                        try:
                            odds = float(soup.find_all(class_='desktop')[0].get_text()) if scores[0].home > scores[0].away else \
                                float(soup.find_all(class_='desktop')[1].get_text()) if scores[0].home == scores[0].away else \
                                float(soup.find_all(class_='desktop')[2].get_text())
                        except:
                            odds = None

                        tips.append(Tip(raw_text=result, confidence=confidence, source=FOOTBALLBETTINGTIPS_NAME, odds=odds))

                        match_predictions = MatchPredictions(scores, probabilities, tips)

                        h2h_results = None

                        match_to_add = Match(
                            home_team=home_team,
                            away_team=away_team,
                            datetime=match_datetime,
                            predictions=match_predictions,
                            h2h=h2h_results,
                        )

                        self.add_match(match_to_add)
        except Exception as e:
            print(f"Caught {e} while parsing")
        finally:
            self.web_scraper.destroy_current_thread()
