"""Match finder for betexplorer.com odds pages."""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup
from scrape_kit import browser, fetch

from bet_crawler.crawler_logging import exception_event, get_logger, log_event
from bet_framework.core.Match import Match, Odds

from ._parallel import balanced_chunks
from .BaseMatchFinder import BaseMatchFinder

logger = get_logger(__name__)

BETEXPLORER_URL = ""
BETEXPLORER_NAME = "betexplorer"
MAX_CONCURRENCY = 10

TOP_LEAGUES = [
    "https://www.betexplorer.com/football/europe/champions-league/",
    "https://www.betexplorer.com/football/europe/europa-league/",
    "https://www.betexplorer.com/football/europe/conference-league/",
    "https://www.betexplorer.com/football/england/premier-league/",
    "https://www.betexplorer.com/football/italy/serie-a/",
    "https://www.betexplorer.com/football/spain/laliga/",
    "https://www.betexplorer.com/football/germany/bundesliga/",
    "https://www.betexplorer.com/football/france/ligue-1/",
    "https://www.betexplorer.com/football/belgium/jupiler-pro-league/",
    "https://www.betexplorer.com/football/england/championship/",
    "https://www.betexplorer.com/football/portugal/liga-portugal/",
    "https://www.betexplorer.com/football/brazil/serie-a-betano/",
    "https://www.betexplorer.com/football/usa/mls/",
    "https://www.betexplorer.com/football/netherlands/eredivisie/",
    "https://www.betexplorer.com/football/denmark/superliga/",
    "https://www.betexplorer.com/football/poland/ekstraklasa/",
    "https://www.betexplorer.com/football/argentina/liga-profesional/",
    "https://www.betexplorer.com/football/japan/j1-league/",
    "https://www.betexplorer.com/football/turkey/super-lig/",
    "https://www.betexplorer.com/football/sweden/allsvenskan/",
    "https://www.betexplorer.com/football/croatia/hnl/",
    "https://www.betexplorer.com/football/mexico/liga-mx/",
    "https://www.betexplorer.com/football/spain/laliga2/",
    "https://www.betexplorer.com/football/norway/eliteserien/",
    "https://www.betexplorer.com/football/austria/bundesliga/",
    "https://www.betexplorer.com/football/switzerland/super-league/",
    "https://www.betexplorer.com/football/italy/serie-b/",
    "https://www.betexplorer.com/football/germany/2-bundesliga/",
    "https://www.betexplorer.com/football/france/ligue-2/",
    "https://www.betexplorer.com/football/scotland/premiership/",
]

