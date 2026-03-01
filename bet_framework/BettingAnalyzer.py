"""
BettingAnalyzer - Data processing, filtering, and bet-slip building.
Optimized to work directly with DataFrames from the database.

SCORING MODEL OVERVIEW
──────────────────────
Every candidate pick is scored on three normalized axes (each 0.0 → 1.0):

  1. prob_score    — How confident are we in this outcome?
                     Normalized from probability_floor (= 0) to 100 % (= 1).
                     A pick right at the floor scores 0; a 100 % certainty scores 1.

  2. sources_score — How many independent data sources back this pick?
                     Normalized from 0 (= 0) to max_sources (= 1).

  3. balance_score — How close is the pick's odds to the ideal per-leg target?
                     1.0 = perfect match, 0.0 = at or beyond the tolerance edge.
                     Decays linearly so moderate deviations still contribute.

These three axes are combined using two simple levers:

  quality_vs_balance (0.0 → 1.0)
      Controls the trade-off between quality and odds balance.
      0.0 = pick purely by odds balance (ignore prob/sources entirely)
      0.5 = equal weight between quality and balance  ← default
      1.0 = pick purely by quality (ignore odds balance)

  prob_vs_sources (0.0 → 1.0)
      Within the quality component, controls how much prob vs sources matters.
      0.0 = quality comes entirely from sources
      0.5 = equal weight between prob and sources  ← default
      1.0 = quality comes entirely from probability

Final formula:
  quality_score = prob_vs_sources × prob_score + (1 − prob_vs_sources) × sources_score
  final_score   = quality_vs_balance × quality_score + (1 − quality_vs_balance) × balance_score

All scores and weights are bounded [0.0, 1.0], so final_score is always [0.0, 1.0]
and every parameter has an immediately understandable meaning.

Picks that fall within the odds tolerance band are "Tier 1" and always ranked above
"Tier 2" picks that fall outside it — regardless of score — to prevent the slip from
drifting far from the target total odds.
"""

import copy
import hashlib
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from bet_framework.SettingsManager import settings_manager


# ──────────────────────────────────────────────────────────────────────────────
# Market definition — single source of truth
# ──────────────────────────────────────────────────────────────────────────────

MARKET_MAP: Dict[str, List[Tuple[str, str, str]]] = {
    'result':         [('prob_home',     'odds_home',     '1'),
                       ('prob_draw',     'odds_draw',     'X'),
                       ('prob_away',     'odds_away',     '2')],
    'over_under_2.5': [('prob_over',     'odds_over',     'Over 2.5'),
                       ('prob_under',    'odds_under',    'Under 2.5')],
    'btts':           [('prob_btts_yes', 'odds_btts_yes', 'BTTS Yes'),
                       ('prob_btts_no',  'odds_btts_no',  'BTTS No')],
}


