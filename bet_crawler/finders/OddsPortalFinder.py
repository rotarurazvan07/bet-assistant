import threading
import time

from scrape_kit import browser, get_logger, fetch

logger = get_logger(__name__)
import contextlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import json
from bet_framework.core.Match import *

from .BaseMatchFinder import BaseMatchFinder

ODDSPORTAL_NAME = "oddsportal"
MAX_CONCURRENCY = 1

TOP_LEAGUES = [
    "https://www.oddsportal.com/football/europe/champions-league/",
    "https://www.oddsportal.com/football/europe/europa-league/",
    "https://www.oddsportal.com/football/europe/conference-league/",
    "https://www.oddsportal.com/football/england/premier-league/",
    "https://www.oddsportal.com/football/italy/serie-a/",
    "https://www.oddsportal.com/football/spain/laliga/",
    "https://www.oddsportal.com/football/germany/bundesliga/",
    "https://www.oddsportal.com/football/france/ligue-1/",
    "https://www.oddsportal.com/football/belgium/jupiler-pro-league/",
    "https://www.oddsportal.com/football/england/championship/",
    "https://www.oddsportal.com/football/portugal/liga-portugal/",
    "https://www.oddsportal.com/football/brazil/serie-a-betano/",
    "https://www.oddsportal.com/football/usa/mls/",
    "https://www.oddsportal.com/football/netherlands/eredivisie/",
    "https://www.oddsportal.com/football/denmark/superliga/",
    "https://www.oddsportal.com/football/poland/ekstraklasa/",
    "https://www.oddsportal.com/football/argentina/liga-profesional/",
    "https://www.oddsportal.com/football/japan/j1-league/",
    "https://www.oddsportal.com/football/turkey/super-lig/",
    "https://www.oddsportal.com/football/sweden/allsvenskan/",
    "https://www.oddsportal.com/football/croatia/hnl/",
    "https://www.oddsportal.com/football/mexico/liga-mx/",
    "https://www.oddsportal.com/football/spain/laliga2/",
    "https://www.oddsportal.com/football/norway/eliteserien/",
    "https://www.oddsportal.com/football/austria/bundesliga/",
    "https://www.oddsportal.com/football/switzerland/super-league/",
    "https://www.oddsportal.com/football/italy/serie-b/",
    "https://www.oddsportal.com/football/germany/2-bundesliga/",
    "https://www.oddsportal.com/football/france/ligue-2/",
    "https://www.oddsportal.com/football/scotland/premiership/",
]

