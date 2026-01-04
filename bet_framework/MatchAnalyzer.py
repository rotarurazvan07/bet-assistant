"""
Refactored MatchAnalyzer - Simple percentage-based suggestions
"""

from typing import Dict, Any

# H2H and scoring constants
H2H_WIN_WEIGHT = 3
WIN_WEIGHT = 3
DRAW_WEIGHT = 1
LOSE_WEIGHT = -3
LEAGUE_POINTS_WEIGHT = 1


class MatchAnalyzer:
    """Analyze matches and provide discrepancy and percentage-based suggestions."""

    def __init__(self):
        pass

    def analyze_match(self, match) -> Dict[str, Any]:
        """Run full analysis and return dict with discrepancy and suggestions."""
        disc = self.discrepancy(match)
        suggs = self.suggestions(match)

        return {
            'discrepancy': disc,
            'suggestions': suggs
        }

    def discrepancy(self, match) -> Dict[str, Any]:
        """Calculate team score discrepancy."""

        try:
            def _team_score(team):
                lp = getattr(team, 'league_points', 0) or 0
                form = getattr(team, 'form', '') or ''
                if isinstance(form, (list, tuple)):
                    fcount = ''.join(form)
                else:
                    fcount = str(form)
                form_value = WIN_WEIGHT * fcount.count('W') + DRAW_WEIGHT * fcount.count('D') + LOSE_WEIGHT * fcount.count('L')
                return float(lp) + float(form_value)

            home_team_score = _team_score(match.home_team)
            away_team_score = _team_score(match.away_team)

            # Apply H2H bias if present
            preds = getattr(match, 'predictions', None)
            if preds and getattr(preds, 'h2h', None):
                h2h = preds.h2h
                h2h_home_wins = getattr(h2h, 'home', 0) or 0
                h2h_away_wins = getattr(h2h, 'away', 0) or 0
                h2h_bias = H2H_WIN_WEIGHT * (h2h_home_wins - h2h_away_wins)
                if h2h_bias < 0:
                    away_team_score += abs(h2h_bias)
                else:
                    home_team_score += h2h_bias

            base = abs(home_team_score - away_team_score)

            avg_home_prob = sum([prob.home for prob in preds.probabilities]) / len(preds.probabilities)
            avg_draw_prob = sum([prob.draw for prob in preds.probabilities]) / len(preds.probabilities)
            avg_away_prob = sum([prob.away for prob in preds.probabilities]) / len(preds.probabilities)
            pct = max(avg_home_prob, avg_away_prob) + avg_draw_prob

            suggestion = ""
            if avg_home_prob >= avg_away_prob:
                suggestion += "1X & "
            else:
                suggestion += "X2 & "

            avg_goals = sum([(score.home + score.away) for score in preds.scores]) / len(preds.scores)
            if (round(avg_goals) - 2) >= 3:
                suggestion += "3+"
            elif (round(avg_goals) - 2) <= 0:
                suggestion += "0-4"
            else:
                suggestion += str(round(avg_goals) - 2) + "-" + str(round(avg_goals) + 2)
        except Exception:
            base = 0.0
            pct = 0.0
            suggestion = ""
            home_team_score = 0.0
            away_team_score = 0.0

        return {
            'score': float(round(base, 2)),
            'pct': float(round(pct, 2)),
            'suggestion' : suggestion
        }

    def suggestions(self, match) -> Dict[str, Dict[str, float]]:
        """
        Return percentage-based suggestions from score predictions.

        Returns dict:
        {
            'result': {'home': %, 'draw': %, 'away': %},
            'over_under_2.5': {'over': %, 'under': %},
            'btts': {'yes': %, 'no': %}
        }
        """
        preds = getattr(match, 'predictions', None)
        scores = preds.scores if preds and getattr(preds, 'scores', None) else []

        if not scores:
            return {
                'result': {'home': 0.0, 'draw': 0.0, 'away': 0.0},
                'over_under_2.5': {'over': 0.0, 'under': 0.0},
                'btts': {'yes': 0.0, 'no': 0.0}
            }

        total = len(scores)
        home_count = draw_count = away_count = 0
        over_count = under_count = 0
        btts_yes_count = btts_no_count = 0

        try:
            for s in scores:
                h = getattr(s, 'home', 0) or 0
                a = getattr(s, 'away', 0) or 0

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
        except Exception:
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