from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc

def create_team_stats_table(match_data, team_type):
    """Create a table showing team statistics."""
    stats = match_data[f'{team_type}_stats']
    return dbc.Table([
        html.Tbody([
            html.Tr([html.Td("Form"), html.Td(stats['form'])]),
            html.Tr([html.Td("Goals For"), html.Td(stats['goals_for'])]),
            html.Tr([html.Td("Goals Against"), html.Td(stats['goals_against'])]),
            html.Tr([html.Td("Clean Sheets"), html.Td(stats['clean_sheets'])]),
            html.Tr([html.Td("Win Rate"), html.Td(f"{stats['win_rate']:.1f}%")])
        ])
    ], bordered=True, hover=True, size="sm")

def create_predictions_table(predictions):
    """Create a table showing match score predictions."""
    return dbc.Table([
        html.Thead([
            html.Tr([
                html.Th("Source"),
                html.Th("Predicted Score"),
                html.Th("Predicted Outcome")
            ])
        ]),
        html.Tbody([
            html.Tr([
                html.Td(pred['source']),
                html.Td(pred['predicted_score']),
                html.Td(pred['predicted_outcome'])
            ]) for pred in predictions
        ])
    ], bordered=True, hover=True, size="sm")

def create_tips_table(tips):
    """Create a table showing betting tips with probabilities and odds."""
    # Group tips by market
    market_tips = {}
    for tip in tips:
        market = tip['market']
        if market not in market_tips:
            market_tips[market] = []
        market_tips[market].append(tip)

    # Create tables for each market
    tables = []
    for market, market_tips_list in market_tips.items():
        tables.append(html.H6(market, className="mt-3"))
        tables.append(
            dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Source"),
                        html.Th("Selection"),
                        html.Th("Probability"),
                        html.Th("Odds"),
                        html.Th("Confidence"),
                        html.Th("Value")
                    ])
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td(tip['source']),
                        html.Td(tip['selection']),
                        html.Td(f"{tip['probability']:.1f}%"),
                        html.Td(f"{tip['odds']:.2f}"),
                        html.Td(f"{tip['confidence']:.1f}%"),
                        html.Td(f"{(tip['probability']/100 - 1/tip['odds'])*100:.1f}%")
                    ]) for tip in market_tips_list
                ])
            ], bordered=True, hover=True, size="sm")
        )
    return html.Div(tables)

def create_h2h_table(h2h):
    """Create a table showing head-to-head statistics."""
    return dbc.Table([
        html.Thead([
            html.Tr([html.Th("Home Wins"), html.Th("Draws"), html.Th("Away Wins")])
        ]),
        html.Tbody([
            html.Tr([
                html.Td(h2h['home_wins']),
                html.Td(h2h['draws']),
                html.Td(h2h['away_wins'])
            ])
        ])
    ], bordered=True, hover=True)

def create_match_details_card(match_data):
    """Create a detailed card view for a selected match."""
    return dbc.Card([
        dbc.CardHeader(f"Match Details: {match_data['home_team']} vs {match_data['away_team']}"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.H5("Home Team Statistics", className="text-primary"),
                    create_team_stats_table(match_data, 'home')
                ], md=6),
                dbc.Col([
                    html.H5("Away Team Statistics", className="text-primary"),
                    create_team_stats_table(match_data, 'away')
                ], md=6)
            ], className="mb-4"),
            dbc.Row([
                dbc.Col([
                    html.H5("Match Predictions", className="text-primary"),
                    create_predictions_table(match_data['predictions'])
                ], md=6),
                dbc.Col([
                    html.H5("Betting Tips", className="text-primary"),
                    create_tips_table(match_data['tips'])
                ], md=6)
            ], className="mb-4"),
            dbc.Row([
                dbc.Col([
                    html.H5("Head to Head Statistics", className="text-primary"),
                    create_h2h_table(match_data['h2h'])
                ], className="text-center")
            ])
        ])
    ], className="mb-4")