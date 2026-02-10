import asyncio
import os
import random
import re
import threading
import time
from datetime import datetime

from bs4 import BeautifulSoup

from bet_crawler.BaseMatchFinder import BaseMatchFinder
from bet_framework.core.Match import *
from bet_framework.WebScraper import WebScraper

SOCCERVISTA_URL = "https://www.soccervista.com"
SOCCERVISTA_NAME = "soccervista"
NUM_THREADS = os.cpu_count()

EXCLUDED = [
    "premier-league-u18", "efl-cup", "fa-community-shield", "fa-cup",
    "fa-trophy", "efl-trophy", "women-s-fa-cup", "fa-youth-cup",
    "women-s-league-cup", "wsl", "wsl-2", "premier-league-cup",
    "women-s-national-league-north", "women-s-national-league-south",
    "national-league-cup", "copa-del-rey", "super-cup", "liga-f-women",
    "copa-federacion", "copa-de-la-reina-women", "super-cup-women",
    "primera-federacion-women", "bundesliga-women", "dfb-pokal",
    "dfb-pokal-women", "super-cup", "dfb-junioren-pokal",
    "2-bundesliga-women", "super-cup-women", "dfb-youth-league",
    "coppa-italia", "super-cup", "super-cup-serie-c", "coppa-italia-serie-c",
    "coppa-italia-primavera", "supercoppa-primavera", "serie-a-women",
    "coppa-italia-serie-d", "serie-b-women", "coppa-italia-women",
    "super-cup-women", "serie-a-cup-women", "coupe-de-france", "super-cup",
    "premiere-ligue-women", "coupe-de-france-women", "super-cup-women",
    "seconde-ligue-women", "coupe-de-la-ligue-women", "champions-league",
    "champions-league-women", "emirates-cup", "euro", "euro-women",
    "europa-league", "euro-u17", "euro-u19", "euro-u21", "uefa-super-cup",
    "world-cup", "baltic-cup", "baltic-cup-u21", "euro-u19-women",
    "euro-u17-women", "atlantic-cup", "uefa-youth-league",
    "premier-league-international-cup", "uefa-regions-cup", "elite-league-u20",
    "uefa-nations-league", "conference-league", "tipsport-malta-cup",
    "uefa-nations-league-women", "all-island-cup-women",
    "uefa-europa-cup-women", "africa-cup-of-nations", "caf-champions-league",
    "caf-confederation-cup", "caf-super-cup", "africa-cup-of-nations-u20",
    "africa-cup-of-nations-u17", "africa-cup-of-nations-women",
    "african-nations-championship", "cecafa-kagame-cup", "cosafa-cup",
    "cosafa-championship-u20", "cosafa-cup-women", "cecafa-championship-women",
    "caf-champions-league-women", "cecafa-championship-u20", "albanian-cup",
    "super-cup", "algeria-cup", "super-cup", "u21-league", "super-cup",
    "andorra-cup", "super-cup", "torneos-de-verano", "copa-argentina",
    "super-cup", "trofeo-de-campeones", "copa-de-la-liga-profesional",
    "primera-a-women", "reserve-league", "international-super-cup",
    "armenian-cup", "super-cup", "afc-champions-league", "asian-cup",
    "eaff-e-1-football-championship", "eaff-e-1-football-championship-women",
    "arabian-gulf-cup", "asean-championship", "asian-cup-women",
    "afc-championship-women-u16", "asean-championship-women", "merdeka-cup",
    "guangdong-hong-kong-cup", "gulf-club-champions-league",
    "asean-championship-u19", "afc-asian-cup-u23", "southeast-asian-games",
    "asean-championship-u23", "saff-championship-women",
    "southeast-asian-games-women", "afc-asian-cup-u17", "afc-asian-cup-u20",
    "waff-championship-women", "cafa-nations-cup", "afc-champions-league-2",
    "afc-asian-cup-women-u20", "waff-championship-u23", "super-cup-uae-qatar",
    "afc-asian-cup-women-u17", "afc-challenge-league",
    "afc-champions-league-women", "saff-championship-u19",
    "waff-championship-u19", "asean-club-championship", "a-league-women",
    "y-league", "australia-cup", "australian-championship",
    "ofc-champions-league", "ofc-nations-cup", "ofc-nations-cup-women",
    "ofc-championship-u16", "ofc-championship-u19",
    "ofc-championship-u19-women", "ofc-championship-u16-women", "ofb-cup",
    "bundesliga-women", "ofb-cup-women", "azerbaijan-cup", "bahrain-cup",
    "king-s-cup", "super-cup", "belarusian-cup", "super-cup",
    "vysshaya-liga-women", "belgian-cup", "super-cup", "1st-national-women",
    "belgian-cup-women", "super-league-women", "pro-league-u21", "copa-pacena",
    "torneo-amistoso-de-verano", "bosnia-and-herzegovina-cup", "super-cup",
    "copa-betano-do-brasil", "copinha", "brasileiro-u20", "copa-do-nordeste",
    "copa-verde", "copa-do-brasil-u20", "brasileiro-women",
    "supercopa-do-brasil", "brasileiro-a2-women", "brasileiro-u23",
    "copa-paulista", "copa-rio", "copa-santa-catarina", "brasileiro-a3-women",
    "acreano-women", "acreano-u20", "alagoano-women", "alagoano-u20",
    "copa-alagoas", "amazonense-women", "amazonense-u20", "baiano-women",
    "baiano-u20", "brasiliense-women", "brasiliense-u20", "carioca-women",
    "carioca-u20", "catarinense-women", "catarinense-u20", "cearense-women",
    "cearense-u20", "sergipano-women", "copa-fares-lopes", "goiano-women",
    "gaucho-women", "gaucho-u20", "goiano-u20", "copa-fgf", "sergipano-u20",
    "mineiro-women", "maranhense-women", "mineiro-u20", "paraibano-u20",
    "paraibano-women", "matogrossense-women", "matogrossense-u20",
    "paranaense-women", "copa-fmf-mato-grosso", "paranaense-u20",
    "paraense-women", "paraense-u20", "sul-matogrossense-women",
    "sul-matogrossense-u20", "piauiense-women", "pernambucano-women",
    "pernambucano-u20", "rondoniense-women", "piauiense-u20",
    "rondoniense-u20", "paulista-women", "potiguar-women", "potiguar-u20",
    "paulista-u20", "copa-espirito-santo", "supercopa-do-brasil-women",
    "copa-rio-women", "copa-rio-u20", "capixaba-u20", "copa-grao-para",
    "tocantinense-u20", "capixaba-women", "brasileiro-u17",
    "copa-paulista-women", "copinha-women", "copa-do-brasil-u17",
    "brasileiro-u20-b", "copa-do-brasil-women", "kings-cup", "bulgarian-cup",
    "super-cup", "coupe-du-president", "super-coupe", "hun-sen-cup",
    "super-cup", "super-cup", "u-sports", "copa-chile", "super-cup",
    "primera-division-women", "super-league-women", "fa-cup", "super-cup",
    "copa-colombia", "super-cup", "liga-women", "super-cup",
    "copa-costa-rica", "recopa-de-costa-rica", "croatian-cup", "super-cup",
    "1-hnl-women", "cyprus-cup", "super-cup", "mol-cup", "tipsport-liga",
    "1-liga-women", "u19-league", "czech-cup-women", "2-liga-women",
    "op-iv-tridy-ji", "op-iv-tridy-pe", "op-iii-tridy-ov", "op-iv-tridy-zr",
    "op-iv-tridy-pu-group-a", "op-iv-tridy-pu-group-b", "op-iv-tridy-bi",
    "op-iv-tridy-vy-group-a", "op-iv-tridy-vy-group-b", "op-iv-tridy-zn-group-a",
    "op-iv-tridy-zn-group-b", "op-iv-tridy-zn-group-c", "op-iv-tridy-zl-group-a",
    "op-iv-tridy-zl-group-b", "op-iv-tridy-nj", "op-iii-tridy-pj-group-b",
    "op-iii-tridy-vs-group-b", "op-iii-tridy-hk-group-b", "op-iii-tridy-cr-group-b",
    "op-iii-tridy-tp-group-a", "op-iii-tridy-bk-group-b", "op-iii-tridy-ln-group-b",
    "op-iii-tridy-me-group-b", "op-iii-tridy-do-group-b", "op-iii-tridy-tp-group-b",
    "op-iv-tridy-su", "landspokal-cup", "a-liga-women", "danish-cup-women",
    "b-liga-women", "copa-de-la-ldf", "copa-ecuador", "super-cup", "egypt-cup",
    "super-cup", "league-cup", "estonian-cup", "super-cup", "meistriliiga-women",
    "ingwenyama-cup", "faroe-islands-cup", "super-cup", "champion-vs-champion",
    "liiga-cup", "suomen-cup", "kansallinen-liiga-women", "suomen-cup-women",
    "ykkosliigacup", "kansallinen-ykkonen-women", "ff-cup", "georgian-cup",
    "super-cup", "ghanaian-cup", "super-cup-div-one", "super-cup",
    "gibraltar-cup", "super-cup", "greek-cup", "super-cup", "division-a-women",
    "senior-shield", "fa-cup", "sapling-cup", "league-cup", "hungarian-cup",
    "nb-i-women", "hungarian-cup-women", "icelandic-cup", "league-cup",
    "super-cup", "besta-deild-women", "icelandic-cup-women", "super-cup-women",
    "league-cup-women", "super-cup", "santosh-trophy", "durand-cup",
    "iwl-women", "ifa-shield", "president-cup", "hazfi-cup", "super-cup",
    "iraq-cup", "fai-cup", "super-cup", "national-league-women",
    "fai-cup-women", "super-cup-women", "state-cup", "toto-cup", "super-cup",
    "emperors-cup", "ybc-levain-cup", "super-cup", "nadeshiko-league-women",
    "empress-s-cup-women", "we-league-women", "we-league-cup-women",
    "jordan-cup", "super-cup", "shield-cup", "kazakhstan-cup", "super-cup",
    "league-cup", "league-women", "fkf-mozzart-bet-cup", "super-cup",
    "super-cup", "kosovar-cup", "crown-prince-cup", "emir-cup", "super-cup",
    "latvian-cup", "super-cup", "1-liga-women", "super-cup-women",
    "lebanese-cup", "super-cup", "federation-cup", "orange-cup",
    "liechtenstein-cup", "lithuanian-cup", "super-cup", "luxembourg-cup",
    "castel-challenge-cup", "fam-charity-shield", "malaysia-cup", "fa-cup",
    "piala-sumbangsih", "mfl-challenge-cup", "fa-trophy", "super-cup",
    "challenge-cup", "copa-mexico", "campeon-de-campeones", "liga-mx-women",
    "copa-por-mexico", "liga-mx-u21", "moldovan-cup", "super-cup",
    "montenegrin-cup", "excellence-cup", "super-cup", "mnl-league-cup",
    "maris-cup", "knvb-beker", "johan-cruyff-shield", "eredivisie-women",
    "knvb-beker-women", "divisie-1-u19", "eredivisie-cup-women",
    "divisie-1-u21", "super-cup-women", "national-league-women", "chatham-cup",
    "kate-sheppard-cup-women", "liga-primera-u20", "copa-primera",
    "federation-cup", "concacaf-champions-cup", "gold-cup", "world-cup",
    "concacaf-championship-women", "concacaf-championship-u20",
    "concacaf-championship-u17", "concacaf-championship-women-u17",
    "concacaf-championship-women-u20", "concacaf-caribbean-cup",
    "concacaf-nations-league", "campeones-cup", "cfu-club-shield", "leagues-cup",
    "concacaf-central-american-cup", "gold-cup-women",
    "concacaf-champions-cup-women", "concacaf-series", "macedonian-cup",
    "1-wfl-women", "irish-cup", "irish-league-cup", "charity-shield",
    "premiership-women", "nm-cup", "toppserien-women", "super-cup",
    "norway-cup-women", "nasjonal-u19-cl", "division-1-women", "obos-supercup",
    "sultan-cup", "super-cup", "fa-cup", "copa-paraguay", "super-cup",
    "copa-peru", "copa-bicentenario", "supercopa-peruana", "liga-women",
    "copa-paulino-alcantara", "polish-cup", "super-cup", "central-youth-league",
    "ekstraliga-women", "polish-cup-women", "league-cup", "super-cup",
    "taca-de-portugal", "liga-revelacao-u23", "liga-bpi-women",
    "taca-de-portugal-women", "super-cup-women", "taca-da-liga-women",
    "taca-revelacao-u23", "campeonato-nacional-u19", "emir-cup", "qatar-cup",
    "qsl-cup", "qfa-cup", "romanian-cup", "super-cup", "superliga-women",
    "romanian-cup-women", "youth-league", "russian-cup", "super-cup",
    "russia-cup-women", "fnl-cup", "supreme-division-women", "super-cup-women",
    "super-cup", "peace-cup", "coppa-titano", "super-cup", "king-cup",
    "super-cup", "premier-league-women", "challenge-cup", "scottish-cup",
    "league-cup", "swpl-1-women", "swpl-cup-women", "scottish-cup-women",
    "mozzart-serbian-cup", "singapore-cup", "singapore-community-shield",
    "slovak-cup", "1-liga-women", "slovenian-cup", "1-sznl-women", "mtn-8-cup",
    "carling-knockout", "nedbank-cup", "diski-challenge", "copa-libertadores",
    "copa-sudamericana", "recopa-sudamericana", "south-american-championship-u20",
    "copa-america", "south-american-championship-u17", "copa-america-women",
    "south-american-championship-women-u20", "south-american-championship-women-u17",
    "copa-libertadores-women", "copa-libertadores-u20", "brasil-ladies-cup-women",
    "conmebol-nations-league-women", "korean-cup", "wk-league-women",
    "allsvenskan-women", "svenska-cupen", "svenska-cupen-women",
    "elitettan-women", "swiss-cup", "super-league-women", "1-liga-classic-cup",
    "swiss-cup-women", "syria-cup", "mulan-football-league-women", "super-cup",
    "tajikistan-cup", "community-shield", "federation-cup", "champions-cup",
    "thai-fa-cup", "league-cup", "super-cup", "tunisia-cup", "super-cup",
    "super-cup", "turkish-cup", "super-lig-women", "uganda-cup", "ukrainian-cup",
    "championship-women", "u19-league", "league-cup", "presidents-cup",
    "super-cup", "super-cup", "copa-uruguay", "us-open-cup",
    "carolina-challenge-cup", "nwsl-women", "nwsl-challenge-cup-women",
    "usl-cup", "usl-super-league-women", "uzbekistan-cup", "super-cup",
    "copa-venezuela", "super-cup", "vietnamese-cup", "super-cup",
    "national-league-women", "vietnamese-cup-women", "fa-cup", "league-cup",
    "premier-women", "fifa-club-world-cup", "kings-cup-thailand",
    "maurice-revello-tournament", "world-cup-u17", "world-cup-u20",
    "world-cup-women", "world-cup-women-u20", "trofeo-colombino",
    "world-cup-women-u17", "olympic-games", "olympic-games-women",
    "fifa-arab-cup", "viareggio-cup", "shebelieves-cup-women",
    "cotif-tournament", "finalissima", "intercontinental-cup-u20",
    "nwsl-x-liga-mx-women-summer-cup", "jezek-cup", "fifa-intercontinental-cup",
    "nextgen-cup", "premier-league-summer-series", "legends-charity-game",
    "fifa-women-s-champions-cup", "kings-world-cup-nations", "absa-cup",
    "super-cup", "chibuku-super-cup", "castle-challenge-cup"
]