ALL_LINKS = [
    "https://www.betexplorer.com/football/albania/abissnet-superiore/",
    "https://www.betexplorer.com/football/albania/kategoria-e-pare/",
    "https://www.betexplorer.com/football/argentina/liga-profesional/",
    "https://www.betexplorer.com/football/argentina/primera-nacional/",
    "https://www.betexplorer.com/football/argentina/primera-b/",
    "https://www.betexplorer.com/football/argentina/primera-c/",
    "https://www.betexplorer.com/football/argentina/copa-argentina/",
    "https://www.betexplorer.com/football/argentina/reserve-league/",
    "https://www.betexplorer.com/football/argentina/primera-a-women/",
    "https://www.betexplorer.com/football/armenia/first-league/",
    "https://www.betexplorer.com/football/aruba/division-di-honor/",
    "https://www.betexplorer.com/football/asia/afc-champions-league-2/",
    "https://www.betexplorer.com/football/australia/a-league/",
    "https://www.betexplorer.com/football/australia/npl-act/",
    "https://www.betexplorer.com/football/australia/npl-northern-nsw/",
    "https://www.betexplorer.com/football/australia/npl-nsw/",
    "https://www.betexplorer.com/football/australia/npl-queensland/",
    "https://www.betexplorer.com/football/australia/npl-south-australia/",
    "https://www.betexplorer.com/football/australia/npl-victoria/",
    "https://www.betexplorer.com/football/australia/nsw-league-one/",
    "https://www.betexplorer.com/football/australia/queensland-premier-league/",
    "https://www.betexplorer.com/football/australia/sa-state-league/",
    "https://www.betexplorer.com/football/australia/victoria-premier-league/",
    "https://www.betexplorer.com/football/australia/victoria-premier-league-2/",
    "https://www.betexplorer.com/football/australia/a-league-women/",
    "https://www.betexplorer.com/football/australia-oceania/ofc-pro-league/",
    "https://www.betexplorer.com/football/austria/bundesliga/",
    "https://www.betexplorer.com/football/austria/2-liga/",
    "https://www.betexplorer.com/football/bahrain/premier-league/",
    "https://www.betexplorer.com/football/barbados/premier-league/",
    "https://www.betexplorer.com/football/belarus/vysshaya-liga/",
    "https://www.betexplorer.com/football/belarus/belarusian-cup/",
    "https://www.betexplorer.com/football/belgium/jupiler-pro-league/",
    "https://www.betexplorer.com/football/belgium/belgian-cup/",
    "https://www.betexplorer.com/football/belgium/pro-league-u21/",
    "https://www.betexplorer.com/football/bolivia/division-profesional/",
    "https://www.betexplorer.com/football/brazil/serie-a-betano/",
    "https://www.betexplorer.com/football/brazil/serie-b/",
    "https://www.betexplorer.com/football/brazil/serie-c/",
    "https://www.betexplorer.com/football/brazil/serie-d/",
    "https://www.betexplorer.com/football/brazil/catarinense-2/",
    "https://www.betexplorer.com/football/brazil/cearense-2/",
    "https://www.betexplorer.com/football/brazil/paranaense-2/",
    "https://www.betexplorer.com/football/brazil/paulista-a2/",
    "https://www.betexplorer.com/football/brazil/copa-betano-do-brasil/",
    "https://www.betexplorer.com/football/brazil/brasileiro-u20/",
    "https://www.betexplorer.com/football/brazil/kings-league-brazil/",
    "https://www.betexplorer.com/football/brazil/brasileiro-women/",
    "https://www.betexplorer.com/football/bulgaria/efbet-league/",
    "https://www.betexplorer.com/football/bulgaria/vtora-liga/",
    "https://www.betexplorer.com/football/cameroon/elite-two/",
    "https://www.betexplorer.com/football/canada/canadian-premier-league/",
    "https://www.betexplorer.com/football/canada/championship/",
    "https://www.betexplorer.com/football/chile/liga-de-primera/",
    "https://www.betexplorer.com/football/chile/liga-de-ascenso/",
    "https://www.betexplorer.com/football/chile/segunda-division/",
    "https://www.betexplorer.com/football/chile/copa-de-la-liga/",
    "https://www.betexplorer.com/football/china/super-league/",
    "https://www.betexplorer.com/football/colombia/primera-a/",
    "https://www.betexplorer.com/football/colombia/primera-b/",
    "https://www.betexplorer.com/football/colombia/copa-colombia/",
    "https://www.betexplorer.com/football/colombia/liga-women/",
    "https://www.betexplorer.com/football/costa-rica/primera-division/",
    "https://www.betexplorer.com/football/costa-rica/liga-de-ascenso/",
    "https://www.betexplorer.com/football/croatia/hnl/",
    "https://www.betexplorer.com/football/croatia/croatian-cup/",
    "https://www.betexplorer.com/football/croatia/1-hnl-women/",
    "https://www.betexplorer.com/football/cyprus/cyprus-league/",
    "https://www.betexplorer.com/football/czech-republic/chance-liga/",
    "https://www.betexplorer.com/football/czech-republic/chnl/",
    "https://www.betexplorer.com/football/czech-republic/3-cfl-group-a/",
    "https://www.betexplorer.com/football/denmark/superliga/",
    "https://www.betexplorer.com/football/denmark/1st-division/",
    "https://www.betexplorer.com/football/denmark/2nd-division/",
    "https://www.betexplorer.com/football/denmark/landspokal-cup/",
    "https://www.betexplorer.com/football/dominican-republic/ldf/",
    "https://www.betexplorer.com/football/ecuador/liga-pro/",
    "https://www.betexplorer.com/football/ecuador/serie-b/",
    "https://www.betexplorer.com/football/egypt/premier-league/",
    "https://www.betexplorer.com/football/egypt/division-2-a/",
    "https://www.betexplorer.com/football/el-salvador/primera-division/",
    "https://www.betexplorer.com/football/england/premier-league/",
    "https://www.betexplorer.com/football/england/championship/",
    "https://www.betexplorer.com/football/england/league-one/",
    "https://www.betexplorer.com/football/england/league-two/",
    "https://www.betexplorer.com/football/england/fa-cup/",
    "https://www.betexplorer.com/football/england/fa-trophy/",
    "https://www.betexplorer.com/football/england/professional-development-league/",
    "https://www.betexplorer.com/football/england/wsl/",
    "https://www.betexplorer.com/football/estonia/meistriliiga/",
    "https://www.betexplorer.com/football/estonia/esiliiga/",
    "https://www.betexplorer.com/football/ethiopia/premier-league/",
    "https://www.betexplorer.com/football/finland/veikkausliiga/",
    "https://www.betexplorer.com/football/finland/ykkosliiga/",
    "https://www.betexplorer.com/football/france/ligue-1/",
    "https://www.betexplorer.com/football/france/national/",
    "https://www.betexplorer.com/football/france/premiere-ligue-women/",
    "https://www.betexplorer.com/football/gambia/gfa-league/",
    "https://www.betexplorer.com/football/georgia/crystalbet-erovnuli-liga/",
    "https://www.betexplorer.com/football/germany/bundesliga/",
    "https://www.betexplorer.com/football/germany/2-bundesliga/",
    "https://www.betexplorer.com/football/germany/3-liga/",
    "https://www.betexplorer.com/football/germany/oberliga-hamburg/",
    "https://www.betexplorer.com/football/germany/oberliga-niedersachsen/",
    "https://www.betexplorer.com/football/germany/bundesliga-women/",
    "https://www.betexplorer.com/football/greece/super-league/",
    "https://www.betexplorer.com/football/guatemala/liga-nacional/",
    "https://www.betexplorer.com/football/honduras/liga-nacional/",
    "https://www.betexplorer.com/football/hungary/nb-i/",
    "https://www.betexplorer.com/football/iceland/besta-deild-karla/",
    "https://www.betexplorer.com/football/iceland/besta-deild-women/",
    "https://www.betexplorer.com/football/india/isl/",
    "https://www.betexplorer.com/football/india/i-league/",
    "https://www.betexplorer.com/football/indonesia/super-league/",
    "https://www.betexplorer.com/football/iran/azadegan-league/",
    "https://www.betexplorer.com/football/iraq/stars-league/",
    "https://www.betexplorer.com/football/ireland/premier-division/",
    "https://www.betexplorer.com/football/ireland/division-1/",
    "https://www.betexplorer.com/football/israel/ligat-ha-al/",
    "https://www.betexplorer.com/football/israel/leumit-league/",
    "https://www.betexplorer.com/football/italy/serie-a/",
    "https://www.betexplorer.com/football/italy/serie-b/",
    "https://www.betexplorer.com/football/italy/serie-d-group-c/",
    "https://www.betexplorer.com/football/italy/serie-d-group-f/",
    "https://www.betexplorer.com/football/italy/coppa-italia/",
    "https://www.betexplorer.com/football/jamaica/premier-league/",
    "https://www.betexplorer.com/football/japan/j1-league/",
    "https://www.betexplorer.com/football/japan/j2-j3-league/",
    "https://www.betexplorer.com/football/japan/nadeshiko-league-women/",
    "https://www.betexplorer.com/football/kazakhstan/kazakhstan-cup/",
    "https://www.betexplorer.com/football/kuwait/premier-league/",
    "https://www.betexplorer.com/football/kyrgyzstan/premier-liga/",
    "https://www.betexplorer.com/football/latvia/virsliga/",
    "https://www.betexplorer.com/football/lithuania/toplyga/",
    "https://www.betexplorer.com/football/lithuania/i-lyga/",
    "https://www.betexplorer.com/football/malawi/super-league/",
    "https://www.betexplorer.com/football/malaysia/super-league/",
    "https://www.betexplorer.com/football/mauritania/ligue-1/",
    "https://www.betexplorer.com/football/mexico/liga-mx/",
    "https://www.betexplorer.com/football/mexico/liga-de-expansion-mx/",
    "https://www.betexplorer.com/football/mexico/liga-mx-women/",
    "https://www.betexplorer.com/football/morocco/botola-pro/",
    "https://www.betexplorer.com/football/netherlands/eredivisie/",
    "https://www.betexplorer.com/football/niger/super-ligue/",
    "https://www.betexplorer.com/football/northern-ireland/nifl-premiership/",
    "https://www.betexplorer.com/football/norway/eliteserien/",
    "https://www.betexplorer.com/football/norway/obos-ligaen/",
    "https://www.betexplorer.com/football/norway/division-3-group-1/",
    "https://www.betexplorer.com/football/norway/division-3-group-2/",
    "https://www.betexplorer.com/football/norway/division-3-group-3/",
    "https://www.betexplorer.com/football/norway/division-3-group-4/",
    "https://www.betexplorer.com/football/norway/division-3-group-6/",
    "https://www.betexplorer.com/football/norway/toppserien-women/",
    "https://www.betexplorer.com/football/oman/professional-league/",
    "https://www.betexplorer.com/football/panama/lpf/",
    "https://www.betexplorer.com/football/paraguay/copa-de-primera/",
    "https://www.betexplorer.com/football/paraguay/division-intermedia/",
    "https://www.betexplorer.com/football/peru/liga-1/",
    "https://www.betexplorer.com/football/peru/liga-2/",
    "https://www.betexplorer.com/football/poland/ekstraklasa/",
    "https://www.betexplorer.com/football/poland/division-1/",
    "https://www.betexplorer.com/football/poland/division-2/",
    "https://www.betexplorer.com/football/poland/iii-liga-group-i/",
    "https://www.betexplorer.com/football/poland/iii-liga-group-ii/",
    "https://www.betexplorer.com/football/poland/iii-liga-group-iii/",
    "https://www.betexplorer.com/football/poland/iii-liga-group-iv/",
    "https://www.betexplorer.com/football/portugal/liga-portugal/",
    "https://www.betexplorer.com/football/portugal/liga-portugal-2/",
    "https://www.betexplorer.com/football/portugal/taca-revelacao-u23/",
    "https://www.betexplorer.com/football/romania/superliga/",
    "https://www.betexplorer.com/football/romania/liga-2/",
    "https://www.betexplorer.com/football/romania/romanian-cup/",
    "https://www.betexplorer.com/football/russia/premier-league/",
    "https://www.betexplorer.com/football/russia/fnl/",
    "https://www.betexplorer.com/football/russia/fnl-2-division-b-group-2/",
    "https://www.betexplorer.com/football/saudi-arabia/saudi-professional-league/",
    "https://www.betexplorer.com/football/scotland/premiership/",
    "https://www.betexplorer.com/football/scotland/championship/",
    "https://www.betexplorer.com/football/scotland/league-one/",
    "https://www.betexplorer.com/football/scotland/league-two/",
    "https://www.betexplorer.com/football/scotland/highland-league/",
    "https://www.betexplorer.com/football/scotland/lowland-league/",
    "https://www.betexplorer.com/football/senegal/ligue-1/",
    "https://www.betexplorer.com/football/serbia/mozzart-bet-prva-liga/",
    "https://www.betexplorer.com/football/serbia/mozzart-serbian-cup/",
    "https://www.betexplorer.com/football/singapore/premier-league/",
    "https://www.betexplorer.com/football/slovakia/nike-liga/",
    "https://www.betexplorer.com/football/slovenia/prva-liga/",
    "https://www.betexplorer.com/football/slovenia/2-snl/",
    "https://www.betexplorer.com/football/south-africa/betway-premiership/",
    "https://www.betexplorer.com/football/south-korea/k-league-1/",
    "https://www.betexplorer.com/football/south-korea/k-league-2/",
    "https://www.betexplorer.com/football/south-korea/k3-league/",
    "https://www.betexplorer.com/football/south-korea/wk-league-women/",
    "https://www.betexplorer.com/football/spain/laliga/",
    "https://www.betexplorer.com/football/spain/laliga2/",
    "https://www.betexplorer.com/football/spain/liga-f-women/",
    "https://www.betexplorer.com/football/suriname/sml/",
    "https://www.betexplorer.com/football/sweden/allsvenskan/",
    "https://www.betexplorer.com/football/sweden/superettan/",
    "https://www.betexplorer.com/football/sweden/division-1-norra/",
    "https://www.betexplorer.com/football/sweden/division-1-sodra/",
    "https://www.betexplorer.com/football/sweden/division-2-norra-gotaland/",
    "https://www.betexplorer.com/football/sweden/division-2-sodra-gotaland/",
    "https://www.betexplorer.com/football/sweden/division-2-vastra-gotaland/",
    "https://www.betexplorer.com/football/sweden/svenska-cupen/",
    "https://www.betexplorer.com/football/sweden/allsvenskan-women/",
    "https://www.betexplorer.com/football/switzerland/super-league/",
    "https://www.betexplorer.com/football/switzerland/challenge-league/",
    "https://www.betexplorer.com/football/tanzania/ligi-kuu-bara/",
    "https://www.betexplorer.com/football/tunisia/ligue-professionnelle-1/",
    "https://www.betexplorer.com/football/tunisia/ligue-2/",
    "https://www.betexplorer.com/football/turkey/super-lig/",
    "https://www.betexplorer.com/football/turkey/1-lig/",
    "https://www.betexplorer.com/football/turkey/turkish-cup/",
    "https://www.betexplorer.com/football/turkey/super-lig-women/",
    "https://www.betexplorer.com/football/ukraine/premier-league/",
    "https://www.betexplorer.com/football/ukraine/persha-liga/",
    "https://www.betexplorer.com/football/ukraine/u19-league/",
    "https://www.betexplorer.com/football/united-arab-emirates/uae-league/",
    "https://www.betexplorer.com/football/united-arab-emirates/pro-league-u23/",
    "https://www.betexplorer.com/football/uruguay/liga-auf-uruguaya/",
    "https://www.betexplorer.com/football/uruguay/segunda-division/",
    "https://www.betexplorer.com/football/usa/mls/",
    "https://www.betexplorer.com/football/usa/mls-next-pro/",
    "https://www.betexplorer.com/football/usa/usl-league-one/",
    "https://www.betexplorer.com/football/usa/usl-league-two/",
    "https://www.betexplorer.com/football/usa/nwsl-women/",
    "https://www.betexplorer.com/football/venezuela/liga-futve/",
    "https://www.betexplorer.com/football/venezuela/liga-futve-2/",
    "https://www.betexplorer.com/football/zambia/super-league/",
]


