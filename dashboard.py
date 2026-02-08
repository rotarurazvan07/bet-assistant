import argparse
from io import StringIO
import sys

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, dash_table, callback_context, ALL
import pandas as pd

from bet_framework.BettingAnalyzer import BettingAnalyzer
from bet_framework.DatabaseManager import DatabaseManager
from bet_framework.SettingsManager import settings_manager

class BetAssistantDashboard:
    def __init__(self, db_path):
        self.db_manager = DatabaseManager(db_path)
        self.betting_analyzer = BettingAnalyzer(self.db_manager)

        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True
        )
        self.app.title = "Bet Assistant"
        self._setup_layout()
        self._setup_callbacks()

    def _format_tip_cell(self, percentage, odds):
        """Format a tip cell with percentage and odds."""
        if odds is not None and odds >= 1:
            return f"{percentage}%\n{odds:.2f}"
        return f"{percentage}%"

    def _create_tips_table(self, df):
        """Create betting tips table from DataFrame."""
        if df.empty:
            return dbc.Alert(
                [html.I(className="fas fa-info-circle me-2"), "No matches found matching your criteria"],
                color="info",
                className="text-center m-4"
            )

        # Prepare display DataFrame with formatted cells
        display_df = df.copy()

        # Create display columns with odds
        display_df['result_home_display'] = display_df.apply(
            lambda row: self._format_tip_cell(row['prob_home'], row['odds_home']), axis=1
        )
        display_df['result_draw_display'] = display_df.apply(
            lambda row: self._format_tip_cell(row['prob_draw'], row['odds_draw']), axis=1
        )
        display_df['result_away_display'] = display_df.apply(
            lambda row: self._format_tip_cell(row['prob_away'], row['odds_away']), axis=1
        )
        display_df['over_display'] = display_df.apply(
            lambda row: self._format_tip_cell(row['prob_over'], row['odds_over']), axis=1
        )
        display_df['under_display'] = display_df.apply(
            lambda row: self._format_tip_cell(row['prob_under'], row['odds_under']), axis=1
        )
        display_df['btts_yes_display'] = display_df.apply(
            lambda row: self._format_tip_cell(row['prob_btts_yes'], row['odds_btts_yes']), axis=1
        )
        display_df['btts_no_display'] = display_df.apply(
            lambda row: self._format_tip_cell(row['prob_btts_no'], row['odds_btts_no']), axis=1
        )

        cols = ['match_id', 'datetime_str', 'home', 'away', 'sources',
                'prob_home', 'result_home_display', 'prob_draw', 'result_draw_display',
                'prob_away', 'result_away_display', 'prob_over', 'over_display',
                'prob_under', 'under_display', 'prob_btts_yes', 'btts_yes_display',
                'prob_btts_no', 'btts_no_display']

        display_df = display_df[cols].rename(columns={'datetime_str': 'datetime'})

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
            sort_by=[{'column_id': 'prob_home', 'direction': 'desc'}],
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
                {'if': {'column_id': 'btts_yes_display'}, 'borderLeft': '3px solid #000000'},
                {'if': {'column_id': 'over_display'}, 'borderLeft': '3px solid #000000'},
                {'if': {'column_id': 'result_home_display'}, 'borderLeft': '3px solid #000000'},

                # Highlighting based on percentage values
                {'if': {'filter_query': '{prob_home} >= 80', 'column_id': 'result_home_display'},
                 'backgroundColor': "#4ce770", 'color': "#073F14", 'fontWeight': 'bold'},
                {'if': {'filter_query': '{prob_draw} >= 80', 'column_id': 'result_draw_display'},
                 'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'},
                {'if': {'filter_query': '{prob_away} >= 80', 'column_id': 'result_away_display'},
                 'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'},
                {'if': {'filter_query': '{prob_btts_yes} >= 80', 'column_id': 'btts_yes_display'},
                 'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'},
                {'if': {'filter_query': '{prob_btts_no} >= 80', 'column_id': 'btts_no_display'},
                 'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'},
                {'if': {'filter_query': '{prob_over} >= 80', 'column_id': 'over_display'},
                 'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'},
                {'if': {'filter_query': '{prob_under} >= 80', 'column_id': 'under_display'},
                 'backgroundColor': '#4ce770', 'color': '#073F14', 'fontWeight': 'bold'},
            ],
            css=[{
                'selector': 'tr:hover td',
                'rule': 'background-color: #f3e5f5 !important; cursor: pointer; transform: scale(1.01);'
            }],
            page_size=25,
            page_action='native',
        )

    def _create_bet_builder(self, grouped_selections):
        """Create bet builder UI from grouped selections."""
        if not grouped_selections:
            return [dbc.Alert("No matches match criteria.", color="warning")]

        grid_items = []

        for group in grouped_selections:
            p = group['primary']
            s_list = group['secondary']

            # --- Helper: Create the Main Market Block ---
            def create_primary_block(bet_data):
                conf = bet_data['prob']
                color = "success" if conf >= 80 else "warning" if conf >= 60 else "danger"
                odds_val = bet_data['odds']
                odds_display = f"@{odds_val:.2f}" if odds_val > 0 else "N/A"
                odds_bg = "bg-primary" if odds_val > 0 else "bg-secondary"

                return html.Div([
                    dbc.Row([
                        dbc.Col(html.Span(bet_data['market'], className="fw-bold fs-6 text-dark"), width=8),
                        dbc.Col(html.Div(odds_display, className=f"badge {odds_bg} fs-6 float-end"), width=4)
                    ], className="align-items-center mb-1"),
                    html.Div([
                        html.Small("Confidence", className="text-muted me-2", style={"fontSize": "0.7rem"}),
                        html.Small(f"{conf}%", className=f"fw-bold text-{color}", style={"fontSize": "0.7rem"}),
                    ], className="d-flex align-items-center mb-1"),
                    dbc.Progress(value=conf, color=color, style={"height": "6px"}, className="rounded-pill mb-2"),
                ], className="bg-light p-2 rounded-2")

            # --- Helper: Create Alternative Markets Rows ---
            def create_alternative_row(bet_data):
                conf = bet_data['prob']
                color = "success" if conf >= 80 else "warning" if conf >= 60 else "danger"
                odds_val = bet_data['odds']
                odds_display = f"@{odds_val:.2f}" if odds_val > 0 else "N/A"
                odds_color = "text-primary" if odds_val > 0 else "text-muted"

                return dbc.Row([
                    dbc.Col(html.Span(bet_data['market'], className="fw-medium text-dark", style={"fontSize": "0.75rem"}), width=3),
                    dbc.Col(
                        dbc.Progress(value=conf, color=color, style={"height": "5px"}, className="rounded-pill w-100"),
                        width=5, className="d-flex align-items-center"
                    ),
                    dbc.Col(html.Span(f"{conf}%", className=f"fw-bold text-{color}", style={"fontSize": "0.7rem"}), width=2, className="ps-1"),
                    dbc.Col(html.Span(odds_display, className=f"fw-bold {odds_color}", style={"fontSize": "0.75rem"}), width=2, className="text-end"),
                ], className="align-items-center g-0 mb-1 pt-1 border-top border-light-subtle")

            # --- Build the Individual Card ---
            selection_card = dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(html.H5(p['match'], className="fw-bold text-dark mb-0", style={"fontSize": "1.1rem"}), width=10),
                        dbc.Col(
                            dbc.Button(
                                html.I(className="fas fa-times"),
                                id={'type': 'exclude-btn', 'index': p['match']},
                                color="link", size="sm", className="p-0 text-muted text-decoration-none"
                            ), width=2, className="text-end"
                        )
                    ], className="mb-2 align-items-center"),

                    create_primary_block(p),

                    html.Div(
                        [create_alternative_row(alt) for alt in s_list[:2]] if s_list else None
                    ),
                ], className="p-2")
            ], className="shadow-sm border-0 rounded-3 h-100", style={"backgroundColor": "#f8f9fa"})

            # --- Wrap Card in a Column (lg=6 creates the 2-column effect) ---
            # xs=12 means full width on mobile
            # lg=6 means half width (2 columns) on desktop
            col_item = dbc.Col(selection_card, xs=12, lg=6, className="mb-3")
            grid_items.append(col_item)

        # Return a single Row containing the grid items
        return dbc.Row(grid_items, className="g-2")

    def _setup_layout(self):
        self.app.layout = dbc.Container([
            dcc.Store(id="current-match-id"),
            dcc.Store(id="max-sources", data=10),
            dcc.Store(id="excluded-matches-store", data=[]),
            dcc.Store(id="matches-data-store"),
            # --- Header ---
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.H1([
                                html.I(className="fas fa-chart-line me-3"),
                                "Bet Assistant"
                            ], className="fw-bold text-white mb-1", style={"letterSpacing": "-1px"})
                        ], className="text-start"),
                        dbc.Button([
                            html.I(className="fas fa-sync-alt me-2"), "Refresh Data"
                        ], id="refresh-btn", className="ms-auto shadow-sm fw-bold",
                        style={"borderRadius": "10px", "background": "rgba(255,255,255,0.2)", "border": "1px solid rgba(255,255,255,0.3)"})
                    ], className="d-flex align-items-center p-4 shadow-lg",
                    style={
                        "background": "linear-gradient(135deg, #4361ee 0%, #3f37c9 100%)",
                        "borderRadius": "20px",
                        "marginTop": "20px"
                    })
                ])
            ], className="mb-4"),

            # --- Unified Filter Row (One row only) ---
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # 1. Search
                        dbc.Col([
                            html.Small("SEARCH ENGINE", className="fw-bold text-muted mb-2 d-block", style={"fontSize": "0.7rem"}),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-search text-primary")),
                                dbc.Input(id="search-input", placeholder="Filter by team", className="border-start-0")
                            ], className="shadow-sm rounded-3")
                        ], lg=3, md=6),

                        # Date Range
                        dbc.Col([
                            html.Small("TIME HORIZON", className="fw-bold text-muted mb-2 d-block", style={"fontSize": "0.7rem"}),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-calendar-alt text-success")),
                                dbc.Input(id="date-from", type="date", className="border-end-0"),
                                dbc.Input(id="date-to", type="date"),
                            ], className="shadow-sm rounded-3")
                        ], lg=4, md=6),

                        # Min sources
                        dbc.Col([
                            html.Div([
                                html.Small("MIN SOURCES", className="fw-bold text-muted mb-2 d-block", style={"fontSize": "0.7rem"}),
                                dcc.Slider(
                                    id='min-sources-slider', min=1, max=10, step=1, value=1,
                                    tooltip={"placement": "bottom", "always_visible": False}
                                )
                            ], id="sources-filter-container")
                        ], lg=5, md=12)

                    ], className="g-2 align-items-end"),
                    html.Div(id="last-updated-text", className="text-muted small mt-2 text-end")
                ], className="py-2")
            ], className="shadow-sm mb-3 border-0"),

            dbc.Card([
                dbc.CardBody([
                    dbc.Tabs(id='main-tabs', active_tab='tab-tips', children=[
                        # Tab 1
                        dbc.Tab(
                            html.Div(id="tips-table-container", className="py-4"),
                            label="Betting Tips", tab_id='tab-tips', labelClassName="px-4 fw-bold"
                        ),
                        # Tab 2: Smart Builder
                        dbc.Tab([
                            dcc.Store(id='builder-current-odds'),
                            # Sub-Settings Bar
                            html.Div([
                                dbc.Row([
                                    dbc.Col(dbc.InputGroup([
                                        dbc.InputGroupText("Legs"),
                                        dbc.Input(id="builder-leg-count", type="number", value=5, size="sm"),
                                    ], className="shadow-sm"), width="auto"),

                                # 1. Risk Profile Selector
                                    dbc.Col([
                                        dbc.InputGroup([
                                            dbc.InputGroupText(html.I(className="fas fa-shield-alt text-primary")),
                                            dbc.Select(
                                                id="builder-risk-level",
                                                options=[
                                                    {"label": "🛡️ Low Risk", "value": "low"},
                                                    {"label": "⚖️ Medium Risk", "value": "med"},
                                                    {"label": "🔥 High Risk", "value": "high"},
                                                ],
                                                value="med",
                                                size="sm",
                                                className="fw-bold"
                                            ),
                                        ], className="shadow-sm")
                                    ], width="auto"),

                                    # 2. Min Odds (Manual)
                                    dbc.Col([
                                        dbc.InputGroup([
                                            dbc.InputGroupText("Min"),
                                            dbc.Input(
                                                id="builder-min-odds",
                                                type="number",
                                                value=1.2,
                                                step=0.05,
                                                size="sm",
                                                style={"width": "80px"}
                                            ),
                                        ], className="shadow-sm")
                                    ], width="auto"),

                                    # 3. Max Odds (Manual)
                                    dbc.Col([
                                        dbc.InputGroup([
                                            dbc.InputGroupText("Max"),
                                            dbc.Input(
                                                id="builder-max-odds",
                                                type="number",
                                                value=2.0,
                                                step=0.05,
                                                size="sm",
                                                style={"width": "80px"}
                                            ),
                                        ], className="shadow-sm")
                                    ], width="auto"),

                                    dbc.Col(html.Div([
                                        html.Small("MARKETS:", className="fw-bold me-3 text-secondary"),
                                        dbc.Checklist(
                                            options=[
                                                {"label": "Result", "value": "result"},
                                                {"label": "O/U 2.5", "value": "over_under_2.5"},
                                                {"label": "BTTS", "value": "btts"},
                                            ],
                                            value=["result", "over_under_2.5", "btts"],
                                            id="market-type-filter", inline=True, switch=True,
                                            style={"fontSize": "0.85rem"}
                                        ),
                                    ], className="d-flex align-items-center bg-light border rounded-pill px-3 py-1"), width="auto")
                                ], justify="start", className="g-3 align-items-center")
                            ], className="p-3 mb-4 bg-white border rounded-3"),

                            # Builder Content
                            html.Div(id="builder-output-container")
                        ], label="Smart Builder", tab_id='tab-builder', labelClassName="px-4 fw-bold")
                    ], className="nav-pills custom-tabs")
                ], className="p-4")
            ], className="border-0 shadow-lg mb-5", style={"borderRadius": "20px"}),

        ], fluid=True, className="px-lg-5", style={"backgroundColor": "#f8f9fe", "minHeight": "100vh"})

    def _setup_callbacks(self):
        @self.app.callback(
            [
                Output("matches-data-store", "data"),
                Output("min-sources-slider", "max"),
            ],
            Input("refresh-btn", "n_clicks"),
            prevent_initial_call=False
        )
        def refresh_data(n_clicks):
            """Refresh data from database - ONLY called on button click or initial load."""
            df = self.betting_analyzer.refresh_data()
            max_sources = int(df['sources'].max()) if not df.empty else 10
            return df.to_json(date_format='iso', orient='split'), max_sources

        @self.app.callback(
            Output("tips-table-container", "children"),
            [
                Input("matches-data-store", "data"),
                Input("search-input", "value"),
                Input("date-from", "value"),
                Input("date-to", "value"),
                Input("min-sources-slider", "value"),
            ]
        )
        def update_tips_table(data_json, search_text, date_from, date_to, min_sources):
            """Update tips table - works purely from DataFrame, no DB query."""
            if not data_json:
                return dbc.Alert(
                    [html.I(className="fas fa-info-circle me-2"), "No data available. Click Refresh Data to load matches."],
                    color="warning",
                    className="m-4"
                )

            # Use analyzer's filtering method
            filtered_df = self.betting_analyzer.get_filtered_matches(
                search_text=search_text,
                date_from=date_from,
                date_to=date_to,
                min_sources=min_sources
            )

            return self._create_tips_table(filtered_df)

        @self.app.callback(
            [Output("builder-min-odds", "value"),
            Output("builder-max-odds", "value")],
            [Input("builder-risk-level", "value")],
            [State("builder-min-odds", "value"),
            State("builder-max-odds", "value")]
        )
        def update_odds_presets(risk_level, current_min, current_max):
            # Mapping presets to specific ranges
            presets = {
                "low": (1.10, 1.40),
                "med": (1.45, 1.85),
                "high": (1.90, 10)
            }

            if risk_level in presets:
                return presets[risk_level]

            # If "custom" is selected, keep the current values
            return current_min, current_max

        @self.app.callback(
            [Output("builder-output-container", "children"),
            Output("builder-current-odds", "data")],
            [Input("matches-data-store", "data"),
            Input("search-input", "value"),
            Input("date-from", "value"),
            Input("date-to", "value"),
            Input("min-sources-slider", "value"),
            Input("builder-leg-count", "value"),
            Input("builder-min-odds", "value"),
            Input("builder-max-odds", "value"),
            Input("main-tabs", "active_tab"),
            Input("excluded-matches-store", "data"),
            Input("market-type-filter", "value")]
        )
        def update_builder_logic(data_json, search_text, date_from, date_to, min_sources,
                                leg_count, min_odds, max_odds, active_tab, excluded_matches,
                                included_markets): # <--- New Argument
            """Update bet builder - reacts to market filters and criteria."""

            if not data_json or active_tab != "tab-builder":
                return dash.no_update, dash.no_update

            # Load data
            df = pd.read_json(StringIO(data_json), orient='split')

            # Use analyzer's updated bet slip builder with market filtering
            grouped_selections = self.betting_analyzer.build_bet_slip(
                search_text=search_text,
                date_from=date_from,
                date_to=date_to,
                min_sources=min_sources,
                leg_count=leg_count or 5,
                min_odds_val=min_odds or 1.1,
                max_odds_val=max_odds or 10,
                excluded_matches=excluded_matches,
                included_market_types=included_markets
            )

            # If no selections found
            if not grouped_selections:
                # Returning a single Alert for the container and an empty list for the odds data
                return [dbc.Alert("No matches meet criteria.", color="warning")], []

            # Generate UI and Odds data
            slip_html = self._create_bet_builder(grouped_selections)
            odds_list = [g['primary']['odds'] for g in grouped_selections]

            return slip_html, odds_list

        @self.app.callback(
            Output("excluded-matches-store", "data"),
            Input({'type': 'exclude-btn', 'index': ALL}, 'n_clicks'),
            State("excluded-matches-store", "data"),
            prevent_initial_call=True
        )
        def exclude_match(n_clicks_list, current_excluded):
            ctx = callback_context
            if not ctx.triggered:
                return dash.no_update

            triggered_prop = ctx.triggered[0]['prop_id']

            if ".n_clicks" not in triggered_prop:
                return dash.no_update

            import json
            try:
                id_str = triggered_prop.split('.n_clicks')[0]
                triggered_id = json.loads(id_str)
                match_to_exclude = triggered_id['index']
            except Exception as e:
                print(f"Error parsing trigger ID: {e}")
                return dash.no_update

            triggered_index = -1
            for i, input_def in enumerate(ctx.inputs_list[0]):
                if input_def['id']['index'] == match_to_exclude:
                    triggered_index = i
                    break

            if triggered_index == -1 or not n_clicks_list[triggered_index]:
                return dash.no_update

            current_excluded = current_excluded or []
            if match_to_exclude not in current_excluded:
                new_excluded = current_excluded.copy()
                new_excluded.append(match_to_exclude)
                return new_excluded

            return dash.no_update

    def run(self, debug=True, port=8050):
        print(f"Starting dashboard on http://0.0.0.0:{port}")
        self.app.run(debug=debug, host='0.0.0.0', port=port)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Match Finder Dashboard")
    parser.add_argument("db_path", help="Path to the SQLite database file (e.g., matches.db)")
    args = parser.parse_args()
    settings_manager.load_settings("config")

    dashboard = BetAssistantDashboard(args.db_path)
    dashboard.run()