ALL_LINKS = [
    "https://www.oddsportal.com/football/world/world-cup-2026/",
    "https://www.oddsportal.com/football/germany/bundesliga/",
    "https://www.oddsportal.com/football/england/premier-league/",
    "https://www.oddsportal.com/football/italy/serie-a/",
    "https://www.oddsportal.com/football/spain/laliga/",
    "https://www.oddsportal.com/football/europe/champions-league/",
    "https://www.oddsportal.com/football/europe/europa-league/",
    "https://www.oddsportal.com/football/europe/euro-u21/",
    "https://www.oddsportal.com/football/france/ligue-1/",
    "https://www.oddsportal.com/football/albania/abissnet-superiore/",
    "https://www.oddsportal.com/football/algeria/ligue-1/",
    "https://www.oddsportal.com/football/argentina/liga-profesional/",
    "https://www.oddsportal.com/football/argentina/primera-nacional/",
    "https://www.oddsportal.com/football/argentina/primera-c/",
    "https://www.oddsportal.com/football/argentina/copa-argentina/",
    "https://www.oddsportal.com/football/argentina/primera-a-women/",
    "https://www.oddsportal.com/football/armenia/first-league/",
    "https://www.oddsportal.com/football/aruba/division-di-honor/",
    "https://www.oddsportal.com/football/asia/afc-champions-league-2/",
    "https://www.oddsportal.com/football/australia/a-league/",
    "https://www.oddsportal.com/football/australia/npl-act/",
    "https://www.oddsportal.com/football/australia/queensland-premier-league/",
    "https://www.oddsportal.com/football/australia/victoria-premier-league/",
    "https://www.oddsportal.com/football/australia/a-league-women/",
    "https://www.oddsportal.com/football/australia-oceania/ofc-pro-league/",
    "https://www.oddsportal.com/football/austria/bundesliga/",
    "https://www.oddsportal.com/football/austria/2-liga/",
    "https://www.oddsportal.com/football/bahrain/premier-league/",
    "https://www.oddsportal.com/football/barbados/premier-league/",
    "https://www.oddsportal.com/football/belarus/vysshaya-liga/",
    "https://www.oddsportal.com/football/belarus/belarusian-cup/",
    "https://www.oddsportal.com/football/belgium/jupiler-pro-league/",
    "https://www.oddsportal.com/football/belgium/belgian-cup/",
    "https://www.oddsportal.com/football/bolivia/division-profesional/",
    "https://www.oddsportal.com/football/brazil/serie-a-betano/",
    "https://www.oddsportal.com/football/brazil/serie-b/",
    "https://www.oddsportal.com/football/brazil/serie-c/",
    "https://www.oddsportal.com/football/brazil/serie-d/",
    "https://www.oddsportal.com/football/brazil/paranaense-2/",
    "https://www.oddsportal.com/football/brazil/copa-betano-do-brasil/",
    "https://www.oddsportal.com/football/brazil/copa-espirito-santo/",
    "https://www.oddsportal.com/football/brazil/copa-do-nordeste/",
    "https://www.oddsportal.com/football/brazil/kings-league-brazil/",
    "https://www.oddsportal.com/football/brazil/brasileiro-women/",
    "https://www.oddsportal.com/football/bulgaria/efbet-league/",
    "https://www.oddsportal.com/football/bulgaria/vtora-liga/",
    "https://www.oddsportal.com/football/canada/canadian-premier-league/",
    "https://www.oddsportal.com/football/canada/championship/",
    "https://www.oddsportal.com/football/chile/liga-de-primera/",
    "https://www.oddsportal.com/football/chile/liga-de-ascenso/",
    "https://www.oddsportal.com/football/chile/segunda-division/",
    "https://www.oddsportal.com/football/chile/copa-de-la-liga/",
    "https://www.oddsportal.com/football/china/super-league/",
    "https://www.oddsportal.com/football/colombia/primera-a/",
    "https://www.oddsportal.com/football/colombia/primera-b/",
    "https://www.oddsportal.com/football/colombia/copa-colombia/",
    "https://www.oddsportal.com/football/colombia/liga-women/",
    "https://www.oddsportal.com/football/costa-rica/primera-division/",
    "https://www.oddsportal.com/football/costa-rica/liga-de-ascenso/",
    "https://www.oddsportal.com/football/croatia/hnl/",
    "https://www.oddsportal.com/football/croatia/croatian-cup/",
    "https://www.oddsportal.com/football/croatia/1-hnl-women/",
    "https://www.oddsportal.com/football/cyprus/cyprus-league/",
    "https://www.oddsportal.com/football/czech-republic/chance-liga/",
    "https://www.oddsportal.com/football/czech-republic/chnl/",
    "https://www.oddsportal.com/football/czech-republic/mol-cup/",
    "https://www.oddsportal.com/football/czech-republic/4-liga-group-b/",
    "https://www.oddsportal.com/football/denmark/superliga/",
    "https://www.oddsportal.com/football/denmark/1st-division/",
    "https://www.oddsportal.com/football/denmark/2nd-division/",
    "https://www.oddsportal.com/football/denmark/landspokal-cup/",
    "https://www.oddsportal.com/football/dominican-republic/ldf/",
    "https://www.oddsportal.com/football/ecuador/liga-pro/",
    "https://www.oddsportal.com/football/ecuador/serie-b/",
    "https://www.oddsportal.com/football/egypt/premier-league/",
    "https://www.oddsportal.com/football/el-salvador/primera-division/",
    "https://www.oddsportal.com/football/england/championship/",
    "https://www.oddsportal.com/football/england/league-one/",
    "https://www.oddsportal.com/football/england/league-two/",
    "https://www.oddsportal.com/football/england/fa-cup/",
    "https://www.oddsportal.com/football/england/fa-trophy/",
    "https://www.oddsportal.com/football/england/professional-development-league/",
    "https://www.oddsportal.com/football/england/wsl/",
    "https://www.oddsportal.com/football/estonia/meistriliiga/",
    "https://www.oddsportal.com/football/estonia/esiliiga/",
    "https://www.oddsportal.com/football/ethiopia/premier-league/",
    "https://www.oddsportal.com/football/europe/conference-league/",
    "https://www.oddsportal.com/football/europe/champions-league-women/",
    "https://www.oddsportal.com/football/finland/veikkausliiga/",
    "https://www.oddsportal.com/football/finland/ykkosliiga/",
    "https://www.oddsportal.com/football/france/national/",
    "https://www.oddsportal.com/football/france/coupe-de-france/",
    "https://www.oddsportal.com/football/georgia/crystalbet-erovnuli-liga/",
    "https://www.oddsportal.com/football/georgia/liga-3/",
    "https://www.oddsportal.com/football/germany/2-bundesliga/",
    "https://www.oddsportal.com/football/germany/3-liga/",
    "https://www.oddsportal.com/football/germany/oberliga-hamburg/",
    "https://www.oddsportal.com/football/germany/oberliga-niedersachsen/",
    "https://www.oddsportal.com/football/germany/oberliga-westfalen/",
    "https://www.oddsportal.com/football/germany/dfb-pokal/",
    "https://www.oddsportal.com/football/germany/bundesliga-women/",
    "https://www.oddsportal.com/football/greece/super-league/",
    "https://www.oddsportal.com/football/guatemala/liga-nacional/",
    "https://www.oddsportal.com/football/honduras/liga-nacional/",
    "https://www.oddsportal.com/football/hungary/nb-i/",
    "https://www.oddsportal.com/football/iceland/besta-deild-karla/",
    "https://www.oddsportal.com/football/iceland/besta-deild-women/",
    "https://www.oddsportal.com/football/india/isl/",
    "https://www.oddsportal.com/football/india/i-league/",
    "https://www.oddsportal.com/football/indonesia/super-league/",
    "https://www.oddsportal.com/football/iran/azadegan-league/",
    "https://www.oddsportal.com/football/iraq/stars-league/",
    "https://www.oddsportal.com/football/ireland/premier-division/",
    "https://www.oddsportal.com/football/ireland/division-1/",
    "https://www.oddsportal.com/football/israel/ligat-ha-al/",
    "https://www.oddsportal.com/football/israel/leumit-league/",
    "https://www.oddsportal.com/football/italy/serie-b/",
    "https://www.oddsportal.com/football/italy/serie-d-group-f/",
    "https://www.oddsportal.com/football/italy/coppa-italia/",
    "https://www.oddsportal.com/football/jamaica/premier-league/",
    "https://www.oddsportal.com/football/japan/j2-j3-league/",
    "https://www.oddsportal.com/football/kazakhstan/premier-league/",
    "https://www.oddsportal.com/football/kazakhstan/kazakhstan-cup/",
    "https://www.oddsportal.com/football/kuwait/premier-league/",
    "https://www.oddsportal.com/football/kyrgyzstan/premier-liga/",
    "https://www.oddsportal.com/football/latvia/virsliga/",
    "https://www.oddsportal.com/football/lithuania/toplyga/",
    "https://www.oddsportal.com/football/lithuania/i-lyga/",
    "https://www.oddsportal.com/football/malawi/super-league/",
    "https://www.oddsportal.com/football/mali/premiere-division/",
    "https://www.oddsportal.com/football/mexico/liga-de-expansion-mx/",
    "https://www.oddsportal.com/football/mexico/liga-mx-women/",
    "https://www.oddsportal.com/football/morocco/botola-pro/",
    "https://www.oddsportal.com/football/northern-ireland/nifl-premiership/",
    "https://www.oddsportal.com/football/norway/obos-ligaen/",
    "https://www.oddsportal.com/football/norway/division-3-group-1/",
    "https://www.oddsportal.com/football/norway/division-3-group-2/",
    "https://www.oddsportal.com/football/norway/division-3-group-3/",
    "https://www.oddsportal.com/football/norway/division-3-group-4/",
    "https://www.oddsportal.com/football/norway/division-3-group-6/",
    "https://www.oddsportal.com/football/norway/norway-cup-women/",
    "https://www.oddsportal.com/football/panama/lpf/",
    "https://www.oddsportal.com/football/paraguay/copa-de-primera/",
    "https://www.oddsportal.com/football/paraguay/division-intermedia/",
    "https://www.oddsportal.com/football/peru/liga-1/",
    "https://www.oddsportal.com/football/peru/liga-2/",
    "https://www.oddsportal.com/football/poland/division-1/",
    "https://www.oddsportal.com/football/poland/division-2/",
    "https://www.oddsportal.com/football/poland/iii-liga-group-i/",
    "https://www.oddsportal.com/football/poland/iii-liga-group-iii/",
    "https://www.oddsportal.com/football/poland/iii-liga-group-iv/",
    "https://www.oddsportal.com/football/poland/ekstraliga-women/",
    "https://www.oddsportal.com/football/poland/polish-cup-women/",
    "https://www.oddsportal.com/football/portugal/liga-portugal-2/",
    "https://www.oddsportal.com/football/portugal/taca-de-portugal/",
    "https://www.oddsportal.com/football/portugal/taca-revelacao-u23/",
    "https://www.oddsportal.com/football/romania/superliga/",
    "https://www.oddsportal.com/football/romania/liga-2/",
    "https://www.oddsportal.com/football/romania/romanian-cup/",
    "https://www.oddsportal.com/football/russia/premier-league/",
    "https://www.oddsportal.com/football/russia/fnl/",
    "https://www.oddsportal.com/football/russia/fnl-2-division-b-group-2/",
    "https://www.oddsportal.com/football/russia/fnl-2-division-b-group-3/",
    "https://www.oddsportal.com/football/russia/russian-cup/",
    "https://www.oddsportal.com/football/saudi-arabia/saudi-professional-league/",
    "https://www.oddsportal.com/football/scotland/championship/",
    "https://www.oddsportal.com/football/scotland/league-one/",
    "https://www.oddsportal.com/football/scotland/league-two/",
    "https://www.oddsportal.com/football/scotland/scottish-cup/",
    "https://www.oddsportal.com/football/serbia/mozzart-bet-prva-liga/",
    "https://www.oddsportal.com/football/serbia/mozzart-serbian-cup/",
    "https://www.oddsportal.com/football/singapore/premier-league/",
    "https://www.oddsportal.com/football/slovakia/nike-liga/",
    "https://www.oddsportal.com/football/slovakia/2-liga/",
    "https://www.oddsportal.com/football/slovenia/prva-liga/",
    "https://www.oddsportal.com/football/slovenia/2-snl/",
    "https://www.oddsportal.com/football/south-africa/betway-premiership/",
    "https://www.oddsportal.com/football/south-america/copa-libertadores/",
    "https://www.oddsportal.com/football/south-america/copa-sudamericana/",
    "https://www.oddsportal.com/football/south-korea/k-league-1/",
    "https://www.oddsportal.com/football/south-korea/k-league-2/",
    "https://www.oddsportal.com/football/spain/laliga2/",
    "https://www.oddsportal.com/football/spain/liga-f-women/",
    "https://www.oddsportal.com/football/suriname/sml/",
    "https://www.oddsportal.com/football/sweden/superettan/",
    "https://www.oddsportal.com/football/sweden/division-1-norra/",
    "https://www.oddsportal.com/football/sweden/division-1-sodra/",
    "https://www.oddsportal.com/football/sweden/division-2-sodra-gotaland/",
    "https://www.oddsportal.com/football/sweden/division-2-vastra-gotaland/",
    "https://www.oddsportal.com/football/sweden/svenska-cupen/",
    "https://www.oddsportal.com/football/sweden/allsvenskan-women/",
    "https://www.oddsportal.com/football/switzerland/challenge-league/",
    "https://www.oddsportal.com/football/taiwan/mulan-football-league-women/",
    "https://www.oddsportal.com/football/tunisia/ligue-2/",
    "https://www.oddsportal.com/football/turkey/1-lig/",
    "https://www.oddsportal.com/football/turkey/turkish-cup/",
    "https://www.oddsportal.com/football/ukraine/premier-league/",
    "https://www.oddsportal.com/football/united-arab-emirates/uae-league/",
    "https://www.oddsportal.com/football/united-arab-emirates/pro-league-u23/",
    "https://www.oddsportal.com/football/uruguay/liga-auf-uruguaya/",
    "https://www.oddsportal.com/football/usa/mls-next-pro/",
    "https://www.oddsportal.com/football/usa/usl-league-one/",
    "https://www.oddsportal.com/football/usa/usl-league-two/",
    "https://www.oddsportal.com/football/usa/nwsl-women/",
    "https://www.oddsportal.com/football/world/friendly-international/",
    "https://www.oddsportal.com/football/zambia/super-league/",
]