# ──────────────────────────────────────────────────────────────────────────────
# Configuration dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BetSlipConfig:
    """
    Complete configuration for the bet-slip builder.
    All parameters include their valid range and a plain-English description.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  SCOPE — what data to consider                                          │
    └─────────────────────────────────────────────────────────────────────────┘
    date_from / date_to         : ISO date strings ('YYYY-MM-DD') to restrict
                                  which matches are considered. None = no limit.

    excluded_urls               : Match result URLs to skip entirely
                                  (e.g. matches already added to another slip).

    included_market_types       : Which market types to allow.
                                  Options: 'result', 'over_under_2.5', 'btts'
                                  None = all markets enabled.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  BET SHAPE — what the slip looks like                                   │
    └─────────────────────────────────────────────────────────────────────────┘
    target_odds     [1.10 – 1000.0]  : Desired cumulative odds for the full slip.
                                       The algorithm stops as soon as it gets
                                       close enough (see stop_threshold).

    target_legs     [1 – 10]         : Desired number of selections on the slip.
                                       The algorithm may add one or two extra legs
                                       if it helps hit the target odds more cleanly
                                       (see max_legs_overflow).

    max_legs_overflow [0 – 5]        : How many extra legs beyond target_legs are
                                       allowed. None = auto (0 for singles,
                                       +1 for 2–4 legs, +2 for 5+ legs).

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  QUALITY GATE — minimum bar to be considered at all                     │
    └─────────────────────────────────────────────────────────────────────────┘
    probability_floor [0.0 – 100.0]  : Minimum prediction confidence (%).
                                       Picks below this are discarded before
                                       any scoring takes place.
                                       Example: 55.0 = only consider picks where
                                       55 %+ of historical scores agree.

    min_odds          [1.01 – 10.0]  : Minimum bookmaker odds to consider.
                                       Filters out near-certain outcomes where
                                       the margin makes the bet unattractive.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  ODDS TOLERANCE — how tightly to track the per-leg target               │
    └─────────────────────────────────────────────────────────────────────────┘
    tolerance_factor  [0.05 – 0.80]  : ± band around the ideal per-leg odds.
                                       A pick is "Tier 1 balanced" when its odds
                                       sit within this band; otherwise "Tier 2".
                                       Tier 1 picks always rank above Tier 2 ones.
                                       Example: 0.25 = ±25 % of the ideal odds.
                                       None = auto-derived (wider for few legs,
                                       tighter for many to prevent drift).

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  STOP CONDITION — when to declare the slip complete                     │
    └─────────────────────────────────────────────────────────────────────────┘
    stop_threshold      [0.50 – 1.00]: The slip stops when
                                       current_odds ≥ target_odds × stop_threshold
                                       AND at least min_legs_fill_ratio of the
                                       target legs have been filled.
                                       0.95 = stop when within 5 % of target odds.
                                       None = auto-derived per target_legs.

    min_legs_fill_ratio [0.50 – 1.00]: Minimum fraction of target_legs that must
                                       be filled before early-stop is allowed.
                                       0.70 = need at least 70 % of legs filled.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  SCORING — how to rank candidate picks                                  │
    └─────────────────────────────────────────────────────────────────────────┘
    quality_vs_balance  [0.0 – 1.0]  : Trade-off between pick quality and odds
                                       balance. See module docstring for formula.
                                       0.0 = balance only (pure odds matching)
                                       0.5 = equal (default)
                                       1.0 = quality only (best prob/sources wins)

    prob_vs_sources     [0.0 – 1.0]  : Within the quality component, how much
                                       weight goes to probability vs data sources.
                                       0.0 = use sources only
                                       0.5 = equal (default)
                                       1.0 = use probability only
    """

    # Scope
    date_from:             Optional[str]       = None
    date_to:               Optional[str]       = None
    excluded_urls:         Optional[List[str]] = None
    included_market_types: Optional[List[str]] = None

    # Bet shape
    target_odds:           float        = 3.0       # [1.10 – 1000.0]
    target_legs:           int          = 3         # [1 – 10]
    max_legs_overflow:     Optional[int]= None      # [0 – 5] | None = auto

    # Quality gate
    probability_floor:     float        = 55.0      # [0.0 – 100.0]
    min_odds:              float        = 1.05      # [1.01 – 10.0]

    # Odds tolerance
    tolerance_factor:      Optional[float] = None   # [0.05 – 0.80] | None = auto

    # Stop condition
    stop_threshold:        Optional[float] = None   # [0.50 – 1.00] | None = auto
    min_legs_fill_ratio:   float           = 0.70   # [0.50 – 1.00]

    # Scoring
    quality_vs_balance:    float = 0.5              # [0.0 – 1.0]
    prob_vs_sources:       float = 0.5              # [0.0 – 1.0]

    def __post_init__(self):
        """Clamp all numeric fields to their documented valid ranges."""
        self.target_odds         = max(1.10,  min(1000.0, self.target_odds))
        self.target_legs         = max(1,     min(10,     self.target_legs))
        self.probability_floor   = max(0.0,   min(100.0,  self.probability_floor))
        self.min_odds            = max(1.01,  min(10.0,   self.min_odds))
        self.min_legs_fill_ratio = max(0.50,  min(1.00,   self.min_legs_fill_ratio))
        self.quality_vs_balance  = max(0.0,   min(1.0,    self.quality_vs_balance))
        self.prob_vs_sources     = max(0.0,   min(1.0,    self.prob_vs_sources))

        if self.tolerance_factor is not None:
            self.tolerance_factor = max(0.05, min(0.80, self.tolerance_factor))
        if self.stop_threshold is not None:
            self.stop_threshold = max(0.50, min(1.00, self.stop_threshold))
        if self.max_legs_overflow is not None:
            self.max_legs_overflow = max(0, min(5, self.max_legs_overflow))


