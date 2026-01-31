import re
from datetime import datetime

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper, ScrapeMode

FOOTBALLBETTINGTIPS_URL = "https://www.footballbettingtips.org/"
FOOTBALLBETTINGTIPS_NAME = "FootballBettingTips"
MAX_CONCURRENCY = 1


class FootballBettingTipsFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        """Load main page via browser (CF bypass), extract prediction URLs."""
        with WebScraper.browser(solve_cloudflare=True) as session:
            page = session.fetch(FOOTBALLBETTINGTIPS_URL)
            soup = BeautifulSoup(page.html_content, 'html.parser')

        return [FOOTBALLBETTINGTIPS_URL + a.find("a")['href'] for a in soup.find_all("h3")[:2]]

    def get_matches(self, urls):
        self.scrape_urls(urls, self._parse_page, mode=ScrapeMode.FAST, max_concurrency=MAX_CONCURRENCY)

    def _parse_page(self, url, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            match_datetime = datetime.strptime(soup.find_all('h2')[-1].get_text(), "%A, %d %B %Y")

            for match_html in soup.find("table", class_="results").find_all("tr"):
                if not match_html.find("a"):
                    continue

                home_team_name = match_html.find("a").get_text().split(" - ")[0]
                away_team_name = match_html.find("a").get_text().split(" - ")[1]

                score_text = re.search(r"(\d+:\d+)", match_html.find_all("td")[-2].get_text()).group(1)
                score = Score(FOOTBALLBETTINGTIPS_NAME, score_text.split(":")[0], score_text.split(":")[1])

                result = "Home Win" if score.home > score.away else "Draw" if score.home == score.away else "Away Win"
                try:
                    odds = float(soup.find_all(class_='desktop')[0].get_text()) if score.home > score.away else \
                        float(soup.find_all(class_='desktop')[1].get_text()) if score.home == score.away else \
                        float(soup.find_all(class_='desktop')[2].get_text())
                except:
                    odds = None

                tips = [Tip(raw_text=result, confidence=100, source=FOOTBALLBETTINGTIPS_NAME, odds=odds)]

                self.add_match(Match(
                    home_team=Team(home_team_name, None, None, None),
                    away_team=Team(away_team_name, None, None, None),
                    datetime=match_datetime,
                    predictions=MatchPredictions([score], None, tips),
                    h2h=None,
                ))
        except Exception as e:
            print(f"Error parsing {url}: {e}")
