from __future__ import annotations

import random
import numpy as np
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field
from enum import Enum


class Outcome(str, Enum):
    PENDING = "Pending"
    WON = "Won"
    LOST = "Lost"
    LIVE = "Live"


class SlipStatus(str, Enum):
    PENDING = "Pending"
    WON = "Won"
    LOST = "Lost"
    LIVE = "Live"


@dataclass
class BetLeg:
    match_name: str
    datetime: str
    market: str
    market_type: str
    odds: float
    status: str
    result_url: str | None
    league: str | None


@dataclass
class BetSlip:
    slip_id: int
    date_generated: str
    profile: str
    total_odds: float
    units: float
    slip_status: str
    legs: list[BetLeg]
    net_profit: float | None = None


@dataclass
class Match:
    match_id: str
    datetime: str | None
    home: str
    away: str
    sources: int
    cons_home: int
    cons_draw: int
    cons_away: int
    cons_over_25: int
    cons_under_25: int
    cons_btts_yes: int
    cons_btts_no: int
    cons_over_05: int
    cons_under_05: int
    cons_over_15: int
    cons_under_15: int
    cons_over_35: int
    cons_under_35: int
    cons_over_45: int
    cons_under_45: int
    cons_dc_1x: int
    cons_dc_12: int
    cons_dc_x2: int
    odds_home: float
    odds_draw: float
    odds_away: float
    odds_over_25: float
    odds_under_25: float
    odds_btts_yes: float
    odds_btts_no: float
    odds_over_05: float
    odds_under_05: float
    odds_over_15: float
    odds_under_15: float
    odds_over_35: float
    odds_under_35: float
    odds_over_45: float
    odds_under_45: float
    odds_dc_1x: float
    odds_dc_12: float
    odds_dc_x2: float
    result_url: str | None
    league: str | None