# ──────────────────────────────────────────────────────────────────────────────
# Built-in risk profiles
# ──────────────────────────────────────────────────────────────────────────────

PROFILES: Dict[str, BetSlipConfig] = {

    # Safe, short-odds, high-confidence doubles.
    # Balance matters most — we want predictable, near-even odds per leg.
    'low_risk': BetSlipConfig(
        target_odds=2.0,
        target_legs=2,
        probability_floor=65.0,
        min_odds=1.10,
        quality_vs_balance=0.35,    # Lean toward balance
        prob_vs_sources=0.60,       # Probability slightly more important than sources
        tolerance_factor=0.20,      # ±20 % band — tight, we want near-even legs
        stop_threshold=0.95,
        min_legs_fill_ratio=0.80,
        included_market_types=['result', 'btts'],
    ),

    # Moderate accumulator. Balanced quality and odds shaping.
    'medium_risk': BetSlipConfig(
        target_odds=5.0,
        target_legs=3,
        probability_floor=55.0,
        quality_vs_balance=0.50,    # Equal weight
        prob_vs_sources=0.50,       # Equal weight
        # tolerance_factor & stop_threshold auto-derived
    ),

    # Larger accumulator. Quality over tight odds control — we want the best
    # picks available, and we accept that odds per leg may vary more.
    'high_risk': BetSlipConfig(
        target_odds=15.0,
        target_legs=5,
        probability_floor=50.0,
        quality_vs_balance=0.70,    # Lean toward quality
        prob_vs_sources=0.50,
        min_legs_fill_ratio=0.60,
        # tolerance_factor auto-derived (tighter for 5 legs, prevents drift)
    ),

    # Value-focused: prioritises well-sourced picks with odds above a floor.
    # Sources are heavily weighted to filter out poorly-covered matches.
    'value_hunter': BetSlipConfig(
        target_odds=8.0,
        target_legs=4,
        probability_floor=52.0,
        min_odds=1.30,              # Skip very short prices
        quality_vs_balance=0.65,
        prob_vs_sources=0.30,       # Sources dominate quality score
        min_legs_fill_ratio=0.65,
    ),
}


def get_profile(name: str) -> BetSlipConfig:
    """Return a deep copy of a named built-in profile, safe to modify."""
    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Available: {list(PROFILES)}")
    return copy.deepcopy(PROFILES[name])


# ──────────────────────────────────────────────────────────────────────────────
# Auto-derived config helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_tolerance(cfg: BetSlipConfig) -> float:
    """
    Wider band for few legs (less precision needed per leg),
    tighter for many legs (prevents cumulative drift from target odds).
    Curve: 1 leg → 0.40, 2 → 0.28, 3 → 0.23, 5 → 0.18, 10 → 0.13
    """
    if cfg.tolerance_factor is not None:
        return cfg.tolerance_factor
    return round(0.40 / (cfg.target_legs ** 0.5), 4)