class BetExplorerFinder(BaseMatchFinder):
    """Finder for BetExplorer football match data and odds."""

    # TIMEZONE = BaseMatchFinder._detect_local_timezone()

    def __init__(self, add_match_callback, **runtime_settings) -> None:
        """Wire the finder contract for betexplorer (see BaseMatchFinder)."""
        super().__init__(add_match_callback, **runtime_settings)
        self._add_match_lock = threading.Lock()

    def get_matches_urls(self):
        """Return list of match URLs to scrape from BetExplorer."""
        urls = []

        for url in TOP_LEAGUES if self.top_leagues_only else ALL_LINKS:
            try:
                html = fetch(url)
                soup = BeautifulSoup(html, "html.parser")

                today = datetime.now(timezone.utc).date()
                max_date = today + timedelta(days=self.num_days_ahead)

                links = []
                for script in soup.find_all("script", type="application/ld+json"):
                    if not script.string:
                        continue
                    try:
                        data = json.loads(script.string)
                        # Normalize data to a list of candidates (handle list, @graph, or single object)
                        candidates = []
                        if isinstance(data, list):
                            candidates = data
                        elif isinstance(data, dict):
                            candidates = data.get("@graph", [data])

                        for event in candidates:
                            if not isinstance(event, dict):
                                log_event(
                                    logger,
                                    event="source.discovery.candidate_invalid",
                                    outcome="warning",
                                    reason_code="event_candidate_not_object",
                                    level=30,
                                    message=f"Ignoring non-object BetExplorer JSON-LD candidate on {url}",
                                    source_key="betexplorer",
                                    url=url,
                                )
                                continue

                            event_type = event.get("@type", [])
                            event_types = (
                                event_type
                                if isinstance(event_type, list)
                                else [event_type]
                            )
                            if event_types and "SportsEvent" not in event_types:
                                continue

                            match_url = event.get("url")
                            start_date_str = event.get("startDate")
                            if not match_url or not start_date_str:
                                log_event(
                                    logger,
                                    event="source.discovery.candidate_invalid",
                                    outcome="warning",
                                    reason_code="event_identity_missing",
                                    level=30,
                                    message="Ignoring BetExplorer SportsEvent without URL or startDate",
                                    source_key="betexplorer",
                                    url=match_url,
                                )
                                continue

                            # eventStatus: assume Scheduled if missing, otherwise check for 'Scheduled'
                            status = str(event.get("eventStatus", "Scheduled"))
                            if "Scheduled" not in status:
                                log_event(
                                    logger,
                                    event="source.discovery.candidate_skipped",
                                    outcome="info",
                                    reason_code="event_not_scheduled",
                                    level=20,
                                    message=f"Ignoring non-scheduled BetExplorer event ({status})",
                                    source_key="betexplorer",
                                    url=match_url,
                                )
                                continue
                            try:
                                match_date = datetime.fromisoformat(
                                    start_date_str.replace("Z", "+00:00")
                                ).date()
                            except (ValueError, TypeError, AttributeError) as exc:
                                log_event(
                                    logger,
                                    event="source.discovery.candidate_invalid",
                                    outcome="warning",
                                    reason_code="start_date_invalid",
                                    level=30,
                                    message=f"Ignoring BetExplorer event with invalid startDate {start_date_str!r}: {exc}",
                                    source_key="betexplorer",
                                    url=match_url,
                                    error_type=type(exc).__name__,
                                    error_message=str(exc),
                                )
                                continue
                            if today <= match_date <= max_date:
                                links.append(match_url)
                            else:
                                log_event(
                                    logger,
                                    event="source.discovery.candidate_skipped",
                                    outcome="info",
                                    reason_code="outside_date_window",
                                    level=20,
                                    message=f"Ignoring BetExplorer event outside date window ({match_date})",
                                    source_key="betexplorer",
                                    url=match_url,
                                )
                    except (json.JSONDecodeError, TypeError) as exc:
                        log_event(
                            logger,
                            event="source.discovery.candidate_invalid",
                            outcome="warning",
                            reason_code="invalid_json_ld",
                            level=30,
                            message=f"Ignoring malformed BetExplorer JSON-LD on {url}: {exc}",
                            source_key="betexplorer",
                            url=url,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                        continue

                links = list(dict.fromkeys(links))
                urls.extend(links)
                logger.info(
                    "Found %d match URLs on %s (total: %d)", len(links), url, len(urls)
                )
            except Exception as e:
                exception_event(
                    logger,
                    event="source.discovery.failed",
                    reason_code="league_fetch_failed",
                    message=f"Failed to discover BetExplorer match URLs from {url}: {e}",
                    source_key="betexplorer",
                    url=url,
                )
                continue

        logger.info("Total URLs found: %d", len(urls))
        return list(set(urls))

    _BROWSER_TIMEOUT_MS = 60_000
    _DECIMAL = re.compile(r"^\d+\.\d+$")

    def _configure_page_timeouts(self, session) -> None:
        """Make browser navigation and action defaults match the 60-second policy."""
        session.page.set_default_timeout(self._BROWSER_TIMEOUT_MS)
        session.page.set_default_navigation_timeout(self._BROWSER_TIMEOUT_MS)

    def _wait_for_selector(
        self, session, selector: str, *, state: str = "visible"
    ) -> None:
        """Wait for a DOM control/content node before reading or interacting with it."""
        session.page.wait_for_selector(
            selector, state=state, timeout=self._BROWSER_TIMEOUT_MS
        )

    def _wait_for_function(self, session, expression: str) -> None:
        """Wait up to one minute for the live page's DOM/data condition."""
        session.page.wait_for_function(expression, timeout=self._BROWSER_TIMEOUT_MS)

    def _click_selector(self, session, selector: str) -> bool:
        """Wait for a click target, then let its DOM-settle wait run for up to one minute."""
        self._wait_for_selector(session, selector)
        return session.click(selector, hard_cap_ms=self._BROWSER_TIMEOUT_MS)

    def _average_decimals(self, soup):
        """Decimal strings from oddsComparisonAll__average_text (skip CTA labels)."""
        return [
            d.get_text(strip=True)
            for d in soup.find_all("div", class_="oddsComparisonAll__average_text")
            if self._DECIMAL.match(d.get_text(strip=True))
        ]

    def _active_tab(self, soup):
        """Title of the active bet-type tab (live 2026-10-12: li.oddsComparison__activeLi)."""
        li = soup.select_one("#bettype_menu_best li.oddsComparison__activeLi")
        return li.get("title") if li else None

    def _click_market(self, session, selector, expected_n, allow_same: bool = False):
        """Click a BetExplorer market tab and wait until its averages render.

        Live 2026-10-12 Coventry–Newcastle: `#bettype_menu_best` click returns while
        averages still show 1X2 (3.19/3.58/2.20). BTTS becomes 1.57/2.34 and DC
        1.67/1.30/1.36 only after ~1.5s. Reading immediately copies 1 and X.
        """
        title = selector.split('title="', 1)[1].split('"', 1)[0]
        self._wait_for_selector(session, selector)
        before = self._average_decimals(
            BeautifulSoup(session.page.content(), "html.parser")
        )
        assert session.click(selector, hard_cap_ms=self._BROWSER_TIMEOUT_MS), (
            "Click failed"
        )
        condition = (
            "() => {"
            "const values = [...document.querySelectorAll('.oddsComparisonAll__average_text')]"
            ".map(e => e.textContent.trim()).filter(v => /^\\d+\\.\\d+$/.test(v));"
            f"const before = {json.dumps(before[:expected_n])};"
            f"const count = {expected_n};"
            "const changed = JSON.stringify(values.slice(0, count)) !== JSON.stringify(before);"
            "const active = document.querySelector('#bettype_menu_best li.oddsComparison__activeLi');"
            f"return values.length >= count && (changed || ({str(allow_same).lower()} && active?.getAttribute('title') === {json.dumps(title)}));"
            "}"
        )
        self._wait_for_function(session, condition)
        soup = BeautifulSoup(session.page.content(), "html.parser")
        avgs = self._average_decimals(soup)
        changed = avgs[:expected_n] != before[:expected_n]
        if len(avgs) >= expected_n and (
            changed or (allow_same and self._active_tab(soup) == title)
        ):
            return soup
        raise TimeoutError(f"{selector} averages did not settle")

    def _ou_handicap_odds(self, soup):
        """data-odd cells per half-line handicap (0.50..4.50); {} off the O/U view."""
        return {
            s.get("data-all-handicap"): [
                d
                for d in s.find_all("div", class_="oddsComparisonAll__average_text")
                if d.get("data-odd")
            ]
            for s in soup.find_all("div", {"data-all-handicap": True})
            if not s.get("data-all-handicap", "").startswith("handicap-")
        }

    def _wait_ou_handicaps(self, session):
        """Wait until all five half-line rows render (live 2026-10-12: ~1.5s after li#all)."""
        keys = ("0.50", "1.50", "2.50", "3.50", "4.50")
        condition = (
            '() => ["0.50", "1.50", "2.50", "3.50", "4.50"].every(key => {'
            'const row = document.querySelector(`[data-all-handicap="${key}"]`);'
            "return row && row.querySelectorAll('.oddsComparisonAll__average_text[data-odd]').length >= 2;"
            "})"
        )
        self._wait_for_function(session, condition)
        soup = BeautifulSoup(session.page.content(), "html.parser")
        c = self._ou_handicap_odds(soup)
        if all(len(c.get(k, [])) >= 2 for k in keys):
            return c
        raise TimeoutError("Over/Under handicaps did not settle")

    def _process_url_batch(self, urls: list) -> None:
        """Process a batch of URLs in a single browser session (runs in its own thread)."""
        thread_name = threading.current_thread().name
        logger.info("[%s] Starting batch of %d URLs", thread_name, len(urls))

        with browser(
            solve_cloudflare=True,
            interactive=True,
            disable_resources=False,
            headless=True,
        ) as session:
            self._configure_page_timeouts(session)
            for url in urls:
                try:
                    try:
                        session.fetch(
                            url,
                            wait_until="domcontentloaded",
                            timeout=self._BROWSER_TIMEOUT_MS,
                        )
                    except Exception as fetch_err:
                        log_event(
                            logger,
                            event="source.fetch.retry",
                            outcome="warning",
                            reason_code="fetch_retry",
                            level=30,
                            message=f"[{thread_name}] BetExplorer fetch retry for {url}: {fetch_err}",
                            source_key="betexplorer",
                            url=url,
                            attempt=1,
                            max_attempts=2,
                            error_type=type(fetch_err).__name__,
                            error_message=str(fetch_err),
                        )
                        session.fetch(
                            url,
                            wait_until="domcontentloaded",
                            timeout=self._BROWSER_TIMEOUT_MS,
                        )

                    try:
                        self._wait_for_selector(session, ".list-details__item__title")
                        self._wait_for_selector(session, "#match-date")
                    except Exception as exc:
                        log_event(
                            logger,
                            event="match.skipped",
                            outcome="error",
                            reason_code="critical_match_selectors_missing",
                            level=40,
                            message=f"[{thread_name}] Skipping BetExplorer match; critical team/date selectors missing: {url}",
                            source_key="betexplorer",
                            url=url,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                        continue

                    try:
                        self._wait_for_selector(session, "#bettype_menu_best")
                        logger.debug("[%s] Odds tab menu found", thread_name)
                    except Exception as exc:
                        log_event(
                            logger,
                            event="match.skipped",
                            outcome="warning",
                            reason_code="odds_tab_menu_missing",
                            level=30,
                            message=f"[{thread_name}] Skipping BetExplorer match; required odds tab menu missing: {url}",
                            source_key="betexplorer",
                            url=url,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                        continue

                    html = session.page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    home_team = soup.select_one(
                        ".list-details__item:nth-child(1) .list-details__item__title"
                    ).text.strip()
                    away_team = soup.select_one(
                        ".list-details__item:nth-child(3) .list-details__item__title"
                    ).text.strip()

                    date_str = soup.select_one("#match-date").text.strip()
                    date_part, time_part = date_str.split(" - ")
                    day, month, year = map(int, date_part.split("."))
                    hour, minute = map(int, time_part.split(":"))
                    match_date = datetime(year, month, day, hour, minute).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )

                    odds_1 = odds_X = odds_2 = odds_btts_yes = odds_btts_no = (
                        odds_dc_1x
                    ) = odds_dc_12 = odds_dc_x2 = None
                    odds_over05 = odds_under05 = odds_over15 = odds_under15 = (
                        odds_over25
                    ) = odds_under25 = odds_over35 = odds_under35 = odds_over45 = (
                        odds_under45
                    ) = None

                    try:
                        logger.info("[%s] Extracting 1x2 Odds", thread_name)
                        soup = self._click_market(
                            session,
                            '#bettype_menu_best li[title="1X2"]',
                            3,
                            allow_same=True,
                        )
                        avgs = self._average_decimals(soup)
                        odds_1, odds_X, odds_2 = avgs[0], avgs[1], avgs[2]
                    except Exception as e:
                        logger.warning(
                            "[%s] Failed to scrape 1X2 odds: %s", thread_name, e
                        )

                    try:
                        logger.info("[%s] Extracting BTTS Odds", thread_name)
                        soup = self._click_market(
                            session,
                            '#bettype_menu_best li[title="Both Teams To Score"]',
                            2,
                        )
                        avgs = self._average_decimals(soup)
                        odds_btts_yes, odds_btts_no = avgs[0], avgs[1]
                    except Exception as e:
                        logger.warning(
                            "[%s] Failed to scrape BTTS odds: %s", thread_name, e
                        )

                    try:
                        logger.info("[%s] Extracting DC Odds", thread_name)
                        soup = self._click_market(
                            session, '#bettype_menu_best li[title="Double Chance"]', 3
                        )
                        avgs = self._average_decimals(soup)
                        odds_dc_1x, odds_dc_12, odds_dc_x2 = avgs[0], avgs[1], avgs[2]
                    except Exception as e:
                        logger.warning(
                            "[%s] Failed to scrape DC odds: %s", thread_name, e
                        )

                    try:
                        logger.info("[%s] Extracting Over/Under Odds", thread_name)
                        ou_selector = '#bettype_menu_best li[title="Over/Under"]'
                        all_selector = ".oddsComparison__ul.bestOddsComparison li#all"
                        assert self._click_selector(session, ou_selector), (
                            "Click failed"
                        )
                        assert self._click_selector(session, all_selector), (
                            "Click failed"
                        )
                        c = self._wait_ou_handicaps(session)
                        odds_over05, odds_under05 = (
                            c["0.50"][0].get("data-odd"),
                            c["0.50"][1].get("data-odd"),
                        )
                        odds_over15, odds_under15 = (
                            c["1.50"][0].get("data-odd"),
                            c["1.50"][1].get("data-odd"),
                        )
                        odds_over25, odds_under25 = (
                            c["2.50"][0].get("data-odd"),
                            c["2.50"][1].get("data-odd"),
                        )
                        odds_over35, odds_under35 = (
                            c["3.50"][0].get("data-odd"),
                            c["3.50"][1].get("data-odd"),
                        )
                        odds_over45, odds_under45 = (
                            c["4.50"][0].get("data-odd"),
                            c["4.50"][1].get("data-odd"),
                        )
                    except Exception as e:
                        logger.warning(
                            "[%s] Failed to scrape O/U odds: %s", thread_name, e
                        )

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
                        btts_yes=odds_btts_yes,
                        btts_no=odds_btts_no,
                        dc_1x=odds_dc_1x,
                        dc_12=odds_dc_12,
                        dc_x2=odds_dc_x2,
                    )
                    logger.info("[%s] %s", thread_name, odds)

                    match = Match(
                        home_team=home_team,
                        away_team=away_team,
                        datetime=match_date,
                        predictions=None,
                        odds=odds,
                    )
                    with self._add_match_lock:
                        self.add_match(match)

                except Exception as e:
                    exception_event(
                        logger,
                        event="match.parse.failed",
                        reason_code="candidate_parse_failed",
                        message=f"[{thread_name}] Failed to parse BetExplorer match {url}: {e}",
                        source_key="betexplorer",
                        url=url,
                    )
                    continue

        logger.info("[%s] Batch complete", thread_name)

    def get_matches(self, urls) -> None:
        """Open browser tabs per match URL and scrape odds across tab clicks."""
        if not urls:
            return

        if MAX_CONCURRENCY <= 1:
            self._process_url_batch(urls)
            return

        chunks = balanced_chunks(urls, MAX_CONCURRENCY)

        logger.info(
            "Parallelizing %d URLs across %d workers (chunks: %s)",
            len(urls),
            len(chunks),
            [len(c) for c in chunks],
        )

        with ThreadPoolExecutor(
            max_workers=MAX_CONCURRENCY, thread_name_prefix="betexp"
        ) as executor:
            futures = {
                executor.submit(copy_context().run, self._process_url_batch, chunk): i
                for i, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                chunk_idx = futures[future]
                try:
                    future.result()
                    logger.info("Worker %d finished successfully", chunk_idx)
                except Exception as e:
                    exception_event(
                        logger,
                        event="source.worker.failed",
                        reason_code="worker_batch_failed",
                        message=f"BetExplorer worker {chunk_idx} failed: {e}",
                        source_key="betexplorer",
                        worker=chunk_idx,
                    )
