import dash
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import pandas as pd

from bet_dashboard.mock_data import create_mock_matches
from bet_dashboard.components import create_match_details_card

# Initialize the app with a modern theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

# Create and process mock data
matches = create_mock_matches()
# Store the full data for details view
full_data = matches.copy()

# Flatten the data for the table view by keeping only the top-level and derived fields
table_data = [{
    'date': m['date'],
    'competition': m['competition'],
    'home_team': m['home_team'],
    'away_team': m['away_team'],
    'consensus_score': m['consensus_score'],
    'consensus_outcome': m['consensus_outcome'],
    'best_value_tip': m['best_value_tip'],
    'best_value_market': m['best_value_market'],
    'best_value_odds': f"{m['best_value_odds']:.2f}",
    'highest_prob': f"{m['highest_prob']:.1f}%"
} for m in matches]

df = pd.DataFrame(table_data)

# Layout definition
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H1("Bet Assistant Dashboard", className="text-primary text-center mb-4 mt-4"),
            html.H4("Match Analysis and Predictions", className="text-secondary text-center mb-4")
        ])
    ]),

    # Main matches table
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Upcoming Matches"),
                dbc.CardBody([
                    dash_table.DataTable(
                        id='matches-table',
                        columns=[
                            {'name': 'Date', 'id': 'date'},
                            {'name': 'Competition', 'id': 'competition'},
                            {'name': 'Home Team', 'id': 'home_team'},
                            {'name': 'Away Team', 'id': 'away_team'},
                            {'name': 'Predicted Score', 'id': 'consensus_score'},
                            {'name': 'Predicted Outcome', 'id': 'consensus_outcome'},
                            {'name': 'Best Value Tip', 'id': 'best_value_tip'},
                            {'name': 'Market', 'id': 'best_value_market'},
                            {'name': 'Odds', 'id': 'best_value_odds'},
                            {'name': 'Highest Prob', 'id': 'highest_prob'}
                        ],
                        data=df.to_dict('records'),
                        sort_action='native',
                        style_header={
                            'backgroundColor': 'rgb(30, 30, 30)',
                            'color': 'white',
                            'fontWeight': 'bold'
                        },
                        style_data={
                            'backgroundColor': 'rgb(50, 50, 50)',
                            'color': 'white'
                        },
                        style_data_conditional=[{
                            'if': {'state': 'selected'},
                            'backgroundColor': 'rgba(0, 116, 217, 0.3)',
                            'border': '1px solid blue'
                        }],
                        row_selectable='single',
                        selected_rows=[],
                        page_size=10
                    )
                ])
            ], className="mb-4")
        ])
    ]),

    # Match details section (populated by callback)
    dbc.Row([
        dbc.Col([
            html.Div(id='match-details')
        ])
    ])
], fluid=True)

@app.callback(
    Output('match-details', 'children'),
    [Input('matches-table', 'selected_rows')]
)
def display_match_details(selected_rows):
    """Update the match details section when a row is selected."""
    if not selected_rows:
        return html.Div()
    return create_match_details_card(full_data[selected_rows[0]])

if __name__ == '__main__':
    app.run(debug=True, port=8050)