def _resolve_stop_threshold(cfg: BetSlipConfig) -> float:
    """
    Stop close to target for singles/doubles (little room for error),
    accept slightly looser stop for longer accumulators.
    Curve: 1 leg → 0.98, 2 → 0.93, 3 → 0.91, 5 → 0.90, 10 → 0.89
    """
    if cfg.stop_threshold is not None:
        return cfg.stop_threshold
    return round(0.88 + (0.1 / cfg.target_legs), 4)


def _resolve_max_legs(cfg: BetSlipConfig) -> int:
    if cfg.max_legs_overflow is not None:
        return cfg.target_legs + cfg.max_legs_overflow
    if cfg.target_legs == 1:
        return 1
    if cfg.target_legs < 5:
        return cfg.target_legs + 1
    return cfg.target_legs + 2


# ──────────────────────────────────────────────────────────────────────────────
# Normalized scoring functions
# ──────────────────────────────────────────────────────────────────────────────

def _score_probability(prob: float, cfg: BetSlipConfig) -> float:
    """
    Normalize probability to [0, 1] relative to the quality gate.
    At the floor: 0.0. At 100 %: 1.0. Linear in between.
    """
    span = 100.0 - cfg.probability_floor
    if span <= 0:
        return 1.0
    return max(0.0, min(1.0, (prob - cfg.probability_floor) / span))


def _score_sources(sources: int, max_sources: int) -> float:
    """
    Normalize source count to [0, 1] relative to the highest-sourced
    candidate in the current pool. The best-covered match always scores 1.0;
    all others scale linearly down from it.
    """
    if max_sources <= 0:
        return 0.0
    return min(1.0, sources / max_sources)


def _score_balance(odds: float, ideal_odds: float, tolerance: float) -> float:
    """
    Normalize odds deviation to [0, 1].
    Perfect match (deviation = 0)       → 1.0
    At tolerance edge (deviation = tol) → 0.0
    Beyond tolerance                    → 0.0 (capped, not negative)
    Linear decay between 0 and tolerance.
    """
    relative_deviation = abs(odds - ideal_odds) / ideal_odds
    return max(0.0, 1.0 - (relative_deviation / tolerance))


def _score_pick(opt: dict, ideal_odds: float, max_sources: int,
                cfg: BetSlipConfig) -> Tuple[int, float]:
    tolerance = _resolve_tolerance(cfg)

    deviation = abs(opt['odds'] - ideal_odds) / ideal_odds
    tier = 1 if deviation <= tolerance else 2

    prob_score    = _score_probability(opt['prob'], cfg)
    sources_score = _score_sources(opt['sources'], max_sources)
    balance_score = _score_balance(opt['odds'], ideal_odds, tolerance)

    quality_score = (
        cfg.prob_vs_sources       * prob_score +
        (1 - cfg.prob_vs_sources) * sources_score
    )
    final_score = (
        cfg.quality_vs_balance       * quality_score +
        (1 - cfg.quality_vs_balance) * balance_score
    )
    return tier, round(final_score, 6)


# ──────────────────────────────────────────────────────────────────────────────
# Candidate collection
# ──────────────────────────────────────────────────────────────────────────────

def _collect_candidates(df: pd.DataFrame, cfg: BetSlipConfig) -> List[dict]:
    """
    Scan the full DataFrame and return every pick that clears the quality gate.
    Only date / URL / market / odds / probability filters are applied here.
    No scoring at this stage.
    """
    date_from = pd.to_datetime(cfg.date_from) if cfg.date_from else None
    date_to   = (pd.to_datetime(cfg.date_to) + pd.Timedelta(days=1)) if cfg.date_to else None
    excluded  = set(cfg.excluded_urls or [])
    markets   = cfg.included_market_types  # None = all

    candidates = []
    for _, row in df.iterrows():
        if date_from and row['datetime'] < date_from:
            continue
        if date_to and row['datetime'] >= date_to:
            continue
        if row['result_url'] is None:
            continue
        if row['result_url'] in excluded:
            continue

        match_name = f"{row['home']} vs {row['away']}"

        for m_type, market_cols in MARKET_MAP.items():
            if markets and m_type not in markets:
                continue
            for prob_col, odds_col, label in market_cols:
                prob = float(row.get(prob_col, 0))
                odds = float(row.get(odds_col, 0))
                if prob >= cfg.probability_floor and odds >= cfg.min_odds:
                    candidates.append({
                        'match':       match_name,
                        'market':      label,
                        'market_type': m_type,
                        'prob':        prob,
                        'odds':        odds,
                        'result_url':  row['result_url'],
                        'sources':     int(row['sources']),
                    })

    return candidates


