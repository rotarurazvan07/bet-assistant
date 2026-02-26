"""
BettingAnalyzer - Handles all data processing, filtering, calculations, and bet building
Optimized to work directly with DataFrame from database without Match object overhead.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import hashlib

from bet_framework.SettingsManager import settings_manager


class BettingAnalyzer:
    """Analyzes matches, filters data, builds bets - all data manipulation logic."""

    def __init__(self, database_manager):
        self.db_manager = database_manager
        self.df = pd.DataFrame()

    def refresh_data(self) -> pd.DataFrame:
        """
        Refresh data from database - OPTIMIZED VERSION.
        Uses fetch_matches() to skip Match object overhead.
        """
        # Get optimized DataFrame directly from database
        raw_df = self.db_manager.fetch_matches()

        if raw_df.empty:
            self.df = pd.DataFrame()
            return self.df

        data = []

        for idx, row in raw_df.iterrows():
            try:
                # Generate stable ID
                match_key = f"{row['home_name']}_{row['away_name']}_{row['datetime'].isoformat()}"
                match_id = f"match_{idx}_{hashlib.md5(match_key.encode()).hexdigest()}"

                # Run analysis logic using the raw data
                suggestions_data = self._calculate_suggestions_from_raw(row)

                # Extract timestamps and odds
                dt = row['datetime']
                odds_data = row['odds']

                # Count unique sources from scores
                scores_data = row['scores']
                unique_sources = len(set(s.get('source', '') for s in scores_data if s.get('source')))

                # Flatten data into a single dictionary
                result_row = {
                    'match_id': match_id,
                    'datetime': dt,
                    'datetime_str': dt.strftime('%Y-%m-%d %H:%M'),
                    'home': row['home_name'],
                    'away': row['away_name'],
                    'sources': unique_sources,
                    'result_url': row['result_url'],

                    # Probability Data (from suggestions)
                    'prob_home': suggestions_data['result']['home'],
                    'prob_draw': suggestions_data['result']['draw'],
                    'prob_away': suggestions_data['result']['away'],
                    'prob_over': suggestions_data['over_under_2.5']['over'],
                    'prob_under': suggestions_data['over_under_2.5']['under'],
                    'prob_btts_yes': suggestions_data['btts']['yes'],
                    'prob_btts_no': suggestions_data['btts']['no'],

                    # Raw Odds Data (Stored for calculations/filtering)
                    'odds_home': odds_data.get('home', 0.0) if odds_data else 0.0,
                    'odds_draw': odds_data.get('draw', 0.0) if odds_data else 0.0,
                    'odds_away': odds_data.get('away', 0.0) if odds_data else 0.0,
                    'odds_over': odds_data.get('over', 0.0) if odds_data else 0.0,
                    'odds_under': odds_data.get('under', 0.0) if odds_data else 0.0,
                    'odds_btts_yes': odds_data.get('btts_y', 0.0) if odds_data else 0.0,
                    'odds_btts_no': odds_data.get('btts_n', 0.0) if odds_data else 0.0,
                }

                data.append(result_row)

            except Exception as e:
                print(f"Error processing match in refresh: {e}")
                import traceback
                traceback.print_exc()
                continue

        self.df = pd.DataFrame(data)
        return self.df

    def get_filtered_matches(self,
                           search_text: Optional[str] = None,
                           date_from: Optional[str] = None,
                           date_to: Optional[str] = None,
                           min_sources: Optional[int] = None) -> pd.DataFrame:
        """
        Internal method to generate a filtered view of the master DataFrame.
        """
        if self.df.empty:
            return self.df

        filtered_df = self.df.copy()

        # Apply search filter
        if search_text:
            mask = filtered_df['home'].str.contains(search_text, case=False, na=False) | \
                   filtered_df['away'].str.contains(search_text, case=False, na=False)
            filtered_df = filtered_df[mask]

        # Apply date filters
        if date_from:
            filtered_df = filtered_df[filtered_df['datetime'] >= pd.to_datetime(date_from)]

        if date_to:
            end_date = pd.to_datetime(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            filtered_df = filtered_df[filtered_df['datetime'] <= end_date]

        # Apply sources filter
        if min_sources and min_sources > 1:
            filtered_df = filtered_df[filtered_df['sources'] >= min_sources]

        return filtered_df

    def generate_bet_slip_low_risk(self, excluded_urls):
        profiles = settings_manager.get_config('betting_profiles') or {}
        prof = profiles.get('betting_profiles', {}).get('low', {
            'target_odds': 1.60, 'target_legs': 1, 'max_legs': 1,
            'min_odds': 1.50, 'max_odds': 1.70, 'prob_floor': 60.0
        })
        max_available_sources = int(self.df['sources'].max()) if not self.df.empty else 1

        slip = self.build_bet_slip(
            date_from=pd.Timestamp.now().normalize(),
            date_to=pd.Timestamp.now().normalize() + pd.Timedelta(days=7),
            min_sources=max_available_sources,
            target_odds=prof.get('target_odds', 1.60),
            target_legs=prof.get('target_legs', 1),
            max_legs=prof.get('max_legs', 1),
            min_odds_val=prof.get('min_odds', 1.50),
            max_odds_val=prof.get('max_odds', 1.70),
            probability_floor=prof.get('prob_floor', 60.0),
            excluded_urls=excluded_urls
        )
        return [bet['primary'] for bet in slip]

    def generate_bet_slip_medium_risk(self, excluded_urls):
        profiles = settings_manager.get_config('betting_profiles') or {}
        # User defined: 2-3 legs, Odds 3.00-5.00
        prof = profiles.get('betting_profiles', {}).get('med', {
            'target_odds': 4.0, 'target_legs': 3, 'max_legs': 3,
            'min_odds': None, 'max_odds': None, 'prob_floor': 50.0
        })

        slip = self.build_bet_slip(
            date_from=pd.Timestamp.now().normalize(),
            date_to=pd.Timestamp.now().normalize() + pd.Timedelta(days=7),
            target_odds=prof.get('target_odds', 4.0),
            target_legs=prof.get('target_legs', 3),
            max_legs=prof.get('max_legs', 3),
            min_odds_val=prof.get('min_odds'),
            max_odds_val=prof.get('max_odds'),
            probability_floor=prof.get('prob_floor', 50.0),
            excluded_urls=excluded_urls
        )
        return [bet['primary'] for bet in slip]

    def generate_bet_slip_high_risk(self, excluded_urls):
        profiles = settings_manager.get_config('betting_profiles') or {}
        # User defined: 5-6 Legs, Odds 15.00+, Avoid 9+ legs.
        prof = profiles.get('betting_profiles', {}).get('high', {
            'target_odds': 15.0, 'target_legs': 6, 'max_legs': 8,
            'min_odds': None, 'max_odds': None, 'prob_floor': 40.0
        })

        slip = self.build_bet_slip(
            date_from=pd.Timestamp.now().normalize(),
            date_to=pd.Timestamp.now().normalize() + pd.Timedelta(days=7),
            target_odds=prof.get('target_odds', 15.0),
            target_legs=prof.get('target_legs', 6),
            max_legs=prof.get('max_legs', 8),
            min_odds_val=prof.get('min_odds'),
            max_odds_val=prof.get('max_odds'),
            probability_floor=prof.get('prob_floor', 40.0),
            excluded_urls=excluded_urls
        )
        return [bet['primary'] for bet in slip]

    def build_bet_slip(self,
                      search_text: Optional[str] = None,
                      date_from: Optional[str] = None,
                      date_to: Optional[str] = None,
                      min_sources: Optional[int] = None,  # Can still be provided by UI explicitly
                      target_odds: float = 2.0,
                      target_legs: int = 2,
                      max_legs: Optional[int] = None,
                      min_odds_val: Optional[float] = None,
                      max_odds_val: Optional[float] = None,
                      excluded_urls: Optional[List[str]] = None,
                      probability_floor: float = 50.0,
                      included_market_types: Optional[List[str]] = None) -> List[Dict]:

        # Determine the maximum available sources in the DB
        max_available_sources = int(self.df['sources'].max()) if not self.df.empty else 1

        # Always start from the absolute max available to find the most trustworthy matches first
        start_sources = max_available_sources

        # If UI provided a strict min_sources, that acts as our hard floor (we stop searching if we reach it).
        # Otherwise, for automatic generation, we go down to 1 if necessary to hit target odds.
        floor_sources = min_sources if min_sources is not None else 1
        floor_sources = max(1, floor_sources)

        # Define all available markets
        market_map = {
            'result': [('prob_home', 'odds_home', '1'), ('prob_draw', 'odds_draw', 'X'), ('prob_away', 'odds_away', '2')],
            'over_under_2.5': [('prob_over', 'odds_over', 'Over 2.5'), ('prob_under', 'odds_under', 'Under 2.5')],
            'btts': [('prob_btts_yes', 'odds_btts_yes', 'BTTS Yes'), ('prob_btts_no', 'odds_btts_no', 'BTTS No')]
        }

        # We will collect picks here
        primaries = []
        seen_matches = set()
        current_total_odds = 1.0

        # Helper dictionary to keep tracking full choices for secondary bets
        full_match_pool = {}

        # Iterative Top-Down Source Logic
        for current_min_sources in range(start_sources, floor_sources - 1, -1):
            if current_total_odds >= target_odds and len(primaries) >= 1:
                break # We reached the target!

            # Grab dataframe filtered to AT LEAST current_min_sources
            # (Note get_filtered_matches does >= min_sources under the hood)
            filtered_df = self.get_filtered_matches(search_text, date_from, date_to, min_sources=current_min_sources)

            if filtered_df.empty:
                continue

            all_options = []

            # Extract market options
            for _, row in filtered_df.iterrows():
                match_name = f"{row['home']} vs {row['away']}"
                if row['result_url'] is None:
                    continue
                if excluded_urls and row['result_url'] in excluded_urls:
                    continue
                if match_name in seen_matches:
                    continue # Already selected from a higher source tier

                for m_type, markets in market_map.items():
                    # Filter based on included markets if specified by UI
                    if included_market_types and m_type not in included_market_types:
                        continue

                    for prob_col, odds_col, label in markets:
                        prob = float(row.get(prob_col, 0))
                        odds = float(row.get(odds_col, 0))

                        # Apply hard bounds on odds if supplied
                        if min_odds_val is not None and odds < min_odds_val:
                            continue
                        if max_odds_val is not None and odds > max_odds_val:
                            continue

                        # Strict floor - we don't want terrible bets, and odds must be > 1.0
                        if prob >= probability_floor and odds > 1.0:
                            all_options.append({
                                'match': match_name,
                                'market': label,
                                'market_type': m_type,
                                'prob': prob,
                                'odds': odds,
                                'result_url': row['result_url'],
                                'sources': row['sources'] # Store for info
                            })

                            # Cache every single acceptable option for secondary generation later
                            if match_name not in full_match_pool:
                                full_match_pool[match_name] = []
                            full_match_pool[match_name].append({
                                'market': label, 'prob': prob, 'odds': odds
                            })

            if not all_options:
                continue

            # Convert to DataFrame to sort cleanly
            options_df = pd.DataFrame(all_options)

            # Sort by Probability (Trust) -> then by highest Odds (Value) -> then by most Sources
            options_df = options_df.sort_values(
                by=['prob', 'odds', 'sources'], ascending=[False, False, False]
            ).reset_index(drop=True)

            # Greedily add to our slip
            for _, row in options_df.iterrows():
                # Check if we should stop
                if current_total_odds >= target_odds and len(primaries) >= max(1, target_legs // 2):
                    break

                # Hard limit just in case
                if max_legs is not None and len(primaries) >= max_legs:
                    break
                elif max_legs is None and len(primaries) >= target_legs + 2:
                    break

                if row['match'] not in seen_matches:
                    primaries.append(row.to_dict())
                    seen_matches.add(row['match'])
                    current_total_odds *= row['odds']

        # 3. GROUPING (Secondaries)
        grouped_selections = []
        for p_bet in primaries:
            match_name = p_bet['match']
            secondaries = []
            if match_name in full_match_pool:
                # Filter out the primary market from secondaries and sort by prob
                secondaries = [
                    opt for opt in full_match_pool[match_name]
                    if opt['market'] != p_bet['market']
                ]
                secondaries.sort(key=lambda x: x['prob'], reverse=True)

            grouped_selections.append({
                'primary': p_bet,
                'secondary': secondaries,
                'result_url': p_bet['result_url']
            })

        return grouped_selections

    def _calculate_suggestions_from_raw(self, row) -> Dict[str, Dict[str, float]]:
        """
        Return percentage-based suggestions from raw DataFrame row.
        Optimized version that works with dictionaries instead of Match objects.
        """
        scores_data = row['scores']

        if not scores_data or len(scores_data) == 0:
            return {
                'result': {'home': 0.0, 'draw': 0.0, 'away': 0.0},
                'over_under_2.5': {'over': 0.0, 'under': 0.0},
                'btts': {'yes': 0.0, 'no': 0.0}
            }

        total = len(scores_data)
        home_count = draw_count = away_count = 0
        over_count = under_count = 0
        btts_yes_count = btts_no_count = 0

        try:
            for s in scores_data:
                h = s.get('home', 0) or 0
                a = s.get('away', 0) or 0

                # Result
                if h > a:
                    home_count += 1
                elif h < a:
                    away_count += 1
                else:
                    draw_count += 1

                # Over/Under 2.5
                goals = h + a
                if goals > 2.5:
                    over_count += 1
                else:
                    under_count += 1

                # BTTS
                if h > 0 and a > 0:
                    btts_yes_count += 1
                else:
                    btts_no_count += 1
        except Exception as e:
            print(f"Error in suggestions calculation: {e}")
            pass

        return {
            'result': {
                'home': round((home_count / total) * 100, 1) if total > 0 else 0.0,
                'draw': round((draw_count / total) * 100, 1) if total > 0 else 0.0,
                'away': round((away_count / total) * 100, 1) if total > 0 else 0.0,
            },
            'over_under_2.5': {
                'over': round((over_count / total) * 100, 1) if total > 0 else 0.0,
                'under': round((under_count / total) * 100, 1) if total > 0 else 0.0,
            },
            'btts': {
                'yes': round((btts_yes_count / total) * 100, 1) if total > 0 else 0.0,
                'no': round((btts_no_count / total) * 100, 1) if total > 0 else 0.0,
            }
        }
