from io import StringIO
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, Any

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

    def _prepare_table_data(self) -> pd.DataFrame:
        data = []
        for idx, match in enumerate(self.matches):
            match_id = f"match_{idx}_{id(match)}"
            self.matches_dict[match_id] = match

            try:
                analysis = self.analyzer.analyze_match(match)
                discrepancy = analysis['discrepancy']['score']
                suggestions = analysis['suggestions']

                preds = getattr(match, 'predictions', None)
                scores = preds.scores if preds and getattr(preds, 'scores', None) else []
                unique_sources = len(set(getattr(s, 'source', '') for s in scores if getattr(s, 'source', None)))

                dt = getattr(match, 'datetime', datetime.now())

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
                    'timestamp': dt
                })
            except Exception as e:
                print(f"Error processing match {match_id}: {e}")
                continue

        return pd.DataFrame(data)

    def _setup_layout(self):
        self.app.layout = dbc.Container([
            dcc.Store(id="current-match-id"),

            # Header
            dbc.Row([
                dbc.Col([
                    html.H1([
                        html.I(className="fas fa-futbol me-3"),
                        "Betting Matches Dashboard"
                    ], className="text-center mb-2 mt-4"),
                    html.P("Analyze and compare betting predictions", className="text-center text-muted mb-4"),
                    html.Hr()
                ])
            ]),

            # Filters Row
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label([html.I(className="fas fa-search me-2"), "Search Team"], className="fw-bold mb-2"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-search")),
                                dbc.Input(id="search-input", type="text", placeholder="Type team name...")
                            ])
                        ], lg=3, md=6, className="mb-3"),

                        dbc.Col([
                            html.Label([html.I(className="fas fa-calendar-alt me-2"), "From Date"], className="fw-bold mb-2"),
                            dcc.DatePickerSingle(
                                id="date-from",
                                date=(datetime.now() - timedelta(days=7)).date(),
                                display_format='YYYY-MM-DD',
                                style={'width': '100%'}
                            )
                        ], lg=2, md=6, className="mb-3"),

                        dbc.Col([
                            html.Label([html.I(className="fas fa-calendar-check me-2"), "To Date"], className="fw-bold mb-2"),
                            dcc.DatePickerSingle(
                                id="date-to",
                                date=(datetime.now() + timedelta(days=30)).date(),
                                display_format='YYYY-MM-DD',
                                style={'width': '100%'}
                            )
                        ], lg=2, md=6, className="mb-3"),

                        dbc.Col([
                            html.Label([html.I(className="fas fa-filter me-2"), "Min Disc %"], className="fw-bold mb-2"),
                            dcc.Slider(
                                id='discrepancy-filter-slider',
                                min=0, max=100, step=5, value=0,
                                marks={0: '0', 50: '50', 100: '100'}
                            )
                        ], lg=2, md=6, className="mb-3"),

                        dbc.Col([
                            html.Label([html.I(className="fas fa-layer-group me-2"), "Min Sources"], className="fw-bold mb-2"),
                            dcc.Slider(
                                id='min-sources-slider',
                                min=1, max=10, step=1, value=2,
                                marks={1: '1', 5: '5', 10: '10'}
                            )
                        ], lg=2, md=6, className="mb-3"),

                        dbc.Col([
                            html.Label("\u00A0", className="fw-bold mb-2 d-block"),
                            dbc.Button(
                                [html.I(className="fas fa-sync-alt me-2"), "Refresh"],
                                id="refresh-btn",
                                color="primary",
                                className="w-100"
                            )
                        ], lg=1, md=12, className="mb-3"),
                    ], align="end")
                ])
            ], className="mb-4 shadow-sm"),

            # Data Tables Container
            dbc.Row([
                dbc.Col([
                    html.Div(id="matches-table-container")
                ])
            ]),

            # Modal
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle(id="modal-title"), close_button=True),
                dbc.ModalBody(id="modal-body", style={"maxHeight": "75vh", "overflowY": "auto"}),
                dbc.ModalFooter(
                    dbc.Button([html.I(className="fas fa-times me-2"), "Close"],
                              id="close-modal", color="secondary")
                ),
            ], id="match-modal", size="xl", scrollable=True),

            dcc.Store(id="matches-data-store"),

        ], fluid=True, className="p-4", style={"backgroundColor": "#f0f2f5", "minHeight": "100vh"})

    def _create_discrepancy_table(self, df):
        if df.empty:
            return dbc.Alert("No matches found", color="info", className="text-center")

        cols = ['match_id', 'datetime', 'home', 'away', 'discrepancy', 'discrepancy_pct', 'quick_suggestion']
        display_df = df[cols].copy()

        return dash_table.DataTable(
            id='table-discrepancy',
            columns=[
                {"name": "", "id": "match_id"},
                {"name": "Date & Time", "id": "datetime"},
                {"name": "Home", "id": "home"},
                {"name": "Away", "id": "away"},
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
            },
            style_cell_conditional=[
                {'if': {'column_id': 'match_id'}, 'display': 'none'}
            ],
            style_header={
                'backgroundColor': '#1a1a2e',
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center',
                'padding': '15px',
            },
            style_data={
                'backgroundColor': 'white',
                'border': '1px solid #e0e0e0'
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'},
                {'if': {'state': 'active'}, 'backgroundColor': '#e3f2fd', 'border': '2px solid #2196F3'},
            ],
            css=[{'selector': 'tr:hover td', 'rule': 'background-color: #e3f2fd !important; cursor: pointer;'}],
            page_size=25,
            page_action='native',
        )

    def _create_tips_table(self, df):
        if df.empty:
            return dbc.Alert("No matches found", color="info", className="text-center")

        cols = ['match_id', 'datetime', 'home', 'away', 'result_home', 'result_draw', 'result_away',
                'over', 'under', 'btts_yes', 'btts_no']
        display_df = df[cols].copy()

        return dash_table.DataTable(
            id='table-tips',
            columns=[
                {"name": "", "id": "match_id"},
                {"name": "Date & Time", "id": "datetime"},
                {"name": "Home", "id": "home"},
                {"name": "Away", "id": "away"},
                {"name": "1 %", "id": "result_home", "type": "numeric"},
                {"name": "X %", "id": "result_draw", "type": "numeric"},
                {"name": "2 %", "id": "result_away", "type": "numeric"},
                {"name": "O2.5 %", "id": "over", "type": "numeric"},
                {"name": "U2.5 %", "id": "under", "type": "numeric"},
                {"name": "BTTS Y %", "id": "btts_yes", "type": "numeric"},
                {"name": "BTTS N %", "id": "btts_no", "type": "numeric"},
            ],
            data=display_df.to_dict('records'),
            sort_action='native',
            sort_mode='multi',
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'center',
                'padding': '15px',
                'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                'fontSize': '14px',
            },
            style_cell_conditional=[
                {'if': {'column_id': 'match_id'}, 'display': 'none'},
                {'if': {'column_id': 'home'}, 'textAlign': 'left'},
                {'if': {'column_id': 'away'}, 'textAlign': 'left'},
            ],
            style_header={
                'backgroundColor': '#1a1a2e',
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center',
                'padding': '15px',
            },
            style_data={
                'backgroundColor': 'white',
                'border': '1px solid #e0e0e0'
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'},
                {'if': {'state': 'active'}, 'backgroundColor': '#e3f2fd', 'border': '2px solid #2196F3'},
            ],
            css=[{'selector': 'tr:hover td', 'rule': 'background-color: #e3f2fd !important; cursor: pointer;'}],
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
            Output("matches-data-store", "data"),
            Input("refresh-btn", "n_clicks"),
            prevent_initial_call=False
        )
        def refresh_data(n_clicks):
            df = self.refresh_data()
            return df.to_json(date_format='iso', orient='split')

        @self.app.callback(
            Output("matches-table-container", "children"),
            [
                Input("matches-data-store", "data"),
                Input("search-input", "value"),
                Input("date-from", "date"),
                Input("date-to", "date"),
                Input("discrepancy-filter-slider", "value"),
                Input("min-sources-slider", "value"),
            ]
        )
        def update_table(data_json, search_text, date_from, date_to, disc_filter, min_sources):
            if not data_json:
                return dbc.Alert("No data. Click Refresh.", color="warning")

            df = pd.read_json(StringIO(data_json), orient='split')

            # Apply common filters
            if search_text:
                mask = df['home'].str.contains(search_text, case=False, na=False) | \
                       df['away'].str.contains(search_text, case=False, na=False)
                df = df[mask]

            if date_from:
                df = df[df['timestamp'] >= pd.to_datetime(date_from)]

            if date_to:
                df = df[df['timestamp'] <= pd.to_datetime(date_to) + pd.Timedelta(days=1)]

            # Discrepancy tab with disc filter
            disc_df = df.copy()
            if disc_filter and disc_filter > 0:
                disc_df = disc_df[disc_df['discrepancy_pct'] >= disc_filter]
            disc_table = self._create_discrepancy_table(disc_df)

            # Tips tab with sources filter
            tips_df = df.copy()
            if min_sources and min_sources > 1:
                tips_df = tips_df[tips_df['sources'] >= min_sources]
            tips_table = self._create_tips_table(tips_df)

            return dbc.Card([
                dbc.CardBody([
                    dbc.Tabs([
                        dbc.Tab(disc_table, label='Discrepancy', tab_id='tab-disc'),
                        dbc.Tab(tips_table, label='Tips', tab_id='tab-tips')
                    ], id='main-tabs', active_tab='tab-disc')
                ])
            ], className="shadow-sm")

        @self.app.callback(
            [
                Output("match-modal", "is_open"),
                Output("modal-title", "children"),
                Output("modal-body", "children"),
                Output("current-match-id", "data"),
            ],
            [
                Input("table-discrepancy", "active_cell"),
                Input("table-tips", "active_cell"),
                Input("close-modal", "n_clicks"),
            ],
            [
                State("match-modal", "is_open"),
                State("table-discrepancy", "derived_viewport_data"),
                State("table-tips", "derived_viewport_data"),
            ],
            prevent_initial_call=True
        )
        def toggle_modal(disc_cell, tips_cell, close_clicks, is_open, disc_data, tips_data):
            ctx = callback_context
            if not ctx.triggered:
                return False, "", "", None

            trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if trigger_id == "close-modal":
                return False, "", "", None

            # Handle clicks from either table
            active_cell = disc_cell if trigger_id == "table-discrepancy" else tips_cell
            table_data = disc_data if trigger_id == "table-discrepancy" else tips_data

            if active_cell and table_data:
                row_idx = active_cell['row']
                if 0 <= row_idx < len(table_data):
                    match_id = table_data[row_idx]['match_id']
                    if match_id in self.matches_dict:
                        match = self.matches_dict[match_id]
                        return True, "Match Details", self._create_match_detail(match), match_id

            return is_open, "", "", None

    def run(self, debug=True, port=8050):
        print(f"Starting dashboard on http://localhost:{port}")
        self.app.run(debug=debug, port=port)


if __name__ == "__main__":
    from bet_framework.DatabaseManager import DatabaseManager
    db_manager = DatabaseManager()
    dashboard = MatchesDashboard(db_manager)
    dashboard.run(debug=True, port=8050)
