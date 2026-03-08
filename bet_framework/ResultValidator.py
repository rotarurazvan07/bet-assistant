from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup

class ResultValidator:
    """
    Validates betting outcomes by scraping match result pages.
    Can extract both LIVE scores (with minutes) and FULL TIME results.
    """

    @staticmethod
    def _parse_score(raw: str) -> Tuple[int, int]:
        """Parse 'H:A' score string into (home_goals, away_goals)."""
        parts = raw.split(":")
        return int(parts[0]), int(parts[1])

    @staticmethod
    def _determine_outcome(home: int, away: int, market: str, market_type: str) -> str:
        """Return 'Won', 'Lost', or 'Pending' for a single leg given the final score."""
        if market_type == "result":
            if   market == "1" and home > away:  return "Won"
            elif market == "2" and away > home:  return "Won"
            elif market == "X" and home == away: return "Won"
            return "Lost"

        if market_type == "btts":
            scored = home > 0 and away > 0
            if   market == "BTTS Yes" and scored:   return "Won"
            elif market == "BTTS No"  and not scored: return "Won"
            return "Lost"

        if market_type == "over_under_2.5":
            total = home + away
            if   market == "Over 2.5"  and total >= 3: return "Won"
            elif market == "Under 2.5" and total <  3: return "Won"
            return "Lost"

        return "Pending"

    @classmethod
    def check_match_status(cls, url: str, market: str, market_type: str) -> Dict[str, Any]:
        """
        Scrape the result URL.
        Returns a dict:
            {
                "status": "LIVE" | "FT" | "PENDING",
                "score": "H:A" (if available),
                "minute": "45'" (if LIVE),
                "outcome": "Won" | "Lost" | "" (only set if FT)
            }
        """
        try:
            # We import here to avoid circular dependencies and because it relies on requests/bs4
            from bet_framework.WebScraper import WebScraper
            html = WebScraper.fetch(url)
            soup = BeautifulSoup(html, "html.parser")
            
            result = {
                "status": "PENDING",
                "score": "",
                "minute": "",
                "outcome": ""
            }

            score_div = soup.find("div", class_="text-base font-bold min-sm:text-xl text-center")
            
            if score_div:
                raw_score = score_div.get_text(strip=True)
                result["score"] = raw_score
                
                # Check status text
                status_container = soup.find(id="status-container")
                status_text = status_container.get_text(strip=True) if status_container else ""
                
                if "FT" in status_text or "Finished" in status_text:
                    result["status"] = "FT"
                    try:
                        h, a = cls._parse_score(raw_score)
                        result["outcome"] = cls._determine_outcome(h, a, market, market_type)
                    except Exception:
                        pass
                else:
                    # It has a score but not FT -> LIVE
                    result["status"] = "LIVE"
                    parent = score_div.parent
                    if parent:
                        # Sometimes parent text looks like: `| 0:1 | 66' | Stade de...`
                        # SoccerVista specifically places it here.
                        text = parent.get_text(separator=' | ', strip=True)
                        parts = [p.strip() for p in text.split('|')]
                        for part in parts:
                            if "'" in part and part[0].isdigit():
                                result["minute"] = part
                                break
                                
            return result
        except Exception as e:
            return {"status": "ERROR", "score": "", "minute": "", "outcome": "", "error": str(e)}