class SoccerVistaFinder(BaseMatchFinder):
    def __init__(self, add_match_callback):
        super().__init__(add_match_callback)
        self._scanned_leagues = 0
        self._stop_logging = False
        self.web_scraper = None

    def _get_league_urls(self):
        try:
            self.get_web_scraper(profile='fast')
            html = self.web_scraper.fast_http_request(SOCCERVISTA_URL)
            soup = BeautifulSoup(html, 'html.parser')

            league_urls = []
            leagues_tag = soup.find('h3', string=lambda t: t and "Top Leagues" in t).parent
            all_links = [link['href'] for link in leagues_tag.find_all('a', href=True)][:-2]
            for link in all_links:
                html = self.web_scraper.fast_http_request(SOCCERVISTA_URL + link)
                soup = BeautifulSoup(html, 'html.parser')
                if html:
                    try:
                        league_urls += [link['value'] for link in soup.find('select',id="tournamentPage").find_all("option")]
                    except AttributeError:
                        print(f"Can't parse: {link}")
                        continue
            league_urls = [
                SOCCERVISTA_URL + url for url in league_urls
                if not any(excluded in url for excluded in EXCLUDED)
            ]

            print(str(len(league_urls)) + " leagues to scrape")

            return league_urls
        finally:
            self.web_scraper.destroy_current_thread()

    async def my_data_handler(self, url, html):
        self._scanned_leagues += 1
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # One-liner to find container, then rows, defaulting to [] if not found
            container = soup.find('h2', string=lambda t: t and "Upcoming Predictions" in t)
            matches_entries = container.parent.find("tbody").find_all("tr") if container else []
            for match_tr in matches_entries:
                home_team_name = match_tr.find_all("td")[1].find_all("span")[-1].get_text()
                away_team_name = match_tr.find_all("td")[3].find_all("span")[0].get_text()
                try:
                    date_str = match_tr.find_all("td")[0].get_text()
                    match_datetime = min(
                        (datetime.strptime(f"{date_str} {y}", "%d %b %Y") for y in [datetime.now().year-1, datetime.now().year, datetime.now().year+1]),
                        key=lambda d: abs(d - datetime.now())
                    )
                except Exception as e:
                    print(f"{home_team_name} vs {away_team_name}: Match ongoing")
                    continue

                scores = [Score(SOCCERVISTA_NAME, int(match_tr.find_all("td")[-1].get_text().split(":")[0]),
                                                    int(match_tr.find_all("td")[-1].get_text().split(":")[1]))]

                match_to_add = Match(
                    home_team=home_team_name,
                    away_team=away_team_name,
                    datetime=match_datetime,
                    predictions=scores,
                    odds=None
                )

                self.add_match(match_to_add)

        except Exception as e:
            print(f"Caught exception {e} while parsing {url}")

    def get_matches(self):
        """Main function to scrape all matches in parallel."""
        self._scanned_leagues = 0
        self._stop_logging = False

        # Get all match URLs
        leagues_urls = self._get_league_urls()
        self.get_web_scraper(profile='slow')
        asyncio.run(self.web_scraper.async_scrape(
            urls=leagues_urls,
            load_callback=self.my_data_handler,
            max_concurrent=12,
            additional_wait=1,
            wait_for_selector=".content-loaded"
        ))

        print(f"Finished scanning {self._scanned_leagues} leagues")

    def _log_progress(self, matches_urls):
        """Log scraping progress."""
        total = len(matches_urls)
        while not self._stop_logging:
            progress = (self._scanned_leagues / total * 100) if total > 0 else 0
            print(f"Progress: {self._scanned_leagues}/{total} ({progress:.1f}%)")
            time.sleep(2)
