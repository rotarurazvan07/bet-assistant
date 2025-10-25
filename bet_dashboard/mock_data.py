from typing import Dict, List
import numpy as np
from datetime import datetime, timedelta

def generate_team_stats() -> Dict:
    """Generate random team statistics."""
    return {
        'form': ''.join(np.random.choice(['W', 'D', 'L'], size=5)),
        'goals_for': int(np.random.uniform(15, 35)),
        'goals_against': int(np.random.uniform(10, 30)),
        'clean_sheets': int(np.random.uniform(3, 10)),
        'win_rate': round(np.random.uniform(30, 70), 1),
        'avg_corners': round(np.random.uniform(4, 8), 1),
        'avg_offsides': round(np.random.uniform(1, 4), 1),
        'avg_gk_saves': round(np.random.uniform(2, 5), 1),
        'avg_yellow_cards': round(np.random.uniform(1, 3), 1),
        'avg_fouls': round(np.random.uniform(8, 15), 1),
        'avg_tackles': round(np.random.uniform(15, 25), 1),
        'avg_scored': round(np.random.uniform(1, 3), 1),
        'avg_conceded': round(np.random.uniform(0.5, 2), 1),
        'avg_shots_on_target': round(np.random.uniform(4, 8), 1),
        'avg_possession': f"{round(np.random.uniform(45, 65), 1)}%"
    }

def generate_predictions() -> List[Dict]:
    """Generate random match score predictions."""
    sources = ['Forebet', 'WhoScored', 'FootyStats', 'Predictz', 'WinDrawWin']
    predictions = []

    for source in sources:
        home_goals = np.random.randint(0, 5)
        away_goals = np.random.randint(0, 5)

        predictions.append({
            'source': source,
            'predicted_score': f"{home_goals}-{away_goals}",
            'predicted_outcome': 'Home Win' if home_goals > away_goals else 'Draw' if home_goals == away_goals else 'Away Win'
        })

    return predictions

def generate_tips() -> List[Dict]:
    """Generate random betting tips with odds and probabilities."""
    tip_sources = ['FreeSuperTips', 'OLBG', 'FootballBettingTips', 'FreeTips']
    tips = []

    for source in tip_sources:
        # Generate match outcome probabilities
        home_prob = round(np.random.uniform(20, 60), 1)
        draw_prob = round(np.random.uniform(15, 35), 1)
        away_prob = round(100 - home_prob - draw_prob, 1)

        # Generate goal market probabilities
        over_prob = round(np.random.uniform(30, 70), 1)
        btts_prob = round(np.random.uniform(40, 80), 1)

        tips.extend([
            {
                'source': source,
                'market': 'Match Result',
                'selection': '1',
                'probability': home_prob,
                'odds': round(100/home_prob, 2) * 0.9,  # Applying bookmaker margin
                'confidence': round(home_prob / 2 + np.random.uniform(0, 20), 1)
            },
            {
                'source': source,
                'market': 'Match Result',
                'selection': 'X',
                'probability': draw_prob,
                'odds': round(100/draw_prob, 2) * 0.9,
                'confidence': round(draw_prob / 2 + np.random.uniform(0, 20), 1)
            },
            {
                'source': source,
                'market': 'Match Result',
                'selection': '2',
                'probability': away_prob,
                'odds': round(100/away_prob, 2) * 0.9,
                'confidence': round(away_prob / 2 + np.random.uniform(0, 20), 1)
            },
            {
                'source': source,
                'market': 'Goals Over/Under',
                'selection': 'Over 2.5',
                'probability': over_prob,
                'odds': round(100/over_prob, 2) * 0.9,
                'confidence': round(over_prob / 2 + np.random.uniform(0, 20), 1)
            },
            {
                'source': source,
                'market': 'Both Teams to Score',
                'selection': 'Yes',
                'probability': btts_prob,
                'odds': round(100/btts_prob, 2) * 0.9,
                'confidence': round(btts_prob / 2 + np.random.uniform(0, 20), 1)
            }
        ])

        return tips

def generate_h2h() -> Dict:
    """Generate random head-to-head statistics."""
    return {
        'home_wins': np.random.randint(1, 8),
        'draws': np.random.randint(1, 5),
        'away_wins': np.random.randint(1, 8)
    }

def create_mock_matches() -> List[Dict]:
    """Generate mock match data for testing."""
    teams = [
        ("Manchester United", "Arsenal"),
        ("Liverpool", "Chelsea"),
        ("Barcelona", "Real Madrid"),
        ("Bayern Munich", "Borussia Dortmund"),
        ("PSG", "Lyon"),
        ("Inter Milan", "AC Milan"),
        ("Ajax", "PSV"),
        ("Porto", "Benfica")
    ]

    matches = []
    for home, away in teams:
        # Generate all match data
        predictions = generate_predictions()
        tips = generate_tips()

        match = {
            # Basic match info
            'home_team': home,
            'away_team': away,
            'date': (datetime.now() + timedelta(days=np.random.randint(1, 14))).strftime('%Y-%m-%d'),
            'competition': np.random.choice(['Premier League', 'La Liga', 'Bundesliga', 'Serie A', 'Ligue 1']),

            # Team Statistics
            'home_stats': generate_team_stats(),
            'away_stats': generate_team_stats(),

            # Predictions, tips and H2H
            'predictions': predictions,
            'tips': tips,
            'h2h': generate_h2h(),

            # Derived fields for table display
            'consensus_score': max(set(p['predicted_score'] for p in predictions),
                                 key=lambda x: list(p['predicted_score'] for p in predictions).count(x)),
            'consensus_outcome': max(set(p['predicted_outcome'] for p in predictions),
                                  key=lambda x: list(p['predicted_outcome'] for p in predictions).count(x)),
            'best_value_tip': max(tips, key=lambda x: x['probability']/100 - 1/x['odds'])['selection'],
            'best_value_odds': max(tips, key=lambda x: x['probability']/100 - 1/x['odds'])['odds'],
            'best_value_market': max(tips, key=lambda x: x['probability']/100 - 1/x['odds'])['market'],
            'highest_prob_tip': max(tips, key=lambda x: x['probability'])['selection'],
            'highest_prob': max(tips, key=lambda x: x['probability'])['probability']
        }
        matches.append(match)

    return matches