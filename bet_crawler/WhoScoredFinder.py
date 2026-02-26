import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper, ScrapeMode

WHOSCORED_URL = "https://www.whoscored.com/"
WHOSCORED_NAME = "whoscored"
MAX_CONCURRENCY = 1


class WhoScoredFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)

    def get_matches_urls(self):
        """Get match URLs via browser (needs JS rendering)."""
        with WebScraper.browser(solve_cloudflare=True) as session:
            page = session.fetch(WHOSCORED_URL + "previews")
            soup = BeautifulSoup(page.html_content, 'html.parser')

        table = soup.find("table", class_="grid")
        urls = [WHOSCORED_URL + a['href'] for a in table.find_all('a') if "matches" in a['href']]
        print(f"{len(urls)} matches to scrape")
        return urls

    def get_matches(self, urls):
        self.scrape_urls(urls, self._parse_page, mode=ScrapeMode.STEALTH, max_concurrency=MAX_CONCURRENCY)

    def _parse_page(self, url, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')

            home_team = soup.find('div', class_='teams-score-info').find("span", class_=re.compile(r'home team')).get_text()
            away_team = soup.find('div', class_='teams-score-info').find("span", class_=re.compile(r'away team')).get_text()

            match_time = (soup.find('dt', text='Date:').find_next_sibling('dd').text + " - " +
                          soup.find('dt', text='Kick off:').find_next_sibling('dd').text)
            match_datetime = datetime.strptime(match_time, "%a, %d-%b-%y - %H:%M") + timedelta(hours=2)

            score = soup.find("div", id="preview-prediction").find_all("span", class_="predicted-score")
            scores = [Score(WHOSCORED_NAME, score[0].get_text(), score[1].get_text())]

            self.add_match(Match(home_team, away_team, match_datetime, scores, None))

        except Exception as e:
            print(f"Error parsing {url}: {e}")