# ──────────────────────────────────────────────────────────────────────────────
# Selection loop
# ──────────────────────────────────────────────────────────────────────────────

def _select_legs(candidates: List[dict], cfg: BetSlipConfig) -> List[dict]:
    stop_threshold = _resolve_stop_threshold(cfg)
    max_legs       = _resolve_max_legs(cfg)
    min_legs       = max(1, int(cfg.target_legs * cfg.min_legs_fill_ratio))

    # Compute once — normalizes all candidates relative to the best-covered match
    max_sources = max((c['sources'] for c in candidates), default=1)

    selected:     List[dict] = []
    seen_matches: set        = set()
    total_odds:   float      = 1.0

    while len(selected) < max_legs:
        if total_odds >= cfg.target_odds * stop_threshold and len(selected) >= min_legs:
            break

        remaining_target = cfg.target_odds / total_odds
        remaining_legs   = max(1, cfg.target_legs - len(selected))
        ideal_per_leg    = remaining_target ** (1.0 / remaining_legs)

        scored = []
        for opt in candidates:
            if opt['match'] in seen_matches:
                continue
            tier, score = _score_pick(opt, ideal_per_leg, max_sources, cfg)
            scored.append({**opt, 'tier': tier, 'score': score})

        if not scored:
            break

        scored.sort(key=lambda x: (x['tier'], -x['score']))
        best = scored[0]

        selected.append(best)
        seen_matches.add(best['match'])
        total_odds *= best['odds']

    return selected


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────

