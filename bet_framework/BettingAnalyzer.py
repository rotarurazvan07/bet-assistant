"""
BettingAnalyzer - Handles all data processing, filtering, calculations, and bet building
Optimized to work directly with DataFrame from database without Match object overhead.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import hashlib


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

    def build_bet_slip(self,
                      search_text: Optional[str] = None,
                      date_from: Optional[str] = None,
                      date_to: Optional[str] = None,
                      min_sources: Optional[int] = None,
                      leg_count: int = 5,
                      min_odds_val: float = 1.1,
                      max_odds_val: float = 10,
                      excluded_matches: Optional[List[str]] = None,
                      probability_floor = 50,
                      included_market_types: Optional[List[str]] = None) -> List[Dict]:

        filtered_df = self.get_filtered_matches(search_text, date_from, date_to, min_sources=min_sources)

        if filtered_df.empty:
            return []

        # Define all available markets
        market_map = {
            'result': [('prob_home', 'odds_home', '1'), ('prob_draw', 'odds_draw', 'X'), ('prob_away', 'odds_away', '2')],
            'over_under_2.5': [('prob_over', 'odds_over', 'Over 2.5'), ('prob_under', 'odds_under', 'Under 2.5')],
            'btts': [('prob_btts_yes', 'odds_btts_yes', 'BTTS Yes'), ('prob_btts_no', 'odds_btts_no', 'BTTS No')]
        }

        all_options = []

        # 1. BUILD THE FULL POOL (Ignore included_market_types here)
        for _, row in filtered_df.iterrows():
            match_name = f"{row['home']} vs {row['away']}"
            if excluded_matches and match_name in excluded_matches:
                continue

            # Iterate through EVERY market type in the map
            for m_type, markets in market_map.items():
                for prob_col, odds_col, label in markets:
                    prob = float(row.get(prob_col, 0))
                    odds = float(row.get(odds_col, 0))

                    if prob >= probability_floor:
                        all_options.append({
                            'match': match_name,
                            'market': label,
                            'market_type': m_type, # Store type to filter primaries later
                            'prob': prob,
                            'odds': odds
                        })

        if not all_options:
            return []

        builder_df = pd.DataFrame(all_options)

        # 2. FILTER PRIMARIES (Apply included_market_types + Odds here)
        if included_market_types:
            primary_candidates = builder_df[builder_df['market_type'].isin(included_market_types)]
        else:
            primary_candidates = builder_df.copy()

        primary_candidates = primary_candidates[
            (primary_candidates['odds'] >= (min_odds_val or 0)) &
            (primary_candidates['odds'] <= (max_odds_val or 10))
        ]

        if primary_candidates.empty:
            return []

        # Stable Sort for Primaries
        primary_candidates = primary_candidates.sort_values(
            by=['prob', 'odds'], ascending=[False, False]
        ).reset_index(drop=True)

        # Select Unique Matches for legs
        primaries = []
        seen_matches = set()
        for _, row in primary_candidates.iterrows():
            if len(primaries) >= (leg_count or 5):
                break
            if row['match'] not in seen_matches:
                primaries.append(row.to_dict())
                seen_matches.add(row['match'])

        # 3. GROUPING (Secondaries pull from the FULL builder_df)
        grouped_selections = []
        for p_bet in primaries:
            # Look in the full pool for this match
            match_pool = builder_df[builder_df['match'] == p_bet['match']]

            # Secondaries: Not the primary bet, must meet prob floor,
            # BUT ignores included_market_types
            secondaries = match_pool[
                (match_pool['market'] != p_bet['market']) &
                (match_pool['prob'] >= probability_floor)
            ].sort_values(by='prob', ascending=False).to_dict('records')

            grouped_selections.append({
                'primary': p_bet,
                'secondary': secondaries
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