class OddsPortalFinder(BaseMatchFinder):
    def __init__(self, add_match_callback, **runtime_settings) -> None:
        super().__init__(add_match_callback, **runtime_settings)
        self._add_match_lock = threading.Lock()

    def get_matches_urls(self):
        urls = []

        for url in TOP_LEAGUES if self.top_leagues_only else ALL_LINKS:
            try:
                html = fetch(url)
                soup = BeautifulSoup(html, "html.parser")

                today = datetime.now(timezone.utc).date()
                max_date = today + timedelta(days=self.num_days_ahead)

                links = list(dict.fromkeys([
                    event['url']
                    for script in soup.find_all('script', type='application/ld+json')
                    for data in [json.loads(script.string)]
                    for event in (data if isinstance(data, list) else [data])
                    if isinstance(event, dict)
                    and event.get('url')
                    and event.get('startDate')
                    and (
                        event.get('eventStatus') == 'Scheduled'
                        or (
                            isinstance(event.get('eventStatus'), dict)
                            and event['eventStatus'].get('@type') == 'EventStatusType'
                            and event['eventStatus'].get('@id') == 'https://schema.org/EventScheduled'
                        )
                    )
                    and today <= datetime.fromisoformat(event['startDate'].replace('Z', '+00:00')).date() <= max_date
                ]))

                urls.extend(links)
                logger.info("Found %d match URLs on %s (total: %d)", len(links), url, len(urls))
            except Exception as e:
                logger.error("Failed to scrape %s: %s", url, e)
                continue

        logger.info("Total URLs found: %d", len(urls))
        return list(set(urls))

    def _process_url_batch(self, urls: list) -> None:
        thread_name = threading.current_thread().name
        logger.info("[%s] Starting batch of %d URLs", thread_name, len(urls))

        with browser(solve_cloudflare=True, interactive=True, disable_resources=False, headless=True) as session:
            for url in urls:
                try:
                    try:
                        session.fetch(url, wait_until="domcontentloaded", timeout=90000)
                    except Exception as e:
                        logger.warning("[%s] Fetch error (retrying): %s", thread_name, e)
                        time.sleep(4)
                        with contextlib.suppress(Exception):
                            session.fetch(url, wait_until="domcontentloaded", timeout=60000)

                    soup = BeautifulSoup(session.page.content(), "html.parser")

                    home_team = soup.select_one('[data-testid="game-host"] a').text.strip()
                    away_team = soup.select_one('[data-testid="game-guest"] a').text.strip()
                    match_date = datetime.strptime(
                        soup.select_one('[data-testid="game-time-item"] p:nth-of-type(2)').text.strip().rstrip(","), "%d %B %Y"
                    ).replace(hour=0, minute=0, second=0)

                    odds_1, odds_X, odds_2 = None, None, None
                    odds_btts_y, odds_btts_n = None, None
                    odds_dc_1x, odds_dc_12, odds_dc_x2 = None, None, None
                    odds_over05, odds_under05 = None, None
                    odds_over15, odds_under15 = None, None
                    odds_over25, odds_under25 = None, None
                    odds_over35, odds_under35 = None, None
                    odds_over45, odds_under45 = None, None

                    try:
                        logger.info("[%s] Extracting 1X2 odds", thread_name)
                        assert session.click("li.odds-item", "1X2"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        cells = soup.find("div", {"data-testid": "over-under-expanded-row"}).find_all(
                            "div", {"data-testid": "odd-container"}
                        )
                        odds_1 = cells[0].find("a", class_="odds-link").get_text(strip=True)
                        odds_X = cells[1].find("a", class_="odds-link").get_text(strip=True)
                        odds_2 = cells[2].find("a", class_="odds-link").get_text(strip=True)
                        odds_1 = odds_1 if odds_1 != "-" else None
                        odds_X = odds_X if odds_X != "-" else None
                        odds_2 = odds_2 if odds_2 != "-" else None
                    except Exception:
                        logger.warning("[%s] Failed to scrape 1X2 odds", thread_name)

                    try:
                        logger.info("[%s] Extracting BTTS odds", thread_name)
                        assert session.click("li.odds-item", "Both Teams to Score"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        cells = soup.find("div", {"data-testid": "over-under-expanded-row"}).find_all(
                            "div", {"data-testid": "odd-container"}
                        )
                        odds_btts_y = cells[0].find("a", class_="odds-link").get_text(strip=True)
                        odds_btts_n = cells[1].find("a", class_="odds-link").get_text(strip=True)
                        odds_btts_y = odds_btts_y if odds_btts_y != "-" else None
                        odds_btts_n = odds_btts_n if odds_btts_n != "-" else None
                    except Exception:
                        logger.warning("[%s] Failed to scrape BTTS odds", thread_name)

                    try:
                        logger.info("[%s] Extracting DC odds", thread_name)
                        assert session.click("li.odds-item", "Double Chance"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        cells = soup.find("div", {"data-testid": "over-under-expanded-row"}).find_all(
                            "div", {"data-testid": "odd-container"}
                        )
                        odds_dc_1x = cells[0].find("a", class_="odds-link").get_text(strip=True)
                        odds_dc_12 = cells[1].find("a", class_="odds-link").get_text(strip=True)
                        odds_dc_x2 = cells[2].find("a", class_="odds-link").get_text(strip=True)
                        odds_dc_1x = odds_dc_1x if odds_dc_1x != "-" else None
                        odds_dc_12 = odds_dc_12 if odds_dc_12 != "-" else None
                        odds_dc_x2 = odds_dc_x2 if odds_dc_x2 != "-" else None
                    except Exception:
                        logger.warning("[%s] Failed to scrape DC odds", thread_name)

                    try:
                        logger.info("[%s] Extracting O/U odds", thread_name)
                        assert session.click("li.odds-item", "Over/Under"), "Click failed"
                        soup = BeautifulSoup(session.page.content(), "html.parser")
                        for row in soup.find_all("div", {"data-testid": "over-under-collapsed-row"}):
                            name = row.find("div", {"data-testid": "over-under-collapsed-option-box"}).get_text(strip=True)
                            conts = row.find_all("div", {"data-testid": "odd-container-default"})
                            over = conts[0].find("p").get_text(strip=True)
                            under = conts[1].find("p").get_text(strip=True)
                            if "+0.5" in name:
                                odds_over05 = over if over != "-" else None
                                odds_under05 = under if under != "-" else None
                            if "+1.5" in name:
                                odds_over15 = over if over != "-" else None
                                odds_under15 = under if under != "-" else None
                            if "+2.5" in name:
                                odds_over25 = over if over != "-" else None
                                odds_under25 = under if under != "-" else None
                            if "+3.5" in name:
                                odds_over35 = over if over != "-" else None
                                odds_under35 = under if under != "-" else None
                            if "+4.5" in name:
                                odds_over45 = over if over != "-" else None
                                odds_under45 = under if under != "-" else None
                    except Exception:
                        logger.warning("[%s] Failed to scrape O/U odds", thread_name)

                    odds = Odds(
                        home=odds_1,
                        draw=odds_X,
                        away=odds_2,
                        over_05=odds_over05,
                        under_05=odds_under05,
                        over_15=odds_over15,
                        under_15=odds_under15,
                        over_25=odds_over25,
                        under_25=odds_under25,
                        over_35=odds_over35,
                        under_35=odds_under35,
                        over_45=odds_over45,
                        under_45=odds_under45,
                        btts_y=odds_btts_y,
                        btts_n=odds_btts_n,
                        dc_1x=odds_dc_1x,
                        dc_12=odds_dc_12,
                        dc_x2=odds_dc_x2,
                    )

                    logger.info("[%s] %s", thread_name, odds)

                    with self._add_match_lock:
                        self.add_match(
                            Match(home_team=home_team, away_team=away_team, datetime=match_date, predictions=None, odds=odds)
                        )

                except Exception as e:
                    logger.error("[%s] Error parsing %s: %s", thread_name, url, e)
                    continue

        logger.info("[%s] Batch complete", thread_name)

    def get_matches(self, urls) -> None:
        if not urls:
            return

        if MAX_CONCURRENCY <= 1:
            self._process_url_batch(urls)
            return

        chunk_size = max(1, len(urls) // MAX_CONCURRENCY)
        chunks = [urls[i : i + chunk_size] for i in range(0, len(urls), chunk_size)]
        while len(chunks) > MAX_CONCURRENCY:
            chunks[-2].extend(chunks[-1])
            chunks.pop()

        logger.info(
            "Parallelizing %d URLs across %d workers (chunks: %s)",
            len(urls),
            len(chunks),
            [len(c) for c in chunks],
        )

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="oddsportal") as executor:
            futures = {executor.submit(self._process_url_batch, chunk): i for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                chunk_idx = futures[future]
                try:
                    future.result()
                    logger.info("Worker %d finished successfully", chunk_idx)
                except Exception as e:
                    logger.error("Worker %d raised an exception: %s", chunk_idx, e)