class BettingAnalyzer:
    """Analyzes match data, filters it, and builds bet slips."""

    def __init__(self, database_manager):
        self.db_manager = database_manager
        self.df = pd.DataFrame()

    # ── Data layer ────────────────────────────────────────────────────────────

    def refresh_data(self) -> pd.DataFrame:
        """Fetch and flatten match data from the database into self.df."""
        raw_df = self.db_manager.fetch_matches()

        if raw_df.empty:
            self.df = pd.DataFrame()
            return self.df

        data = []
        for idx, row in raw_df.iterrows():
            try:
                match_key   = f"{row['home_name']}_{row['away_name']}_{row['datetime'].isoformat()}"
                match_id    = f"match_{idx}_{hashlib.md5(match_key.encode()).hexdigest()}"
                suggestions = self._calculate_suggestions_from_raw(row)
                dt          = row['datetime']
                odds_data   = row['odds'] or {}
                scores_data = row['scores']
                unique_sources = len({s.get('source', '') for s in scores_data if s.get('source')})

                data.append({
                    'match_id':      match_id,
                    'datetime':      dt,
                    'datetime_str':  dt.strftime('%Y-%m-%d %H:%M'),
                    'home':          row['home_name'],
                    'away':          row['away_name'],
                    'sources':       unique_sources,
                    'result_url':    row['result_url'],
                    # Probabilities
                    'prob_home':     suggestions['result']['home'],
                    'prob_draw':     suggestions['result']['draw'],
                    'prob_away':     suggestions['result']['away'],
                    'prob_over':     suggestions['over_under_2.5']['over'],
                    'prob_under':    suggestions['over_under_2.5']['under'],
                    'prob_btts_yes': suggestions['btts']['yes'],
                    'prob_btts_no':  suggestions['btts']['no'],
                    # Odds
                    'odds_home':     odds_data.get('home',   0.0),
                    'odds_draw':     odds_data.get('draw',   0.0),
                    'odds_away':     odds_data.get('away',   0.0),
                    'odds_over':     odds_data.get('over',   0.0),
                    'odds_under':    odds_data.get('under',  0.0),
                    'odds_btts_yes': odds_data.get('btts_y', 0.0),
                    'odds_btts_no':  odds_data.get('btts_n', 0.0),
                })

            except Exception as e:
                print(f"Error processing match {idx}: {e}")
                traceback.print_exc()

        self.df = pd.DataFrame(data)
        return self.df

    def get_filtered_matches(self,
                             search_text: Optional[str] = None,
                             date_from:   Optional[str] = None,
                             date_to:     Optional[str] = None,
                             min_sources: Optional[int] = None) -> pd.DataFrame:
        """Return a filtered view of the master DataFrame."""
        if self.df.empty:
            return self.df

        filtered = self.df.copy()

        if search_text:
            mask = (
                filtered['home'].str.contains(search_text, case=False, na=False) |
                filtered['away'].str.contains(search_text, case=False, na=False)
            )
            filtered = filtered[mask]

        if date_from:
            filtered = filtered[filtered['datetime'] >= pd.to_datetime(date_from)]

        if date_to:
            end = pd.to_datetime(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            filtered = filtered[filtered['datetime'] <= end]

        if min_sources and min_sources > 1:
            filtered = filtered[filtered['sources'] >= min_sources]

        return filtered

    # ── Bet-slip builder ──────────────────────────────────────────────────────

    def build_bet_slip(self, config: BetSlipConfig = BetSlipConfig()) -> List[Dict]:
        """
        Build and return a bet slip according to the supplied BetSlipConfig.

        Returns a list of selected picks (one dict per leg), each containing:
            match        — 'Home vs Away'
            market       — e.g. '1', 'X', 'Over 2.5', 'BTTS Yes'
            market_type  — 'result' | 'over_under_2.5' | 'btts'
            prob         — prediction confidence (%)
            odds         — bookmaker odds
            result_url   — match identifier
            sources      — number of data sources
            tier         — 1 (balanced) or 2 (outside tolerance band)
            score        — final normalized score [0.0 – 1.0]
        """
        if self.df.empty:
            return []

        candidates = _collect_candidates(self.df, config)
        if not candidates:
            return []

        return _select_legs(candidates, config)

    # ── Internal analytics ────────────────────────────────────────────────────

    def _calculate_suggestions_from_raw(self, row) -> Dict[str, Dict[str, float]]:
        """Compute result / over-under / BTTS probabilities from historical scores."""
        scores_data = row['scores']
        empty = {
            'result':         {'home': 0.0, 'draw': 0.0, 'away': 0.0},
            'over_under_2.5': {'over': 0.0, 'under': 0.0},
            'btts':           {'yes':  0.0, 'no':    0.0},
        }

        if not scores_data:
            return empty

        total      = len(scores_data)
        home_count = draw_count = away_count = 0
        over_count = under_count = 0
        btts_yes   = btts_no    = 0

        try:
            for s in scores_data:
                h = s.get('home', 0) or 0
                a = s.get('away', 0) or 0

                if   h > a: home_count += 1
                elif h < a: away_count += 1
                else:        draw_count += 1

                if h + a > 2.5: over_count  += 1
                else:            under_count += 1

                if h > 0 and a > 0: btts_yes += 1
                else:                btts_no  += 1

        except Exception as e:
            print(f"Error in suggestions calculation: {e}")
            return empty

        def pct(n: int) -> float:
            return round((n / total) * 100, 1) if total else 0.0

        return {
            'result':         {'home': pct(home_count), 'draw': pct(draw_count), 'away': pct(away_count)},
            'over_under_2.5': {'over': pct(over_count), 'under': pct(under_count)},
            'btts':           {'yes':  pct(btts_yes),   'no':    pct(btts_no)},
        }