class DemoDataProvider:
    """
    Deterministic demo data provider for dashboard demonstration.
    Generates realistic betting data spanning 6 months with 3 profiles.
    """

    PROFILES = ["Conservative", "Aggressive", "Balanced"]
    LEAGUES = [
        "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
        "Champions League", "Europa League", "Championship", "Serie B", "Primeira Liga"
    ]
    MARKETS = [
        "Match Winner", "Over/Under 2.5", "Both Teams to Score",
        "Over/Under 0.5", "Over/Under 1.5", "Over/Under 3.5", "Over/Under 4.5",
        "Double Chance 1X", "Double Chance 12", "Double Chance X2"
    ]
    MARKET_TYPES = ["1X2", "Over/Under", "BTTS", "Over/Under", "Over/Under", "Over/Under", "Over/Under", "Double Chance", "Double Chance", "Double Chance"]

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        self._slips: list[BetSlip] = []
        self._matches: list[Match] = []
        self._odds_history: dict[int, list[dict]] = {}
        self._match_id_counter = 0
        self._slip_id_counter = 0
        self._generate_all_data()

    def _generate_all_data(self) -> None:
        """Generate all demo data: matches, slips, odds history."""
        # Generate matches first (needed for slips)
        self._generate_matches()
        # Generate slips referencing matches
        self._generate_slips()
        # Generate odds history for matches in slips
        self._generate_odds_history()

    def _generate_matches(self) -> None:
        """Generate ~500 matches over 6 months."""
        start_date = datetime(2026, 2, 1)  # 6 months back from August 2026
        end_date = datetime(2026, 8, 1)
        current_date = start_date
        match_id = 0

        teams_by_league = {
            "Premier League": ["Arsenal", "Chelsea", "Liverpool", "Man City", "Man United", "Tottenham", "Newcastle", "Brighton", "Aston Villa", "West Ham"],
            "La Liga": ["Real Madrid", "Barcelona", "Atletico Madrid", "Sevilla", "Valencia", "Villarreal", "Real Sociedad", "Athletic Bilbao", "Betis", "Girona"],
            "Bundesliga": ["Bayern Munich", "Borussia Dortmund", "RB Leipzig", "Bayer Leverkusen", "Frankfurt", "Wolfsburg", "Freiburg", "Mainz", "Hoffenheim", "Stuttgart"],
            "Serie A": ["Inter Milan", "AC Milan", "Juventus", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna", "Torino"],
            "Ligue 1": ["PSG", "Marseille", "Lyon", "Monaco", "Lille", "Rennes", "Nice", "Lens", "Reims", "Montpellier"],
            "Champions League": ["Real Madrid", "Man City", "Bayern Munich", "PSG", "Inter Milan", "Arsenal", "Barcelona", "Dortmund"],
            "Europa League": ["Liverpool", "Roma", "Bayer Leverkusen", "Brighton", "Marseille", "Atalanta", "Freiburg", "Rennes"],
            "Championship": ["Leicester", "Leeds", "Southampton", "Ipswich", "Middlesbrough", "Norwich", "West Brom", "Hull City"],
            "Serie B": ["Parma", "Como", "Venezia", "Cremonese", "Catanzaro", "Palermo", "Sampdoria", "Brescia"],
            "Primeira Liga": ["Benfica", "Porto", "Sporting CP", "Braga", "Vitoria Guimaraes", "Familia", "Arouca", "Boavista"]
        }

        while current_date <= end_date:
            # 2-5 matches per day
            matches_today = random.randint(2, 5)
            for _ in range(matches_today):
                league = random.choice(self.LEAGUES)
                teams = teams_by_league.get(league, ["Team A", "Team B"])
                home, away = random.sample(teams, 2)

                # Match datetime (evening)
                match_dt = current_date.replace(hour=random.randint(18, 21), minute=random.choice([0, 15, 30, 45]))

                # Consensus values (0-100)
                cons_home = random.randint(30, 70)
                cons_draw = random.randint(20, 40)
                cons_away = 100 - cons_home - cons_draw + random.randint(-5, 5)
                cons_away = max(10, min(50, cons_away))

                # Other markets consensus
                cons_over_25 = random.randint(35, 65)
                cons_under_25 = 100 - cons_over_25 + random.randint(-3, 3)
                cons_btts_yes = random.randint(40, 70)
                cons_btts_no = 100 - cons_btts_yes + random.randint(-3, 3)

                # Odds derived from consensus with bookmaker margin
                margin = 1.05
                odds_home = round(margin * 100 / max(1, cons_home), 2)
                odds_draw = round(margin * 100 / max(1, cons_draw), 2)
                odds_away = round(margin * 100 / max(1, cons_away), 2)
                odds_over_25 = round(margin * 100 / max(1, cons_over_25), 2)
                odds_under_25 = round(margin * 100 / max(1, cons_under_25), 2)
                odds_btts_yes = round(margin * 100 / max(1, cons_btts_yes), 2)
                odds_btts_no = round(margin * 100 / max(1, cons_btts_no), 2)

                match = Match(
                    match_id=str(match_id),
                    datetime=match_dt.isoformat(),
                    home=home,
                    away=away,
                    sources=random.randint(3, 15),
                    cons_home=cons_home, cons_draw=cons_draw, cons_away=cons_away,
                    cons_over_25=cons_over_25, cons_under_25=cons_under_25,
                    cons_btts_yes=cons_btts_yes, cons_btts_no=cons_btts_no,
                    cons_over_05=random.randint(80, 95), cons_under_05=random.randint(5, 20),
                    cons_over_15=random.randint(60, 85), cons_under_15=random.randint(15, 40),
                    cons_over_35=random.randint(20, 45), cons_under_35=random.randint(55, 80),
                    cons_over_45=random.randint(10, 30), cons_under_45=random.randint(70, 90),
                    cons_dc_1x=random.randint(55, 85), cons_dc_12=random.randint(70, 95), cons_dc_x2=random.randint(45, 75),
                    odds_home=odds_home, odds_draw=odds_draw, odds_away=odds_away,
                    odds_over_25=odds_over_25, odds_under_25=odds_under_25,
                    odds_btts_yes=odds_btts_yes, odds_btts_no=odds_btts_no,
                    odds_over_05=round(margin * 100 / random.randint(80, 95), 2),
                    odds_under_05=round(margin * 100 / random.randint(5, 20), 2),
                    odds_over_15=round(margin * 100 / random.randint(60, 85), 2),
                    odds_under_15=round(margin * 100 / random.randint(15, 40), 2),
                    odds_over_35=round(margin * 100 / random.randint(20, 45), 2),
                    odds_under_35=round(margin * 100 / random.randint(55, 80), 2),
                    odds_over_45=round(margin * 100 / random.randint(10, 30), 2),
                    odds_under_45=round(margin * 100 / random.randint(70, 90), 2),
                    odds_dc_1x=round(margin * 100 / random.randint(55, 85), 2),
                    odds_dc_12=round(margin * 100 / random.randint(70, 95), 2),
                    odds_dc_x2=round(margin * 100 / random.randint(45, 75), 2),
                    result_url=f"https://example.com/match/{match_id}",
                    league=league
                )
                self._matches.append(match)
                match_id += 1
            current_date += timedelta(days=1)

        self._match_id_counter = match_id

    def _generate_slips(self) -> None:
        """Generate ~300-450 slips over 6 months across 3 profiles."""
        start_date = datetime(2026, 2, 1)
        end_date = datetime(2026, 8, 1)
        slip_id = 1

        # Profile configurations
        profile_config = {
            "Conservative": {
                "odds_range": (1.5, 2.5),
                "win_rate": 0.55,
                "stake_range": (0.5, 1.5),
                "legs_range": (1, 2),
                "slips_per_month": (15, 20)
            },
            "Balanced": {
                "odds_range": (2.0, 4.0),
                "win_rate": 0.45,
                "stake_range": (1.0, 2.5),
                "legs_range": (1, 3),
                "slips_per_month": (20, 25)
            },
            "Aggressive": {
                "odds_range": (3.0, 8.0),
                "win_rate": 0.35,
                "stake_range": (1.5, 3.0),
                "legs_range": (2, 4),
                "slips_per_month": (15, 20)
            }
        }

        current_date = start_date
        while current_date <= end_date:
            for profile in self.PROFILES:
                config = profile_config[profile]
                slips_this_month = random.randint(*config["slips_per_month"])
                # Distribute slips across the month
                for _ in range(slips_this_month):
                    slip_date = current_date + timedelta(days=random.randint(0, 27))
                    if slip_date > end_date:
                        continue

                    n_legs = random.randint(*config["legs_range"])
                    stake = round(random.uniform(*config["stake_range"]), 1)

                    # Select random matches from that time period
                    available_matches = [m for m in self._matches
                                         if m.datetime and abs((datetime.fromisoformat(m.datetime) - slip_date).days) <= 3]
                    if not available_matches or len(available_matches) < n_legs:
                        continue

                    selected_matches = random.sample(available_matches, n_legs)
                    legs = []
                    total_odds = 1.0

                    for match in selected_matches:
                        market_idx = random.randint(0, len(self.MARKETS) - 1)
                        market = self.MARKETS[market_idx]
                        market_type = self.MARKET_TYPES[market_idx]

                        # Pick odds based on market
                        if market == "Match Winner":
                            odds = random.choice([match.odds_home, match.odds_draw, match.odds_away])
                        elif market == "Over/Under 2.5":
                            odds = random.choice([match.odds_over_25, match.odds_under_25])
                        elif market == "Both Teams to Score":
                            odds = random.choice([match.odds_btts_yes, match.odds_btts_no])
                        else:
                            odds = random.uniform(*config["odds_range"])

                        odds = round(odds, 2)
                        total_odds *= odds

                        # Determine status based on profile win rate and date
                        if slip_date > datetime(2026, 7, 15):  # Recent matches - more pending/live
                            status_roll = random.random()
                            if status_roll < 0.15:
                                status = Outcome.PENDING.value
                            elif status_roll < 0.20:
                                status = Outcome.LIVE.value
                            else:
                                status = random.choices([Outcome.WON.value, Outcome.LOST.value],
                                                          weights=[config["win_rate"], 1 - config["win_rate"]])[0]
                        else:
                            # Older matches - mostly settled
                            status_roll = random.random()
                            if status_roll < 0.05:
                                status = Outcome.PENDING.value
                            else:
                                status = random.choices([Outcome.WON.value, Outcome.LOST.value],
                                                          weights=[config["win_rate"], 1 - config["win_rate"]])[0]

                        leg = BetLeg(
                            match_name=f"{match.home} vs {match.away}",
                            datetime=match.datetime or slip_date.isoformat(),
                            market=market,
                            market_type=market_type,
                            odds=odds,
                            status=status,
                            result_url=match.result_url,
                            league=match.league
                        )
                        legs.append(leg)

                    total_odds = round(total_odds, 2)

                    # Determine slip status
                    leg_statuses = [leg.status for leg in legs]
                    if any(s == Outcome.LIVE.value for s in leg_statuses):
                        slip_status = SlipStatus.LIVE.value
                    elif any(s == Outcome.PENDING.value for s in leg_statuses):
                        slip_status = SlipStatus.PENDING.value
                    elif all(s == Outcome.WON.value for s in leg_statuses):
                        slip_status = SlipStatus.WON.value
                    elif all(s == Outcome.LOST.value for s in leg_statuses):
                        slip_status = SlipStatus.LOST.value
                    else:
                        slip_status = SlipStatus.LOST.value  # Mixed = lost for accumulator

                    # Calculate net profit for settled slips
                    net_profit = None
                    if slip_status in (SlipStatus.WON.value, SlipStatus.LOST.value):
                        if slip_status == SlipStatus.WON.value:
                            net_profit = round((total_odds - 1) * stake, 2)
                        else:
                            net_profit = round(-stake, 2)

                    slip = BetSlip(
                        slip_id=slip_id,
                        date_generated=slip_date.strftime("%Y-%m-%d"),
                        profile=profile,
                        total_odds=total_odds,
                        units=stake,
                        slip_status=slip_status,
                        legs=legs,
                        net_profit=net_profit
                    )
                    self._slips.append(slip)
                    slip_id += 1
            current_date += timedelta(days=30)

        self._slip_id_counter = slip_id

    def _generate_odds_history(self) -> None:
        """Generate odds history for matches referenced in slips."""
        # Get unique match IDs from slips
        match_ids_in_slips = set()
        for slip in self._slips:
            for leg in slip.legs:
                if leg.result_url:
                    # Extract match_id from URL
                    try:
                        match_id = int(leg.result_url.split("/")[-1])
                        match_ids_in_slips.add(match_id)
                    except (ValueError, IndexError):
                        pass

        # Generate 30 days of history for each match
        for match_id in match_ids_in_slips:
            if match_id >= len(self._matches):
                continue
            match = self._matches[match_id]
            if not match.datetime:
                continue

            match_dt = datetime.fromisoformat(match.datetime)
            history = []
            for days_before in range(30, 0, -1):
                snapshot_dt = match_dt - timedelta(days=days_before)
                # Odds drift slightly over time
                drift = random.uniform(-0.15, 0.15)
                odds = {
                    "home": round(max(1.01, match.odds_home + drift), 2),
                    "draw": round(max(1.01, match.odds_draw + drift), 2),
                    "away": round(max(1.01, match.odds_away + drift), 2),
                    "over_25": round(max(1.01, match.odds_over_25 + drift), 2),
                    "under_25": round(max(1.01, match.odds_under_25 + drift), 2),
                    "btts_yes": round(max(1.01, match.odds_btts_yes + drift), 2),
                    "btts_no": round(max(1.01, match.odds_btts_no + drift), 2),
                }
                history.append({
                    "timestamp": snapshot_dt.isoformat(),
                    "odds": odds
                })
            self._odds_history[match_id] = history

    # ── Public API methods matching router expectations ─────────────────────────

    def get_analytics(self, profiles: list[str] | None, date_from: str | None, date_to: str | None) -> dict[str, Any]:
        """Return analytics data matching AnalyticsData schema."""
        filtered_slips = self._filter_slips(profiles, date_from, date_to)
        settled_slips = [s for s in filtered_slips if s.slip_status in (SlipStatus.WON.value, SlipStatus.LOST.value)]

        # History (daily P&L)
        history = self._calculate_daily_summary(settled_slips, date_from, date_to)

        # Market accuracy
        market_accuracy = self._calculate_market_accuracy(settled_slips)

        # PnL by market
        pnl_by_market = self._pnl_by_market(settled_slips)

        # Correlation
        correlation = self._calculate_correlation_data(settled_slips)

        # Profile scatter
        profile_scatter = self._profile_scatter(settled_slips)

        # Stats
        stats = self._calculate_stats(settled_slips, filtered_slips)

        # Profiles list
        all_profiles = sorted({s.profile for s in self._slips})

        # Market breakdown
        market_breakdown = self._market_breakdown(settled_slips)

        # League breakdown
        league_breakdown = self._league_breakdown(settled_slips)

        # Rolling edge
        rolling_edge = self._calculate_rolling_edge(settled_slips, 14)

        # Drawdown
        drawdown = self._calculate_drawdown(history)

        # Return distribution
        return_distribution = self._calculate_return_distribution(settled_slips)

        # Time patterns
        time_patterns = self._calculate_time_patterns(settled_slips)

        # Correlation matrix
        correlation_matrix = self._correlation_matrix(settled_slips)

        # Profit attribution
        profit_attribution = self._profit_attribution(settled_slips)

        return {
            "history": history,
            "market_accuracy": market_accuracy,
            "pnl_by_market": pnl_by_market,
            "odds_distribution": self._odds_distribution(settled_slips),
            "correlation": correlation,
            "profile_scatter": profile_scatter,
            "stats": stats,
            "profiles": all_profiles,
            "market_breakdown": market_breakdown,
            "league_breakdown": league_breakdown,
            "rolling_edge": rolling_edge,
            "drawdown": drawdown,
            "return_distribution": return_distribution,
            "time_patterns": time_patterns,
            "correlation_matrix": correlation_matrix,
            "profit_attribution": profit_attribution,
        }

    def get_slips(self, profiles: list[str] | None, date_from: str | None, date_to: str | None,
                  hide_settled: bool, live_only: bool) -> dict[str, Any]:
        """Return slips data matching SlipsPage schema."""
        filtered = self._filter_slips(profiles, date_from, date_to)

        if hide_settled:
            filtered = [s for s in filtered if s.slip_status not in (SlipStatus.WON.value, SlipStatus.LOST.value)]
        if live_only:
            filtered = [s for s in filtered if any(leg.status == Outcome.LIVE.value for leg in s.legs)]

        slips_data = []
        for slip in filtered:
            legs_data = []
            for leg in slip.legs:
                legs_data.append({
                    "match_name": leg.match_name,
                    "datetime": leg.datetime,
                    "market": leg.market,
                    "market_type": leg.market_type,
                    "odds": leg.odds,
                    "status": leg.status,
                    "result_url": leg.result_url,
                    "league": leg.league
                })
            slips_data.append({
                "slip_id": slip.slip_id,
                "date_generated": slip.date_generated,
                "profile": slip.profile,
                "total_odds": slip.total_odds,
                "units": slip.units,
                "slip_status": slip.slip_status,
                "legs": legs_data,
                "net_profit": slip.net_profit
            })

        # Stats
        settled = [s for s in filtered if s.slip_status in (SlipStatus.WON.value, SlipStatus.LOST.value)]
        stats = self._calculate_stats(settled, filtered)

        # Profiles with slips
        all_slips_for_profiles = self._filter_slips(None, date_from, date_to)
        profiles_with_slips = sorted({s.profile for s in all_slips_for_profiles})

        return {
            "slips": slips_data,
            "stats": stats,
            "profiles": profiles_with_slips
        }

    def get_matches(self, page: int = 1, page_size: int = 40, search: str | None = None,
                    date_from: str | None = None, date_to: str | None = None,
                    sort_by: str = "datetime", sort_dir: str = "asc",
                    min_consensus: int | None = None, min_odds: float | None = None,
                    only_significant_movement: bool = False) -> dict[str, Any]:
        """Return matches data matching MatchesPage schema."""
        filtered = self._matches

        if search:
            search_lower = search.lower()
            filtered = [m for m in filtered if search_lower in m.home.lower() or search_lower in m.away.lower()]

        if date_from:
            filtered = [m for m in filtered if m.datetime and m.datetime >= date_from]
        if date_to:
            filtered = [m for m in filtered if m.datetime and m.datetime <= date_to]

        # Sort
        reverse = sort_dir == "desc"
        if sort_by == "datetime":
            filtered.sort(key=lambda m: m.datetime or "", reverse=reverse)
        elif sort_by == "home":
            filtered.sort(key=lambda m: m.home, reverse=reverse)
        elif sort_by == "away":
            filtered.sort(key=lambda m: m.away, reverse=reverse)
        elif sort_by == "sources":
            filtered.sort(key=lambda m: m.sources, reverse=reverse)

        total = len(filtered)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        page_matches = filtered[start:end]

        matches_data = []
        for m in page_matches:
            matches_data.append({
                "match_id": m.match_id,
                "datetime": m.datetime,
                "home": m.home,
                "away": m.away,
                "sources": m.sources,
                "cons_home": m.cons_home, "cons_draw": m.cons_draw, "cons_away": m.cons_away,
                "cons_over_25": m.cons_over_25, "cons_under_25": m.cons_under_25,
                "cons_btts_yes": m.cons_btts_yes, "cons_btts_no": m.cons_btts_no,
                "cons_over_05": m.cons_over_05, "cons_under_05": m.cons_under_05,
                "cons_over_15": m.cons_over_15, "cons_under_15": m.cons_under_15,
                "cons_over_35": m.cons_over_35, "cons_under_35": m.cons_under_35,
                "cons_over_45": m.cons_over_45, "cons_under_45": m.cons_under_45,
                "cons_dc_1x": m.cons_dc_1x, "cons_dc_12": m.cons_dc_12, "cons_dc_x2": m.cons_dc_x2,
                "odds_home": m.odds_home, "odds_draw": m.odds_draw, "odds_away": m.odds_away,
                "odds_over_25": m.odds_over_25, "odds_under_25": m.odds_under_25,
                "odds_btts_yes": m.odds_btts_yes, "odds_btts_no": m.odds_btts_no,
                "odds_over_05": m.odds_over_05, "odds_under_05": m.odds_under_05,
                "odds_over_15": m.odds_over_15, "odds_under_15": m.odds_under_15,
                "odds_over_35": m.odds_over_35, "odds_under_35": m.odds_under_35,
                "odds_over_45": m.odds_over_45, "odds_under_45": m.odds_under_45,
                "odds_dc_1x": m.odds_dc_1x, "odds_dc_12": m.odds_dc_12, "odds_dc_x2": m.odds_dc_x2,
                "result_url": m.result_url,
                "league": m.league
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "matches": matches_data
        }

    def get_profiles(self) -> dict[str, Any]:
        """Return demo profiles."""
        profiles = {
            "Conservative": {
                "target_odds": 2.0, "target_legs": 1, "max_legs_overflow": 1,
                "consensus_floor": 60, "min_odds": 1.5,
                "included_markets": ["Match Winner", "Double Chance 1X"],
                "included_leagues": ["Premier League", "La Liga", "Bundesliga"],
                "tolerance_factor": 1.2, "stop_threshold": 0.02,
                "min_legs_fill_ratio": 0.8, "quality_vs_balance": 0.7, "consensus_vs_sources": 0.6,
                "units": 1.0, "target_payout": 10.0, "run_daily_count": 1,
                "consensus_shrinkage_k": 10, "min_source_edge": 2.0,
                "max_single_leg_odds": 3.0, "tol_lower": 0.8, "tol_upper": 1.2,
                "balance_decay": "linear", "min_pick_quality": 0.6,
                "odds_movement_weight": 0.3, "odds_movement_strength_min": 0.05
            },
            "Balanced": {
                "target_odds": 3.5, "target_legs": 2, "max_legs_overflow": 1,
                "consensus_floor": 50, "min_odds": 1.8,
                "included_markets": ["Match Winner", "Over/Under 2.5", "Both Teams to Score"],
                "included_leagues": ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"],
                "tolerance_factor": 1.0, "stop_threshold": 0.05,
                "min_legs_fill_ratio": 0.7, "quality_vs_balance": 0.5, "consensus_vs_sources": 0.5,
                "units": 1.5, "target_payout": 25.0, "run_daily_count": 2,
                "consensus_shrinkage_k": 8, "min_source_edge": 1.5,
                "max_single_leg_odds": 5.0, "tol_lower": 0.7, "tol_upper": 1.3,
                "balance_decay": "gaussian", "min_pick_quality": 0.5,
                "odds_movement_weight": 0.5, "odds_movement_strength_min": 0.03
            },
            "Aggressive": {
                "target_odds": 6.0, "target_legs": 3, "max_legs_overflow": 2,
                "consensus_floor": 40, "min_odds": 2.0,
                "included_markets": ["Match Winner", "Over/Under 2.5", "Both Teams to Score", "Over/Under 3.5"],
                "included_leagues": self.LEAGUES,
                "tolerance_factor": 0.8, "stop_threshold": 0.1,
                "min_legs_fill_ratio": 0.6, "quality_vs_balance": 0.3, "consensus_vs_sources": 0.4,
                "units": 2.0, "target_payout": 50.0, "run_daily_count": 3,
                "consensus_shrinkage_k": 5, "min_source_edge": 1.0,
                "max_single_leg_odds": 10.0, "tol_lower": 0.6, "tol_upper": 1.5,
                "balance_decay": "gaussian", "min_pick_quality": 0.4,
                "odds_movement_weight": 0.7, "odds_movement_strength_min": 0.02
            }
        }
        return {"profiles": profiles}

    def get_odds_history(self, match_id: int) -> dict[str, Any]:
        """Return odds history for a match."""
        if match_id < 0 or match_id >= len(self._matches):
            raise ValueError(f"Match {match_id} not found")

        match = self._matches[match_id]
        history = self._odds_history.get(match_id, [])

        snapshots = [{"timestamp": h["timestamp"], "odds": h["odds"]} for h in history]

        # Calculate movement
        movement = {}
        if len(history) >= 2:
            first = history[0]["odds"]
            last = history[-1]["odds"]
            for key in first:
                if key in last:
                    change = (last[key] - first[key]) / first[key] * 100
                    if abs(change) > 2:
                        movement[key] = "up" if change > 0 else "down"
                    else:
                        movement[key] = "stable"

        return {
            "match_id": match_id,
            "match_name": f"{match.home} vs {match.away}",
            "datetime": match.datetime or "",
            "snapshots": snapshots,
            "movement": movement
        }

    def get_all_movements(self) -> dict[str, Any]:
        """Return movement summary for all future matches."""
        result = {}
        now = datetime.now()
        for idx, match in enumerate(self._matches):
            if match.datetime:
                match_dt = datetime.fromisoformat(match.datetime)
                if match_dt > now:
                    history = self._odds_history.get(idx, [])
                    if len(history) >= 2:
                        first = history[0]["odds"]
                        last = history[-1]["odds"]
                        movement = {}
                        for key in first:
                            if key in last:
                                change = (last[key] - first[key]) / first[key] * 100
                                if abs(change) > 2:
                                    movement[key] = "up" if change > 0 else "down"
                                else:
                                    movement[key] = "stable"
                        if movement:
                            result[str(idx)] = movement
        return result

    def get_significant_movements(self) -> dict[str, Any]:
        """Return significant movements only."""
        all_movements = self.get_all_movements()
        result = {}
        for match_id, movement in all_movements.items():
            sig_count = sum(1 for v in movement.values() if v in ("up", "down"))
            if sig_count > 0:
                result[match_id] = movement
        return result

    # ── Helper methods (adapted from analytics.py) ──────────────────────────────

    def _filter_slips(self, profiles: list[str] | None, date_from: str | None, date_to: str | None) -> list[BetSlip]:
        filtered = self._slips
        if profiles:
            filtered = [s for s in filtered if s.profile in profiles]
        if date_from:
            filtered = [s for s in filtered if s.date_generated >= date_from]
        if date_to:
            filtered = [s for s in filtered if s.date_generated <= date_to]
        return filtered

    def _calculate_daily_summary(self, slips: list[BetSlip], date_from: str | None, date_to: str | None) -> list[dict]:
        from collections import defaultdict
        daily = defaultdict(lambda: {"slips": 0, "units": 0.0, "profit": 0.0, "won": 0, "total": 0})
        for slip in slips:
            date = slip.date_generated
            daily[date]["slips"] += 1
            daily[date]["units"] += slip.units
            if slip.net_profit is not None:
                daily[date]["profit"] += slip.net_profit
            if slip.slip_status == SlipStatus.WON.value:
                daily[date]["won"] += 1
            daily[date]["total"] += 1

        sorted_dates = sorted(daily.keys())
        if date_from:
            sorted_dates = [d for d in sorted_dates if d >= date_from]
        if date_to:
            sorted_dates = [d for d in sorted_dates if d <= date_to]

        cumulative = 0.0
        cumulative_bet = 0.0
        result = []
        for date in sorted_dates:
            d = daily[date]
            cumulative += d["profit"]
            cumulative_bet += d["units"]
            roi = (cumulative / cumulative_bet * 100) if cumulative_bet > 0 else 0.0
            wr = (d["won"] / d["total"] * 100) if d["total"] > 0 else 0.0
            result.append({
                "date": date,
                "slips_count": d["slips"],
                "units_bet": round(d["units"], 2),
                "net_profit": round(d["profit"], 2),
                "cumulative_profit": round(cumulative, 2),
                "cumulative_bet": round(cumulative_bet, 2),
                "roi_percentage": round(roi, 2),
                "win_rate": round(wr, 2)
            })
        return result

    def _calculate_market_accuracy(self, slips: list[BetSlip]) -> list[dict]:
        from collections import defaultdict
        market_stats = defaultdict(lambda: {"won": 0, "lost": 0, "total": 0})
        processed = set()
        for slip in slips:
            for leg in slip.legs:
                fp = (leg.result_url, leg.market)
                if fp in processed:
                    continue
                processed.add(fp)
                m = market_stats[leg.market]
                m["total"] += 1
                if leg.status == Outcome.WON.value:
                    m["won"] += 1
                elif leg.status == Outcome.LOST.value:
                    m["lost"] += 1
        return [
            {"market": m, "won": v["won"], "lost": v["lost"], "total": v["total"],
             "accuracy": round(v["won"] / v["total"] * 100, 1) if v["total"] > 0 else 0.0}
            for m, v in market_stats.items()
        ]

    def _pnl_by_market(self, slips: list[BetSlip]) -> list[dict]:
        from collections import defaultdict
        market_pnl = defaultdict(lambda: {"won": 0, "lost": 0, "profit": 0.0})
        processed = set()
        for slip in slips:
            n_legs = max(len(slip.legs), 1)
            per_leg_stake = slip.units / n_legs
            for leg in slip.legs:
                fp = (leg.result_url, leg.market)
                if fp in processed:
                    continue
                processed.add(fp)
                m = market_pnl[leg.market]
                if leg.status == Outcome.WON.value:
                    m["won"] += 1
                    m["profit"] += (leg.odds - 1) * per_leg_stake
                elif leg.status == Outcome.LOST.value:
                    m["lost"] += 1
                    m["profit"] -= per_leg_stake
        return [
            {"market": m, "won": v["won"], "lost": v["lost"], "net_profit": round(v["profit"], 2)}
            for m, v in market_pnl.items()
        ]

    def _odds_distribution(self, slips: list[BetSlip]) -> list[dict]:
        buckets = [
            (1.0, 1.5, "1.0-1.5"), (1.5, 2.0, "1.5-2.0"), (2.0, 3.0, "2.0-3.0"),
            (3.0, 5.0, "3.0-5.0"), (5.0, 10.0, "5.0-10.0"), (10.0, 100.0, "10.0+")
        ]
        bucket_stats = {label: {"count": 0, "wins": 0, "losses": 0, "sum_odds": 0.0, "sum_implied": 0.0} for _, _, label in buckets}
        processed = set()
        for slip in slips:
            for leg in slip.legs:
                fp = (leg.result_url, leg.market)
                if fp in processed:
                    continue
                processed.add(fp)
                for low, high, label in buckets:
                    if low <= leg.odds < high or (label == "10.0+" and leg.odds >= 10.0):
                        b = bucket_stats[label]
                        b["count"] += 1
                        b["sum_odds"] += leg.odds
                        b["sum_implied"] += 1.0 / leg.odds if leg.odds > 0 else 0
                        if leg.status == Outcome.WON.value:
                            b["wins"] += 1
                        elif leg.status == Outcome.LOST.value:
                            b["losses"] += 1
                        break
        result = []
        for low, high, label in buckets:
            b = bucket_stats[label]
            if b["count"] == 0:
                continue
            wr = round(b["wins"] / b["count"] * 100, 1)
            implied = round(b["sum_implied"] / b["count"] * 100, 1)
            result.append({
                "range": label,
                "count": b["count"],
                "wins": b["wins"],
                "losses": b["losses"],
                "win_rate": wr,
                "implied_win_rate": implied,
                "avg_odds": round(b["sum_odds"] / b["count"], 2),
                "edge": round(wr - implied, 1)
            })
        return result

    def _calculate_correlation_data(self, slips: list[BetSlip]) -> list[dict]:
        result = []
        for slip in slips:
            n_legs = len(slip.legs)
            result.append({
                "legs_count": n_legs,
                "total_odds": slip.total_odds,
                "units": slip.units,
                "status": slip.slip_status,
                "profit": slip.net_profit or 0.0
            })
        return result

    def _profile_scatter(self, slips: list[BetSlip]) -> list[dict]:
        from collections import defaultdict
        profiles = defaultdict(lambda: {"total": 0, "won": 0, "sum_odds": 0.0, "sum_profit": 0.0})
        for slip in slips:
            p = profiles[slip.profile]
            p["total"] += 1
            p["sum_odds"] += slip.total_odds
            if slip.slip_status == SlipStatus.WON.value:
                p["won"] += 1
                p["sum_profit"] += (slip.total_odds - 1) * slip.units
            elif slip.slip_status == SlipStatus.LOST.value:
                p["sum_profit"] -= slip.units
        return [
            {
                "profile": p,
                "avg_odds": round(d["sum_odds"] / d["total"], 2),
                "win_rate": round(d["won"] / d["total"] * 100, 1),
                "net_profit": round(d["sum_profit"], 2),
                "volume": d["total"],
                "break_even_win_rate": round(d["total"] / d["sum_odds"] * 100, 1) if d["sum_odds"] > 0 else 0.0
            }
            for p, d in profiles.items()
        ]

    def _calculate_stats(self, settled: list[BetSlip], all_slips: list[BetSlip]) -> dict[str, Any]:
        if not settled:
            return {
                "total_settled": 0, "total_won_count": 0, "win_rate": 0.0,
                "implied_win_rate": 0.0, "edge": 0.0, "total_units_bet": 0.0,
                "gross_return": 0.0, "net_profit": 0.0, "roi_percentage": 0.0,
                "avg_odds": 0.0, "avg_units": 0.0, "units_std": 0.0,
                "pending_count": len([s for s in all_slips if s.slip_status == SlipStatus.PENDING.value]),
                "sharpe_ratio": None, "kelly_suggested_units": 0.0,
                "edge_trend": "neutral", "recent_edge_value": 0.0,
                "biggest_win_units": None, "biggest_loss_units": None,
                "best_day_pnl": None, "worst_day_pnl": None,
                "current_streak": 0, "longest_win_streak": 0, "longest_loss_streak": 0,
                "profit_factor": 0.0
            }

        total_settled = len(settled)
        total_won = len([s for s in settled if s.slip_status == SlipStatus.WON.value])
        win_rate = round(total_won / total_settled * 100, 1)

        total_units = sum(s.units for s in settled)
        gross_return = sum((s.total_odds - 1) * s.units for s in settled if s.slip_status == SlipStatus.WON.value)
        net_profit = sum(s.net_profit or 0 for s in settled)
        roi = round(net_profit / total_units * 100, 2) if total_units > 0 else 0.0
        avg_odds = round(sum(s.total_odds for s in settled) / total_settled, 2)
        avg_units = round(total_units / total_settled, 2)

        # Implied win rate
        implied_sum = sum(1.0 / s.total_odds for s in settled if s.total_odds > 0)
        implied_wr = round(implied_sum / total_settled * 100, 1) if total_settled > 0 else 0.0
        edge = round(win_rate - implied_wr, 1)

        # Streaks
        daily_pnl = {}
        for slip in settled:
            date = slip.date_generated
            daily_pnl[date] = daily_pnl.get(date, 0) + (slip.net_profit or 0)
        sorted_dates = sorted(daily_pnl.keys())
        current_streak = 0
        longest_win = 0
        longest_loss = 0
        temp_win = 0
        temp_loss = 0
        for date in sorted_dates:
            pnl = daily_pnl[date]
            if pnl > 0:
                temp_win += 1
                temp_loss = 0
                longest_win = max(longest_win, temp_win)
            elif pnl < 0:
                temp_loss += 1
                temp_win = 0
                longest_loss = max(longest_loss, temp_loss)
            else:
                temp_win = 0
                temp_loss = 0
        if sorted_dates:
            last_pnl = daily_pnl[sorted_dates[-1]]
            if last_pnl > 0:
                current_streak = temp_win
            elif last_pnl < 0:
                current_streak = -temp_loss

        # Biggest win/loss
        won_slips = [s for s in settled if s.slip_status == SlipStatus.WON.value]
        lost_slips = [s for s in settled if s.slip_status == SlipStatus.LOST.value]
        biggest_win = max((s.net_profit or 0) for s in won_slips) if won_slips else None
        biggest_loss = min((s.net_profit or 0) for s in lost_slips) if lost_slips else None

        # Best/worst day
        best_day = max(daily_pnl.values()) if daily_pnl else None
        worst_day = min(daily_pnl.values()) if daily_pnl else None

        # Profit factor
        gross_profit = sum(s.net_profit or 0 for s in won_slips)
        gross_loss = abs(sum(s.net_profit or 0 for s in lost_slips))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0

        # Kelly
        kelly = 0.0
        if total_settled > 0 and implied_wr > 0:
            kelly = round((win_rate / 100 - implied_wr / 100) / (avg_odds - 1) * 100, 2) if avg_odds > 1 else 0.0

        return {
            "total_settled": total_settled,
            "total_won_count": total_won,
            "win_rate": win_rate,
            "implied_win_rate": implied_wr,
            "edge": edge,
            "total_units_bet": round(total_units, 2),
            "gross_return": round(gross_return, 2),
            "net_profit": round(net_profit, 2),
            "roi_percentage": roi,
            "avg_odds": avg_odds,
            "avg_units": avg_units,
            "units_std": 0.0,
            "pending_count": len([s for s in all_slips if s.slip_status == SlipStatus.PENDING.value]),
            "sharpe_ratio": None,
            "kelly_suggested_units": kelly,
            "edge_trend": "neutral",
            "recent_edge_value": 0.0,
            "biggest_win_units": biggest_win,
            "biggest_loss_units": biggest_loss,
            "best_day_pnl": best_day,
            "worst_day_pnl": worst_day,
            "current_streak": current_streak,
            "longest_win_streak": longest_win,
            "longest_loss_streak": longest_loss,
            "profit_factor": profit_factor
        }

    def _market_breakdown(self, slips: list[BetSlip]) -> list[dict]:
        from collections import defaultdict
        data = defaultdict(lambda: {"legs": 0, "won": 0, "lost": 0, "sum_odds": 0.0, "sum_implied": 0.0, "net_profit": 0.0})
        processed = set()
        for slip in slips:
            n_legs = max(len(slip.legs), 1)
            per_leg_stake = slip.units / n_legs
            for leg in slip.legs:
                fp = (leg.result_url, leg.market)
                if fp in processed:
                    continue
                processed.add(fp)
                m = data[leg.market]
                m["legs"] += 1
                m["sum_odds"] += leg.odds
                m["sum_implied"] += 1.0 / leg.odds if leg.odds > 0 else 0
                if leg.status == Outcome.WON.value:
                    m["won"] += 1
                    m["net_profit"] += (leg.odds - 1) * per_leg_stake
                elif leg.status == Outcome.LOST.value:
                    m["lost"] += 1
                    m["net_profit"] -= per_leg_stake
        result = []
        for m, d in data.items():
            total = d["legs"]
            wr = round(d["won"] / total * 100, 1) if total else 0.0
            implied = round(d["sum_implied"] / total * 100, 1) if total else 0.0
            result.append({
                "market": m, "legs": total, "won": d["won"], "lost": d["lost"],
                "win_rate": wr, "implied_win_rate": implied, "edge": round(wr - implied, 1),
                "avg_odds": round(d["sum_odds"] / total, 2) if total else 0.0,
                "net_profit": round(d["net_profit"], 2)
            })
        return sorted(result, key=lambda x: x["edge"], reverse=True)

    def _league_breakdown(self, slips: list[BetSlip]) -> list[dict]:
        from collections import defaultdict
        data = defaultdict(lambda: {"legs": 0, "won": 0, "lost": 0, "sum_odds": 0.0, "sum_implied": 0.0, "net_profit": 0.0})
        processed = set()
        for slip in slips:
            n_legs = max(len(slip.legs), 1)
            per_leg_stake = slip.units / n_legs
            for leg in slip.legs:
                fp = (leg.result_url, leg.market)
                if fp in processed:
                    continue
                processed.add(fp)
                lg = leg.league or "Unknown"
                m = data[lg]
                m["legs"] += 1
                m["sum_odds"] += leg.odds
                m["sum_implied"] += 1.0 / leg.odds if leg.odds > 0 else 0
                if leg.status == Outcome.WON.value:
                    m["won"] += 1
                    m["net_profit"] += (leg.odds - 1) * per_leg_stake
                elif leg.status == Outcome.LOST.value:
                    m["lost"] += 1
                    m["net_profit"] -= per_leg_stake
        result = []
        for lg, d in data.items():
            total = d["legs"]
            wr = round(d["won"] / total * 100, 1) if total else 0.0
            implied = round(d["sum_implied"] / total * 100, 1) if total else 0.0
            result.append({
                "league": lg, "legs": total, "won": d["won"], "lost": d["lost"],
                "win_rate": wr, "implied_win_rate": implied, "edge": round(wr - implied, 1),
                "avg_odds": round(d["sum_odds"] / total, 2) if total else 0.0,
                "net_profit": round(d["net_profit"], 2)
            })
        return sorted(result, key=lambda x: x["edge"], reverse=True)

    def _calculate_rolling_edge(self, slips: list[BetSlip], window: int) -> list[dict]:
        from collections import defaultdict
        daily = defaultdict(lambda: {"won": 0, "total": 0, "sum_implied": 0.0})
        processed = set()
        for slip in slips:
            date = slip.date_generated
            for leg in slip.legs:
                fp = (leg.result_url, leg.market)
                if fp in processed:
                    continue
                processed.add(fp)
                d = daily[date]
                d["total"] += 1
                d["sum_implied"] += 1.0 / leg.odds if leg.odds > 0 else 0
                if leg.status == Outcome.WON.value:
                    d["won"] += 1
        sorted_dates = sorted(daily.keys())
        result = []
        for i, date in enumerate(sorted_dates):
            start = max(0, i - window + 1)
            window_dates = sorted_dates[start:i+1]
            total_won = sum(daily[d]["won"] for d in window_dates)
            total_legs = sum(daily[d]["total"] for d in window_dates)
            total_implied = sum(daily[d]["sum_implied"] for d in window_dates)
            if total_legs > 0:
                wr = round(total_won / total_legs * 100, 1)
                implied = round(total_implied / total_legs * 100, 1)
                result.append({
                    "date": date,
                    "rolling_edge": round(wr - implied, 1),
                    "rolling_win_rate": wr,
                    "rolling_implied": implied,
                    "sample_size": total_legs
                })
        return result

    def _calculate_drawdown(self, history: list[dict]) -> list[dict]:
        if not history:
            return []
        peak = 0.0
        result = []
        for day in history:
            cum = day["cumulative_profit"]
            if cum > peak:
                peak = cum
            result.append({
                "date": day["date"],
                "drawdown": round(cum - peak, 2),
                "peak": round(peak, 2),
                "cumulative_profit": cum
            })
        return result

    def _calculate_return_distribution(self, slips: list[BetSlip]) -> dict[str, Any] | None:
        if not slips:
            return None
        profits = [s.net_profit or 0 for s in slips]
        if not profits:
            return None
        import math
        mean = sum(profits) / len(profits)
        sorted_profits = sorted(profits)
        median = sorted_profits[len(sorted_profits) // 2]
        min_p, max_p = min(profits), max(profits)
        bin_width = max(0.5, (max_p - min_p) / 10) if max_p != min_p else 1.0
        bins = []
        for i in range(10):
            low = min_p + i * bin_width
            high = low + bin_width
            count = sum(1 for p in profits if low <= p < high) or (1 if i == 9 and max_p == high else 0)
            bins.append({
                "range": f"{low:.1f}",
                "range_end": f"{high:.1f}",
                "count": count,
                "is_positive": low >= 0
            })
        return {"bins": bins, "mean": round(mean, 2), "median": round(median, 2)}

    def _calculate_time_patterns(self, slips: list[BetSlip]) -> dict[str, Any] | None:
        from collections import defaultdict
        dow = defaultdict(lambda: {"total": 0, "won": 0})
        hour = defaultdict(lambda: {"total": 0, "won": 0})
        for slip in slips:
            try:
                dt = datetime.strptime(slip.date_generated, "%Y-%m-%d")
                dow[dt.strftime("%A")]["total"] += 1
                if slip.slip_status == SlipStatus.WON.value:
                    dow[dt.strftime("%A")]["won"] += 1
            except ValueError:
                pass
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_result = []
        for day in dow_order:
            if day in dow:
                d = dow[day]
                dow_result.append({"key": day, "total": d["total"], "won": d["won"],
                                   "win_rate": round(d["won"] / d["total"] * 100, 1) if d["total"] > 0 else 0.0})
        return {"day_of_week": dow_result, "hour": []}

    def _correlation_matrix(self, slips: list[BetSlip]) -> dict[str, Any]:
        from collections import defaultdict
        data = defaultdict(lambda: defaultdict(lambda: {"won": 0, "total": 0, "sum_implied": 0.0}))
        leagues = set()
        markets = set()
        processed = set()
        for slip in slips:
            for leg in slip.legs:
                fp = (leg.result_url, leg.market)
                if fp in processed:
                    continue
                processed.add(fp)
                lg = leg.league or "Unknown"
                mkt = leg.market
                leagues.add(lg)
                markets.add(mkt)
                cell = data[lg][mkt]
                cell["total"] += 1
                cell["sum_implied"] += 1.0 / leg.odds if leg.odds > 0 else 0
                if leg.status == Outcome.WON.value:
                    cell["won"] += 1
        matrix = {}
        for lg in sorted(leagues):
            matrix[lg] = {}
            for mkt in sorted(markets):
                if mkt in data[lg]:
                    d = data[lg][mkt]
                    wr = round(d["won"] / d["total"] * 100, 1) if d["total"] > 0 else 0.0
                    implied = round(d["sum_implied"] / d["total"] * 100, 1) if d["total"] > 0 else 0.0
                    matrix[lg][mkt] = {"win_rate": wr, "edge": round(wr - implied, 1), "total": d["total"]}
        return {"leagues": sorted(leagues), "markets": sorted(markets), "matrix": matrix}

    def _profit_attribution(self, slips: list[BetSlip]) -> dict[str, Any]:
        """Sequential Shapley approximation for profit attribution."""
        import pandas as pd
        records = []
        for slip in slips:
            n_legs = max(len(slip.legs), 1)
            per_leg_stake = slip.units / n_legs
            slip_profit = 0.0
            for leg in slip.legs:
                leg_profit = (leg.odds - 1) * per_leg_stake if leg.status == Outcome.WON.value else -per_leg_stake
                slip_profit += leg_profit
                records.append({
                    "slip_id": slip.slip_id,
                    "leg_result_url": leg.result_url,
                    "market": leg.market,
                    "league": leg.league or "Unknown",
                    "odds": leg.odds,
                    "bet_type": f"{len(slip.legs)}-leg" if len(slip.legs) < 5 else "5+",
                    "stake": per_leg_stake,
                    "profile": slip.profile,
                    "date_generated": slip.date_generated,
                    "profit": leg_profit,
                    "slip_profit": slip_profit,
                })
        if not records:
            return {"total_profit": 0.0, "components": []}
        df = pd.DataFrame(records)
        total_profit = df["slip_profit"].iloc[0] if not df.empty else 0.0
        df = df.drop_duplicates(subset=["leg_result_url", "market"])
        def odds_bucket(o):
            if o < 1.5: return "<1.5"
            elif o < 2.0: return "1.5-2.0"
            elif o < 3.5: return "2.0-3.5"
            elif o < 7.0: return "3.5-7.0"
            else: return "7.0+"
        df["odds_bucket"] = df["odds"].apply(odds_bucket)
        df["timing_bucket"] = "Pre-match (>24h)"
        dimensions = [
            ("Market Selection", "market"),
            ("League Selection", "league"),
            ("Odds Range", "odds_bucket"),
            ("Bet Type", "bet_type"),
            ("Stake Sizing", "stake"),
            ("Timing", "timing_bucket"),
            ("Profile", "profile"),
        ]
        components = []
        running_total = 0.0
        prev_avg = 0.0
        for name, col in dimensions:
            grouped = df.groupby(col).agg(avg_profit=("profit", "mean"), count=("profit", "count")).reset_index()
            weighted_avg = (grouped["avg_profit"] * grouped["count"]).sum() / grouped["count"].sum()
            contribution = weighted_avg - prev_avg
            running_total += contribution
            components.append({
                "name": name,
                "value": round(contribution, 2),
                "percentage": round(contribution / total_profit * 100, 1) if total_profit != 0 else 0.0,
                "sub_components": [
                    {"name": row[col], "value": round(row["avg_profit"], 2), "count": int(row["count"])}
                    for _, row in grouped.iterrows()
                ],
            })
            prev_avg = weighted_avg
        residual = total_profit - running_total
        components.append({
            "name": "Residual (Noise)",
            "value": round(residual, 2),
            "percentage": round(residual / total_profit * 100, 1) if total_profit != 0 else 0.0,
            "sub_components": [],
        })
        return {"total_profit": round(total_profit, 2), "components": components}


# Singleton instance
demo_provider = DemoDataProvider()


def get_demo_provider() -> DemoDataProvider:
    return demo_provider
