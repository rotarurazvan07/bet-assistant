from io import StringIO
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, Any
from itertools import combinations

from bet_framework.MatchAnalyzer import MatchAnalyzer

class MatchesDashboard:
    """Dashboard for visualizing betting matches."""

    def __init__(self, database_manager):
        self.db_manager = database_manager
        self.matches = []
        self.matches_dict = {}
        self.analyzer = MatchAnalyzer()
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True
        )
        self._setup_layout()
        self._setup_callbacks()

    def refresh_data(self):
        self.matches = self.db_manager.fetch_matches()
        self.matches_dict = {}
        return self._prepare_table_data()

    def _format_tip_cell(self, percentage, odds):
        """Format a tip cell with percentage and odds."""
        if odds is not None and odds >= 1:
            return f"{percentage}%\n{odds:.2f}"
        return f"{percentage}%"

    def _prepare_table_data(self) -> pd.DataFrame:
        """Prepare table data with stable match IDs based on match properties."""
        data = []
        for idx, match in enumerate(self.matches):
            # Create stable match_id using match properties instead of id()
            match_key = f"{match.home_team.name}_{match.away_team.name}_{getattr(match, 'datetime', datetime.now()).isoformat()}"
            match_id = f"match_{idx}_{hash(match_key)}"
            self.matches_dict[match_id] = match

            try:
                analysis = self.analyzer.analyze_match(match)
                discrepancy = analysis['discrepancy']['score']
                suggestions = analysis['suggestions']

                preds = getattr(match, 'predictions', None)
                scores = preds.scores if preds and getattr(preds, 'scores', None) else []
                unique_sources = len(set(getattr(s, 'source', '') for s in scores if getattr(s, 'source', None)))

                dt = getattr(match, 'datetime', datetime.now())

                # Get odds
                odds = getattr(match, 'odds', None)

                data.append({
                    'match_id': match_id,
                    'datetime': dt.strftime('%Y-%m-%d %H:%M'),
                    'home': match.home_team.name,
                    'away': match.away_team.name,
                    'discrepancy': round(discrepancy, 2),
                    'discrepancy_pct': analysis['discrepancy']['pct'],
                    'quick_suggestion': analysis['discrepancy']['suggestion'],
                    'sources': unique_sources,
                    'result_home': suggestions['result']['home'],
                    'result_draw': suggestions['result']['draw'],
                    'result_away': suggestions['result']['away'],
                    'over': suggestions['over_under_2.5']['over'],
                    'under': suggestions['over_under_2.5']['under'],
                    'btts_yes': suggestions['btts']['yes'],
                    'btts_no': suggestions['btts']['no'],
                    'timestamp': dt,
                    # Add odds with formatting
                    'result_home_display': self._format_tip_cell(suggestions['result']['home'], odds.home if odds else None),
                    'result_draw_display': self._format_tip_cell(suggestions['result']['draw'], odds.draw if odds else None),
                    'result_away_display': self._format_tip_cell(suggestions['result']['away'], odds.away if odds else None),
                    'over_display': self._format_tip_cell(suggestions['over_under_2.5']['over'], odds.over if odds else None),
                    'under_display': self._format_tip_cell(suggestions['over_under_2.5']['under'], odds.under if odds else None),
                    'btts_yes_display': self._format_tip_cell(suggestions['btts']['yes'], odds.btts_y if odds else None),
                    'btts_no_display': self._format_tip_cell(suggestions['btts']['no'], odds.btts_n if odds else None),
                })
            except Exception as e:
                print(f"Error processing match {match_id}: {e}")
                continue

        return pd.DataFrame(data)

    def _apply_common_filters(self, df, search_text=None, date_from=None, date_to=None, min_sources=None):
        """Apply common filters to dataframe and return filtered result."""
        if df.empty:
            return df

        filtered_df = df.copy()

        # Apply search filter
        if search_text:
            mask = filtered_df['home'].str.contains(search_text, case=False, na=False) | \
                   filtered_df['away'].str.contains(search_text, case=False, na=False)
            filtered_df = filtered_df[mask]

        # Apply date filters - inclusive of both start and end dates
        if date_from:
            # Start of the day for date_from
            filtered_df = filtered_df[filtered_df['timestamp'] >= pd.to_datetime(date_from)]

        if date_to:
            # End of the day for date_to (add 1 day minus 1 second)
            end_date = pd.to_datetime(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            filtered_df = filtered_df[filtered_df['timestamp'] <= end_date]

        # Apply sources filter
        if min_sources and min_sources > 1:
            filtered_df = filtered_df[filtered_df['sources'] >= min_sources]

        return filtered_df

    def _create_bet_builder(self, df, leg_count, min_odds_val):
        if df.empty:
            return [dbc.Alert("No matches match criteria.", color="warning")], []

        markets = [
            ('result_home', '1'), ('result_draw', 'X'), ('result_away', '2'),
            ('over', 'Over 2.5'), ('under', 'Under 2.5'),
            ('btts_yes', 'BTTS Yes'), ('btts_no', 'BTTS No')
        ]

        all_options = []
        for _, row in df.iterrows():
            match_obj = self.matches_dict.get(row['match_id'])
            odds_obj = getattr(match_obj, 'odds', None)
            odds_values = {
                '1': getattr(odds_obj, 'home', 1.0), 'X': getattr(odds_obj, 'draw', 1.0), '2': getattr(odds_obj, 'away', 1.0),
                'Over 2.5': getattr(odds_obj, 'over', 1.0), 'Under 2.5': getattr(odds_obj, 'under', 1.0),
                'BTTS Yes': getattr(odds_obj, 'btts_y', 1.0), 'BTTS No': getattr(odds_obj, 'btts_n', 1.0)
            }

            for prob_col, label in markets:
                odds = odds_values.get(label, 1.0)
                if odds >= (min_odds_val or 0):
                    all_options.append({
                        'match': f"{row['home']} vs {row['away']}",
                        'market': label,
                        'prob': row[prob_col],
                        'odds': odds
                    })

        if not all_options:
            return [dbc.Alert("No markets found.", color="info")], []

        builder_df = pd.DataFrame(all_options)
        # Sort: Confidence (Desc) then Odds (Desc)
        builder_df = builder_df.sort_values(by=['prob', 'odds'], ascending=[False, False]).head(leg_count)

        current_odds = builder_df['odds'].tolist()

        slip_items = [
            html.Div([
                html.Small(row['match'], className="text-muted d-block"),
                html.Div([
                    html.B(row['market']),
                    html.Span(f" @{row['odds']:.2f}", className="float-end text-primary fw-bold")
                ]),
                html.Div([
                    html.Span("Confidence: ", className="text-muted", style={"fontSize": "0.75rem"}),
                    html.B(f"{row['prob']}%", style={"color": "#27ae60", "fontSize": "0.8rem"})
                ], className="mt-1"),
                html.Hr(style={"borderTop": "1px dashed #ddd", "margin": "8px 0"})
            ]) for _, row in builder_df.iterrows()
        ]

        return slip_items, current_odds

    def _setup_layout(self):
        self.app.layout = dbc.Container([
            dcc.Store(id="current-match-id"),
            dcc.Store(id="max-sources", data=10),

            # Header with gradient
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H1([
                            html.I(className="fas fa-futbol me-3"),
                            "Betting Matches Dashboard"
                        ], className="text-white mb-2"),
                        html.P("Analyze and compare betting predictions",
                               className="text-white-50 mb-0",
                               style={"fontSize": "1.1rem"}),
                    ], className="text-center py-4",
                       style={
                           "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                           "borderRadius": "15px",
                           "boxShadow": "0 10px 30px rgba(0,0,0,0.2)"
                       })
                ])
            ], className="mb-4 mt-3"),

            # Filters Card
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # 1. Search Column (20%)
                        dbc.Col([
                            html.Label([
                                html.I(className="fas fa-search me-2 text-primary"),
                                "Search Team"
                            ], className="fw-bold mb-2", style={"fontSize": "0.9rem"}),
                            dbc.InputGroup([
                                dbc.InputGroupText(
                                    html.I(className="fas fa-search"),
                                    style={"background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                                        "color": "white", "border": "none"}
                                ),
                                dbc.Input(
                                    id="search-input",
                                    type="text",
                                    placeholder="Team name...",
                                    style={"borderLeft": "none"}
                                )
                            ], className="shadow-sm")
                        ], style={"width": "20%"}),

                        # 2. From Date (12.5%)
                        dbc.Col([
                            html.Label([
                                html.I(className="fas fa-calendar-alt me-2 text-success"),
                                "From"
                            ], className="fw-bold mb-2", style={"fontSize": "0.9rem"}),
                            dcc.DatePickerSingle(
                                id="date-from",
                                placeholder="Start",
                                display_format='YYYY-MM-DD',
                                className="shadow-sm",
                                style={'width': '100%'}
                            )
                        ], style={"width": "12.5%"}),

                        # 3. To Date (12.5%)
                        dbc.Col([
                            html.Label([
                                html.I(className="fas fa-calendar-check me-2 text-success"),
                                "To"
                            ], className="fw-bold mb-2", style={"fontSize": "0.9rem"}),
                            dcc.DatePickerSingle(
                                id="date-to",
                                placeholder="End",
                                display_format='YYYY-MM-DD',
                                className="shadow-sm",
                                style={'width': '100%'}
                            )
                        ], style={"width": "12.5%"}),

                        # 4. SHARED SLOT: Discrepancy Slider OR Min Sources Slider (40%)
                        dbc.Col([
                            # Container A: Discrepancy
                            html.Div([
                                html.Label([
                                    html.I(className="fas fa-filter me-2 text-warning"),
                                    "Min Discrepancy %"
                                ], className="fw-bold mb-2", style={"fontSize": "0.9rem"}),
                                dcc.Slider(
                                    id='discrepancy-filter-slider',
                                    min=0, max=100, step=5, value=80,
                                    marks={0: '0%', 25: '25%', 50: '50%', 75: '75%', 100: '100%'},
                                    tooltip={"placement": "bottom", "always_visible": True}
                                )
                            ], id="discrepancy-filter-container", style={"display": "block"}),

                            # Container B: Min Sources
                            html.Div([
                                html.Label([
                                    html.I(className="fas fa-layer-group me-2 text-info"),
                                    "Min Sources"
                                ], className="fw-bold mb-2", style={"fontSize": "0.9rem"}),
                                dcc.Slider(
                                    id='min-sources-slider',
                                    min=1, max=10, step=1, value=1,
                                    tooltip={"placement": "bottom", "always_visible": True}
                                )
                            ], id="sources-filter-container", style={"display": "none"})
                        ], style={"width": "40%"}),

                        # 5. Refresh Button (15%)
                        dbc.Col([
                            html.Label("\u00A0", className="fw-bold mb-2 d-block"),
                            dbc.Button(
                                [html.I(className="fas fa-sync-alt me-2"), "Refresh"],
                                id="refresh-btn",
                                className="w-100 shadow-sm",
                                style={
                                    "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                                    "border": "none",
                                    "fontWeight": "600"
                                }
                            )
                        ], style={"width": "15%"}),

                    ], align="center", className="g-2")
                ])
            ], className="mb-4 shadow", style={"borderRadius": "15px", "border": "none"}),

            dbc.Card([
                dbc.CardBody([
                    dbc.Tabs(
                        id='main-tabs',
                        active_tab='tab-disc',
                        className="nav-fill w-100",
                        children=[
                            dbc.Tab(
                                # Wrap the output in a Div inside the Tab
                                html.Div(id="discrepancy-table-container", className="mt-3"),
                                label="⚠️ Discrepancy Analysis",
                                tab_id='tab-disc',
                                label_style={"fontSize": "1rem", "fontWeight": "600", "width": "100%"},
                                active_label_style={"color": "#667eea", "borderBottom": "3px solid #667eea"}
                            ),
                            dbc.Tab(
                                html.Div(id="tips-table-container", className="mt-3"),
                                label="💡 Betting Tips",
                                tab_id='tab-tips',
                                label_style={"fontSize": "1rem", "fontWeight": "600", "width": "100%"},
                                active_label_style={"color": "#764ba2", "borderBottom": "3px solid #764ba2"}
                            ),
                            dbc.Tab(
                                html.Div([
                                    # persistent Store for the odds
                                    dcc.Store(id='builder-current-odds'),

                                    # 1. Settings Bar
                                    html.Div(id="builder-settings-container", children=[
                                        dbc.Row([
                                            dbc.Col(dbc.InputGroup([
                                                dbc.InputGroupText("Legs"),
                                                dbc.Input(id="builder-leg-count", type="number", value=5, min=1, max=15),
                                            ], size="sm"), width="auto"),
                                            dbc.Col(dbc.InputGroup([
                                                dbc.InputGroupText("Min Odds"),
                                                dbc.Input(id="builder-min-odds", type="number", value=1.2, min=1, step=0.1),
                                            ], size="sm"), width="auto"),
                                        ], justify="center", className="g-3 my-3")
                                    ]),

                                    # 2. Main Split View
                                    dbc.Row([
                                        # Left side: The List of Matches
                                        dbc.Col(dbc.Card([
                                            dbc.CardHeader("🎯 Optimized Bet Slip", className="text-center fw-bold bg-dark text-white"),
                                            dbc.CardBody(id="builder-output-container", style={ "overflowY": "auto"})
                                        ], className="border-0 shadow-sm"), md=6),

                                        # Right side: The Simulator UI
                                        dbc.Col(dbc.Card([
                                            dbc.CardHeader("🧮 System Bet Simulator", className="text-center fw-bold bg-success text-white"),
                                            dbc.CardBody([
                                                html.Label("Total Stake ($)", className="small fw-bold"),
                                                dbc.Input(id="sys-total-stake", type="number", value=100, min=1, className="mb-3"),

                                                html.Label("Select System Types:", className="small fw-bold"),
                                                dbc.Checklist(
                                                    id="sys-type",
                                                    options=[], # Populated via callback
                                                    value=[],   # Populated via callback
                                                    inline=True,
                                                    switch=True,
                                                    className="mb-3"
                                                ),
                                                html.Hr(),
                                                html.Div(id="sys-results-output")
                                            ])
                                        ], className="border-0 shadow-sm"), md=6)
                                    ], className="mt-3")
                                ], className="mt-3"),
                                label="🎯 Smart Bet Builder",
                                tab_id='tab-builder',
                                label_style={"fontSize": "1rem", "fontWeight": "600", "width": "100%"},
                                active_label_style={"color": "#27ae60", "borderBottom": "3px solid #27ae60"}
                            )
                        ]
                    )
                ], className="p-3")
            ], className="shadow", style={"borderRadius": "15px", "border": "none"}),

            # Modal
            dbc.Modal([
                dbc.ModalHeader(
                    dbc.ModalTitle(id="modal-title"),
                    close_button=True,
                    style={
                        "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                        "color": "white"
                    }
                ),
                dbc.ModalBody(id="modal-body", style={"maxHeight": "75vh", "overflowY": "auto"}),
                dbc.ModalFooter(
                    dbc.Button(
                        [html.I(className="fas fa-times me-2"), "Close"],
                        id="close-modal",
                        style={
                            "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                            "border": "none"
                        }
                    )
                ),
            ], id="match-modal", size="xl", scrollable=True),

            dcc.Store(id="matches-data-store"),

        ], fluid=True, className="p-4", style={
            "background": "linear-gradient(to bottom, #f8f9fa 0%, #e9ecef 100%)",
            "minHeight": "100vh"
        })

    def _create_discrepancy_table(self, df):
        if df.empty:
            return dbc.Alert(
                [html.I(className="fas fa-info-circle me-2"), "No matches found matching your criteria"],
                color="info",
                className="text-center m-4"
            )

        cols = ['match_id', 'datetime', 'home', 'away', 'discrepancy', 'discrepancy_pct', 'quick_suggestion']
        display_df = df[cols].copy()

        return dash_table.DataTable(
            id={'type': 'match-table', 'index': 'discrepancy'},
            columns=[
                {"name": "", "id": "match_id"},
                {"name": "Date & Time", "id": "datetime"},
                {"name": "Home Team", "id": "home"},
                {"name": "Away Team", "id": "away"},
                {"name": "Discrepancy", "id": "discrepancy", "type": "numeric"},
                {"name": "Disc %", "id": "discrepancy_pct", "type": "numeric"},
                {"name": "Quick Suggestion", "id": "quick_suggestion"},
            ],
            data=display_df.to_dict('records'),
            sort_action='native',
            sort_mode='multi',
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '15px',
                'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                'fontSize': '14px',
                'whiteSpace': 'normal',
                'height': 'auto',
            },
            style_cell_conditional=[
                {'if': {'column_id': 'match_id'}, 'display': 'none'},
                {'if': {'column_id': 'datetime'}, 'width': '140px', 'minWidth': '140px', 'maxWidth': '140px'},
                {'if': {'column_id': 'home'}, 'width': '180px', 'minWidth': '180px', 'maxWidth': '180px'},
                {'if': {'column_id': 'away'}, 'width': '180px', 'minWidth': '180px', 'maxWidth': '180px'},
                {'if': {'column_id': 'discrepancy'}, 'width': '100px', 'minWidth': '100px', 'maxWidth': '100px', 'textAlign': 'center'},
                {'if': {'column_id': 'discrepancy_pct'}, 'width': '80px', 'minWidth': '80px', 'maxWidth': '80px', 'textAlign': 'center'},
                {'if': {'column_id': 'quick_suggestion'}, 'width': '200px', 'minWidth': '200px', 'maxWidth': '200px'},
            ],
            style_header={
                'backgroundColor': '#667eea',
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center',
                'padding': '15px',
                'border': 'none',
            },
            style_data={
                'backgroundColor': 'white',
                'border': 'none',
                'borderBottom': '1px solid #e9ecef'
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'},
                {
                    'if': {'state': 'active'},
                    'backgroundColor': '#e3f2fd',
                    'border': '2px solid #667eea'
                },
                {
                    'if': {
                        'filter_query': '{discrepancy_pct} >= 90',
                        'column_id': 'discrepancy_pct'
                    },
                    'backgroundColor': '#d4edda',
                    'color': '#073F14',
                    'fontWeight': 'bold'
                },
                {
                    'if': {
                        'filter_query': '{discrepancy_pct} >= 80 && {discrepancy_pct} < 90',
                        'column_id': 'discrepancy_pct'
                    },
                    'backgroundColor': '#fff3cd',
                    'color': '#856404'
                },
            ],
            css=[{
                'selector': 'tr:hover td',
                'rule': 'background-color: #e3f2fd !important; cursor: pointer; transform: scale(1.01);'
            }],
            page_size=25,
            page_action='native',
        )

    def _create_tips_table(self, df):
        if df.empty:
            return dbc.Alert(
                [html.I(className="fas fa-info-circle me-2"), "No matches found matching your criteria"],
                color="info",
                className="text-center m-4"
            )

        cols = ['match_id', 'datetime', 'home', 'away', 'sources', 'result_home', 'result_home_display', 'result_draw',
                'result_draw_display', 'result_away', 'result_away_display', 'over', 'over_display',
                'under', 'under_display', 'btts_yes', 'btts_yes_display', 'btts_no', 'btts_no_display']
        display_df = df[cols].copy()

        return dash_table.DataTable(
            id={'type': 'match-table', 'index': 'tips'},
            columns=[
                {"name": "", "id": "match_id"},
                {"name": "Date & Time", "id": "datetime"},
                {"name": "Home Team", "id": "home"},
                {"name": "Away Team", "id": "away"},
                {"name": "1", "id": "result_home_display"},
                {"name": "X", "id": "result_draw_display"},
                {"name": "2", "id": "result_away_display"},
                {"name": "O2.5", "id": "over_display"},
                {"name": "U2.5", "id": "under_display"},
                {"name": "BTTS Y", "id": "btts_yes_display"},
                {"name": "BTTS N", "id": "btts_no_display"},
            ],
            data=display_df.to_dict('records'),
            sort_action='native',
            sort_mode='multi',
            sort_by=[{'column_id': 'result_home', 'direction': 'desc'}],
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'center',
                'padding': '15px',
                'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                'fontSize': '14px',
                'whiteSpace': 'pre-line',
                'height': 'auto',
            },
            style_cell_conditional=[
                {'if': {'column_id': 'match_id'}, 'display': 'none'},
                {'if': {'column_id': 'datetime'}, 'width': '120px', 'minWidth': '120px', 'maxWidth': '120px'},
                {'if': {'column_id': 'home'}, 'textAlign': 'left', 'width': '150px', 'minWidth': '150px', 'maxWidth': '150px'},
                {'if': {'column_id': 'away'}, 'textAlign': 'left', 'width': '150px', 'minWidth': '150px', 'maxWidth': '150px'},
                {'if': {'column_id': 'sources'}, 'width': '70px', 'minWidth': '70px', 'maxWidth': '70px'},
                {'if': {'column_id': 'result_home_display'}, 'width': '80px', 'minWidth': '80px', 'maxWidth': '80px'},
                {'if': {'column_id': 'result_draw_display'}, 'width': '80px', 'minWidth': '80px', 'maxWidth': '80px'},
                {'if': {'column_id': 'result_away_display'}, 'width': '80px', 'minWidth': '80px', 'maxWidth': '80px'},
                {'if': {'column_id': 'over_display'}, 'width': '80px', 'minWidth': '80px', 'maxWidth': '80px'},
                {'if': {'column_id': 'under_display'}, 'width': '80px', 'minWidth': '80px', 'maxWidth': '80px'},
                {'if': {'column_id': 'btts_yes_display'}, 'width': '90px', 'minWidth': '90px', 'maxWidth': '90px'},
                {'if': {'column_id': 'btts_no_display'}, 'width': '90px', 'minWidth': '90px', 'maxWidth': '90px'},
            ],
            style_header={
                'backgroundColor': '#764ba2',
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center',
                'padding': '15px',
                'border': 'none',
            },
            style_data={
                'backgroundColor': 'white',
                'border': 'none',
                'borderBottom': '1px solid #e9ecef'
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'},
                {
                    'if': {'state': 'active'},
                    'backgroundColor': '#f3e5f5',
                    'border': '2px solid #764ba2'
                },

                {
                    'if': {'column_id': 'btts_yes_display'},
                    'borderLeft': '3px solid #000000'
                },
                {
                    'if': {'column_id': 'over_display'},
                    'borderLeft': '3px solid #000000'
                },
                {
                    'if': {'column_id': 'result_home_display'},
                    'borderLeft': '3px solid #000000'
                },

                # Highlighting based on percentage values (using hidden columns for filtering)
                {
                    'if': {'filter_query': '{result_home} >= 80', 'column_id': 'result_home_display'},
                    'backgroundColor': "#4ce770", 'color': "#073F14", 'fontWeight': 'bold'
                },
                {
                    'if': {'filter_query': '{result_draw} >= 80', 'column_id': 'result_draw_display'},
                    'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'
                },
                {
                    'if': {'filter_query': '{result_away} >= 80', 'column_id': 'result_away_display'},
                    'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'
                },
                {
                    'if': {'filter_query': '{btts_yes} >= 80', 'column_id': 'btts_yes_display'},
                    'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'
                },
                {
                    'if': {'filter_query': '{btts_no} >= 80', 'column_id': 'btts_no_display'},
                    'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'
                },
                {
                    'if': {'filter_query': '{over} >= 80', 'column_id': 'over_display'},
                    'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'
                },
                {
                    'if': {'filter_query': '{under} >= 80', 'column_id': 'under_display'},
                    'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'
                },
            ],
            css=[{
                'selector': 'tr:hover td',
                'rule': 'background-color: #f3e5f5 !important; cursor: pointer; transform: scale(1.01);'
            }],
            page_size=25,
            page_action='native',
        )

    def _create_match_detail(self, match):
        """Create detailed match modal view."""
        try:
            analysis = self.analyzer.analyze_match(match)
            discrepancy = analysis['discrepancy']['score']
            suggestions = analysis['suggestions']

            preds = getattr(match, 'predictions', None)
            scores = preds.scores if preds and getattr(preds, 'scores', None) else []
            unique_sources = len(set(getattr(s, 'source', '') for s in scores if getattr(s, 'source', None)))
        except:
            return html.Div("Error loading match details")

        return html.Div([
            # Header
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{match.home_team.name} vs {match.away_team.name}", className="text-center mb-2"),
                    html.H5(match.datetime.strftime('%A, %B %d, %Y at %H:%M'), className="text-center text-white-50"),
                ])
            ], className="mb-4 text-white", style={"background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"}),

            # Overview Cards
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div(html.I(className="fas fa-exclamation-triangle fa-2x mb-2 text-warning"), className="text-center"),
                            html.H5("Discrepancy", className="text-center text-muted"),
                            html.H2(f"{discrepancy:.2f}", className="text-center text-warning mb-0")
                        ])
                    ], className="shadow-sm h-100")
                ], md=6),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div(html.I(className="fas fa-database fa-2x mb-2 text-primary"), className="text-center"),
                            html.H5("Sources", className="text-center text-muted"),
                            html.H2(unique_sources, className="text-center text-primary mb-0")
                        ])
                    ], className="shadow-sm h-100")
                ], md=6),
            ], className="mb-4"),

            # Suggestions
            html.H4([html.I(className="fas fa-chart-pie me-2"), "Predictions"], className="mb-3"),
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H6("Result", className="text-center mb-3"),
                            dbc.Progress([
                                dbc.Progress(value=suggestions['result']['home'], label=f"1: {suggestions['result']['home']}%", color="success", bar=True),
                                dbc.Progress(value=suggestions['result']['draw'], label=f"X: {suggestions['result']['draw']}%", color="warning", bar=True),
                                dbc.Progress(value=suggestions['result']['away'], label=f"2: {suggestions['result']['away']}%", color="info", bar=True),
                            ], style={"height": "35px"})
                        ], md=12, className="mb-4"),
                    ]),

                    dbc.Row([
                        dbc.Col([
                            html.H6("Over/Under 2.5", className="text-center mb-3"),
                            dbc.Progress([
                                dbc.Progress(value=suggestions['over_under_2.5']['over'], label=f"Over: {suggestions['over_under_2.5']['over']}%", color="danger", bar=True),
                                dbc.Progress(value=suggestions['over_under_2.5']['under'], label=f"Under: {suggestions['over_under_2.5']['under']}%", color="primary", bar=True),
                            ], style={"height": "35px"})
                        ], md=6),

                        dbc.Col([
                            html.H6("BTTS", className="text-center mb-3"),
                            dbc.Progress([
                                dbc.Progress(value=suggestions['btts']['yes'], label=f"Yes: {suggestions['btts']['yes']}%", color="success", bar=True),
                                dbc.Progress(value=suggestions['btts']['no'], label=f"No: {suggestions['btts']['no']}%", color="secondary", bar=True),
                            ], style={"height": "35px"})
                        ], md=6),
                    ]),
                ])
            ], className="shadow-sm")
        ])

    def _setup_callbacks(self):
        @self.app.callback(
            [
                Output("matches-data-store", "data"),
                Output("max-sources", "data"),
            ],
            Input("refresh-btn", "n_clicks"),
            prevent_initial_call=False
        )
        def refresh_data(n_clicks):
            df = self.refresh_data()
            max_sources = int(df['sources'].max()) if not df.empty else 10
            return df.to_json(date_format='iso', orient='split'), max_sources

        @self.app.callback(
            Output("min-sources-slider", "max"),
            Input("max-sources", "data")
        )
        def update_sources_slider_max(max_sources):
            return max(max_sources, 1)

        @self.app.callback(
            [
                Output("discrepancy-filter-container", "style"),
                Output("sources-filter-container", "style"),
                Output("builder-settings-container", "style"),
            ],
            Input("main-tabs", "active_tab")
        )
        def toggle_filters(active_tab):
            if active_tab == "tab-disc":
                return {"display": "block"}, {"display": "none"}, {"display": "none"}
            elif active_tab == "tab-tips":
                return {"display": "none"}, {"display": "block"}, {"display": "none"}
            else: # tab-builder
                return {"display": "none"}, {"display": "block"}, {"display": "block"}

        @self.app.callback(
            [Output("builder-output-container", "children"),
             Output("builder-current-odds", "data"),
             Output("sys-type", "options"),
             Output("sys-type", "value")],
            [Input("matches-data-store", "data"),
             Input("search-input", "value"),
             Input("date-from", "date"),
             Input("date-to", "date"),
             Input("min-sources-slider", "value"),
             Input("builder-leg-count", "value"),
             Input("builder-min-odds", "value"),
             Input("main-tabs", "active_tab")],
            [State("sys-type", "value")] # Memory logic: remember current selections
        )
        def update_builder_logic(data_json, search_text, date_from, date_to, min_sources, leg_count, min_odds, active_tab, current_selected_ks):
            if not data_json or active_tab != "tab-builder":
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update

            df = pd.read_json(StringIO(data_json), orient='split')
            df = self._apply_common_filters(df, search_text, date_from, date_to, min_sources)

            slip_html, odds_list = self._create_bet_builder(df, leg_count or 5, min_odds or 1.2)

            n = len(odds_list)
            new_options = [{'label': f'System {k}/{n}', 'value': k} for k in range(1, n + 1)]

            # Intelligent Checking: Keep old selections only if they still exist in the new leg count
            if current_selected_ks:
                updated_selection = [k for k in current_selected_ks if k <= n]
            else:
                updated_selection = [n] if n > 0 else []

            return slip_html, odds_list, new_options, updated_selection

        @self.app.callback(
            Output("sys-results-output", "children"),
            [Input("sys-total-stake", "value"),
             Input("sys-type", "value"),
             Input("builder-current-odds", "data")]
        )
        def update_simulator_math(total_stake, k_list, odds_list):
            if not odds_list or not total_stake or not k_list:
                return html.Div("Select system types to calculate.", className="text-muted small")

            from itertools import combinations
            system_details = []
            total_bets_count = 0

            for k in sorted(k_list):
                combos = list(combinations(odds_list, k))
                total_bets_count += len(combos)
                system_details.append({'k': k, 'num_bets': len(combos), 'combos': combos})

            stake_per_bet = total_stake / total_bets_count
            total_max_payout = 0

            for sys in system_details:
                sys_payout = sum([stake_per_bet * pd.Series(c).prod() for c in sys['combos']])
                total_max_payout += sys_payout

            summary_rows = [
                html.Tr([
                    html.Td(f"{s['k']}/{len(odds_list)}"),
                    html.Td(s['num_bets']),
                    html.Td(f"${(s['num_bets'] * stake_per_bet):.2f}")
                ]) for s in system_details
            ]

            return html.Div([
                dbc.Table([
                    html.Thead(html.Tr([html.Th("System"), html.Th("Bets"), html.Th("Stake Split")])),
                    html.Tbody(summary_rows)
                ], bordered=False, hover=True, size="sm", className="mb-3 small"),

                dbc.Alert([
                    html.Div([html.Span("Total Bets: "), html.B(total_bets_count)], className="d-flex justify-content-between"),
                    html.Div([html.Span("Stake/Bet: "), html.B(f"${stake_per_bet:.2f}")], className="d-flex justify-content-between"),
                    html.Hr(),
                    html.Div([html.Span("MAX POTENTIAL PAYOUT: ", className="fw-bold"),
                              html.B(f"${total_max_payout:.2f}", style={"fontSize": "1.2rem"})],
                             className="d-flex justify-content-between align-items-center text-success"),
                ], color="light", className="border-0 shadow-sm p-3")
            ])

        @self.app.callback(
            Output("discrepancy-table-container", "children"),
            [
                Input("matches-data-store", "data"),
                Input("search-input", "value"),
                Input("date-from", "date"),
                Input("date-to", "date"),
                Input("discrepancy-filter-slider", "value"),
            ]
        )
        def update_discrepancy_table(data_json, search_text, date_from, date_to, disc_filter):
            if not data_json:
                return dbc.Alert(
                    [html.I(className="fas fa-info-circle me-2"), "No data available. Click Refresh Data to load matches."],
                    color="warning",
                    className="m-4"
                )

            df = pd.read_json(StringIO(data_json), orient='split')
            df = self._apply_common_filters(df, search_text, date_from, date_to)

            # Apply discrepancy filter
            if disc_filter and disc_filter > 0:
                df = df[df['discrepancy_pct'] >= disc_filter]

            return self._create_discrepancy_table(df)

        @self.app.callback(
            Output("tips-table-container", "children"),
            [
                Input("matches-data-store", "data"),
                Input("search-input", "value"),
                Input("date-from", "date"),
                Input("date-to", "date"),
                Input("min-sources-slider", "value"),
            ]
        )
        def update_tips_table(data_json, search_text, date_from, date_to, min_sources):
            if not data_json:
                return dbc.Alert(
                    [html.I(className="fas fa-info-circle me-2"), "No data available. Click Refresh Data to load matches."],
                    color="warning",
                    className="m-4"
                )

            df = pd.read_json(StringIO(data_json), orient='split')
            df = self._apply_common_filters(df, search_text, date_from, date_to, min_sources)

            return self._create_tips_table(df)

        @self.app.callback(
            [
                Output("match-modal", "is_open"),
                Output("modal-title", "children"),
                Output("modal-body", "children"),
                Output("current-match-id", "data"),
            ],
            [
                Input({'type': 'match-table', 'index': dash.dependencies.ALL}, "active_cell"),
                Input("close-modal", "n_clicks"),
            ],
            [
                State("match-modal", "is_open"),
                State({'type': 'match-table', 'index': dash.dependencies.ALL}, "derived_viewport_data"),
            ],
            prevent_initial_call=True
        )
        def toggle_modal(active_cells, close_clicks, is_open, derived_viewport_data_list):
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update

            trigger_id = ctx.triggered[0]["prop_id"]

            # Close modal button clicked
            if "close-modal" in trigger_id:
                return False, "", "", None

            # Only handle table cell clicks, not other triggers
            if not active_cells or not any(cell is not None for cell in active_cells):
                return dash.no_update

            try:
                # Find which table was clicked and get the actual data
                for idx, cell in enumerate(active_cells):
                    if cell and derived_viewport_data_list and idx < len(derived_viewport_data_list):
                        viewport_data = derived_viewport_data_list[idx]
                        if viewport_data:
                            row_idx = cell['row']
                            if 0 <= row_idx < len(viewport_data):
                                # Get match_id from the viewport data (only current page visible rows)
                                match_id = viewport_data[row_idx]['match_id']
                                if match_id in self.matches_dict:
                                    match = self.matches_dict[match_id]
                                    return True, "Match Details", self._create_match_detail(match), match_id
                                else:
                                    print(f"Warning: match_id {match_id} not found in matches_dict")
            except Exception as e:
                print(f"Error opening modal: {e}")
                import traceback
                traceback.print_exc()

            return dash.no_update

    def run(self, debug=True, port=8050):
        print(f"Starting dashboard on http://localhost:{port}")
        self.app.run(debug=debug, port=port)


if __name__ == "__main__":
    from bet_framework.DatabaseManager import DatabaseManager
    db_manager = DatabaseManager()
    dashboard = MatchesDashboard(db_manager)
    dashboard.run(debug=True, port=8050)