"""
Modern Betting Matches Dashboard
Displays and filters betting predictions with detailed match analysis

REQUIREMENTS:
pip install dash dash-bootstrap-components pandas pymongo
"""

from io import StringIO
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any
import json

# Import your classes (adjust path as needed)
from bet_framework.core.Match import *
from bet_framework.core.Tip import Tip

# Use MatchAnalyzer for analysis
from bet_framework.MatchAnalyzer import MatchAnalyzer


class MatchesDashboard:
    """Dashboard for visualizing betting matches."""

    def __init__(self, database_manager):
        """
        Initialize dashboard.

        Args:
            database_manager: Your database manager with fetch_matches() method
        """
        self.db_manager = database_manager
        self.matches = []
        self.matches_dict = {}  # Map match IDs to match objects
        # instantiate analyzer once
        self.analyzer = MatchAnalyzer()
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True
        )
        self._setup_layout()
        self._setup_callbacks()

    def refresh_data(self):
        """Fetch latest matches from database."""
        self.matches = self.db_manager.fetch_matches()

        self.matches_dict = {}
        return self._prepare_table_data()

    def _prepare_table_data(self) -> pd.DataFrame:
        """Convert matches to DataFrame for table display."""
        data = []
        for idx, match in enumerate(self.matches):
            # Create unique ID (prefer stable DB id if available)
            raw_id = getattr(match, 'id', None) or getattr(match, 'match_id', None)
            if raw_id is None:
                match_id = f"match_{idx}_{id(match)}"
            else:
                match_id = f"match_{str(raw_id)}"
            # store match object keyed by match_id so modal lookup works
            self.matches_dict[match_id] = match
            # Process each match defensively: ensure a single bad match doesn't
            # break the whole table generation. If something fails, append a
            # minimal fallback row and continue.
            try:
                preds = getattr(match, 'predictions', None)
                tips = []
                if preds and getattr(preds, 'tips', None):
                    tips = preds.tips or []

                unique_sources = len({getattr(t, 'source', None) for t in tips if getattr(t, 'source', None)})
                avg_confidence = 0.0
                if tips:
                    confs = [getattr(t, 'confidence', None) for t in tips if getattr(t, 'confidence', None) is not None]
                    if confs:
                        avg_confidence = sum(float(c) for c in confs) / len(confs)

                # run analysis once and reuse; analyzer itself is defensive but
                # protect against unexpected errors here as well
                try:
                    analysis = self.analyzer.analyze_match(match) or {}
                except Exception as e:
                    print(f"Warning: analyzer failed for match {match_id}: {e}")
                    analysis = {}

                value = analysis.get('value', {}).get('score', 0.0)
                discrepancy = analysis.get('discrepancy', {}).get('score', 0.0)

                # Compute averaged probabilities and scores for table-level fields
                avg_home_prob = avg_draw_prob = avg_away_prob = 0.0
                avg_home_score = avg_away_score = None
                try:
                    probs = preds.probabilities if preds and getattr(preds, 'probabilities', None) else []
                    if probs:
                        avg_home_prob = sum(getattr(p, 'home', 0.0) for p in probs) / len(probs)
                        avg_draw_prob = sum(getattr(p, 'draw', 0.0) for p in probs) / len(probs)
                        avg_away_prob = sum(getattr(p, 'away', 0.0) for p in probs) / len(probs)
                except Exception:
                    avg_home_prob = avg_draw_prob = avg_away_prob = 0.0

                try:
                    scs = preds.scores if preds and getattr(preds, 'scores', None) else []
                    if scs:
                        avg_home_score = sum(getattr(s, 'home', 0) for s in scs) / len(scs)
                        avg_away_score = sum(getattr(s, 'away', 0) for s in scs) / len(scs)
                except Exception:
                    avg_home_score = avg_away_score = None

                # Safe outcome: use score predictions votes to choose 1X vs X2; if tied, fall back to probabilities
                try:
                    scs = preds.scores if preds and getattr(preds, 'scores', None) else []
                    if scs:
                        home_votes = sum(1 for s in scs if getattr(s, 'home', 0) > getattr(s, 'away', 0))
                        away_votes = sum(1 for s in scs if getattr(s, 'away', 0) > getattr(s, 'home', 0))
                        if home_votes > away_votes:
                            outcome_side = '1X'
                        elif away_votes > home_votes:
                            outcome_side = 'X2'
                        else:
                            # tie -> prefer probabilities if available
                            if probs:
                                outcome_side = '1X' if (avg_home_prob + avg_draw_prob) >= (avg_away_prob + avg_draw_prob) else 'X2'
                            else:
                                outcome_side = 'X/12'
                    else:
                        # no score predictions: use probabilities if present, else default to 1X
                        if probs:
                            outcome_side = '1X' if (avg_home_prob + avg_draw_prob) >= (avg_away_prob + avg_draw_prob) else 'X2'
                        else:
                            outcome_side = 'X/12'

                    total_goals = (avg_home_score or 0) + (avg_away_score or 0)
                    rounded = int(round(total_goals))
                    lower = max(0, rounded - 2)
                    upper = lower + 4
                    safe_outcome = f"{outcome_side}&{lower}-{upper}"
                except Exception:
                    safe_outcome = ''

                # Discrepancy %: combine top result probability and draw into one metric (average)
                try:
                    discrepancy_pct = round(max(avg_home_prob, avg_away_prob) + avg_draw_prob, 2)
                except Exception:
                    discrepancy_pct = 0.0

                dt = getattr(match, 'datetime', None) or datetime.now()
                if hasattr(dt, 'strftime'):
                    # Friendly datetime: Mon 24 Dec 18:30
                    dt_str = dt.strftime('%a %d %b %H:%M')
                else:
                    dt_str = str(dt)

                home_name = getattr(getattr(match, 'home_team', None), 'name', 'Unknown')
                away_name = getattr(getattr(match, 'away_team', None), 'name', 'Unknown')

                quick_items = []
                try:
                    # Aggregate tips by normalized text and require at least 2 unique sources
                    tip_groups = {}
                    for t in tips:
                        try:
                            text = t.to_text() if hasattr(t, 'to_text') else None
                        except Exception:
                            text = None

                        if not text:
                            # fall back to common dict/attr fields
                            text = getattr(t, 'raw_text', None) or getattr(t, 'tip', None)
                            if not text:
                                try:
                                    text = t.get('raw_text') if isinstance(t, dict) else None
                                except Exception:
                                    text = None
                        if not text:
                            continue
                        tip_groups.setdefault(text, []).append(t)

                    for label, group in tip_groups.items():
                        # count unique sources
                        sources = set()
                        confs = []
                        for tt in group:
                            src = getattr(tt, 'source', None)
                            if not src:
                                try:
                                    src = tt.get('source') if isinstance(tt, dict) else None
                                except Exception:
                                    src = None
                            if src:
                                sources.add(src)

                            try:
                                c = float(getattr(tt, 'confidence', None) if getattr(tt, 'confidence', None) is not None else (tt.get('confidence') if isinstance(tt, dict) else 0))
                            except Exception:
                                try:
                                    c = float(tt.get('confidence', 0)) if isinstance(tt, dict) else 0
                                except Exception:
                                    c = 0
                            confs.append(c)

                        if len(sources) < 2:
                            continue

                        avg_conf = sum(confs) / len(confs) if confs else 0
                        if avg_conf >= 75:
                            quick_items.append(label)
                except Exception:
                    pass

                try:
                    sugs = analysis.get('suggestions', []) if isinstance(analysis, dict) else []
                    for s in sugs:
                        # Normalize different shapes (dict-like or object-like)
                        try:
                            if isinstance(s, dict):
                                conf = float(s.get('confidence', 0.0) or 0.0)
                                ev = s.get('evidence', []) or []
                                support = int(s.get('evidence_count', len(ev)))
                                label = s.get('suggestion') or s.get('label') or str(s)
                            else:
                                # object-like
                                conf = float(getattr(s, 'confidence', 0.0) or 0.0)
                                ev = getattr(s, 'evidence', []) or []
                                support = int(getattr(s, 'evidence_count', len(ev)))
                                label = getattr(s, 'suggestion', getattr(s, 'label', str(s)))
                        except Exception:
                            # skip malformed suggestion entries
                            continue

                        # Only include high-confidence suggestions with at least two supporting evidences
                        if conf >= 75 and support >= 2:
                            quick_items.append(str(label))
                except Exception:
                    pass

                # Deduplicate quick items while preserving order
                try:
                    unique_quick = list(dict.fromkeys(quick_items))
                except Exception:
                    unique_quick = quick_items

                quick_suggestions = "\n".join(unique_quick)

                # Use date-only prefix for datetime so sorting ignores hours when multi-sorting
                display_date_prefix = dt.strftime('%Y-%m-%d')

                # For sorting, store only the date (so rows on same day are equal when sorting by date)
                data.append({
                    'match_id': match_id,
                    'datetime': f"{display_date_prefix}",
                    'home': home_name,
                    'away': away_name,
                    # Round Tips Value to 2 decimals for table display
                    'value': round(float(value or 0.0), 2),
                    'discrepancy': discrepancy,
                    'safe_outcome': safe_outcome,
                    'discrepancy_pct': discrepancy_pct,
                    'sources': unique_sources,
                    'quick_suggestions': quick_suggestions,
                    'timestamp': dt  # For filtering
                })
            except Exception as e:
                # Fallback: include the match with minimal info so UI keeps it
                print(f"Error processing match {match_id}: {e}")
                dt = getattr(match, 'datetime', None) or datetime.now()
                dt_str = dt.strftime('%Y-%m-%d %H:%M') if hasattr(dt, 'strftime') else str(dt)
                home_name = getattr(getattr(match, 'home_team', None), 'name', 'Unknown')
                away_name = getattr(getattr(match, 'away_team', None), 'name', 'Unknown')
                data.append({
                    'match_id': match_id,
                    'datetime': dt_str,
                    'home': home_name,
                    'away': away_name,
                    'value': round(0.0, 2),
                    'discrepancy': 0.0,
                    'safe_outcome': '',
                    'discrepancy_pct': 0.0,
                    'sources': 0,
                    'quick_suggestions': '',
                    'timestamp': dt
                })

        return pd.DataFrame(data)

    def _setup_layout(self):
        """Setup dashboard layout."""
        self.app.layout = dbc.Container([
            # Header with info card
            dbc.Row([
                dcc.Store(id="current-match-id"),  # store for currently opened match id in modal
                dbc.Col([
                    html.H1([
                        html.I(className="fas fa-futbol me-3"),
                        "Betting Matches Dashboard"
                    ], className="mb-2 mt-4"),
                    html.P("Analyze and compare betting predictions", className="text-muted mb-2")
                ], lg=8),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("How calculations are made", className="card-title"),
                                        html.Ul([
                                            html.Li([html.B("Tips Value:"), html.Span(" TODO")]),
                                            html.Li([html.B("Discrepancy:"), html.Span(" TODO")]),
                                            html.Li([html.B("Discrepancy %:"), html.Span(" TODO")])
                                        ], style={"fontSize": "13px", "margin": "0"})
                        ])
                    ], className="shadow-sm")
                ], lg=4, className="text-end")
            ]),

            # Filters Row
            dbc.Row([
                # Search box
                dbc.Col([
                    html.Label([
                        html.I(className="fas fa-search me-2"),
                        "Search"
                    ], className="fw-bold mb-2"),
                    dbc.Input(id="search-input", placeholder="Search by team name...", type="text")
                ], lg=3, md=6, className="mb-3"),

                # Date From
                dbc.Col([
                    html.Label([
                        html.I(className="fas fa-calendar-alt me-2"),
                        "From Date"
                    ], className="fw-bold mb-2"),
                    dcc.DatePickerSingle(
                        id="date-from",
                        date=None,
                        display_format='YYYY-MM-DD',
                        style={'width': '100%'}
                    )
                ], lg=3, md=6, className="mb-3"),

                # Date To
                dbc.Col([
                    html.Label([
                        html.I(className="fas fa-calendar-check me-2"),
                        "To Date"
                    ], className="fw-bold mb-2"),
                    dcc.DatePickerSingle(
                        id="date-to",
                        date=None,
                        display_format='YYYY-MM-DD',
                        style={'width': '100%'}
                    )
                ], lg=3, md=6, className="mb-3"),

                # Refresh Button
                dbc.Col([
                    html.Label("\u00A0", className="fw-bold mb-2 d-block"),  # Spacer
                    dbc.Button(
                        [html.I(className="fas fa-sync-alt me-2"), "Refresh"],
                        id="refresh-btn",
                        color="primary",
                        className="w-100"
                    )
                ], lg=2, md=12, className="mb-3"),
            ], align="end", className="mb-4 shadow-sm"),

            # Discrepancy % filter slider (0-100)
            dbc.Row([
                dbc.Col(html.Label("Discrepancy % Filter (hide below)"), lg=3),
                dbc.Col(dcc.Slider(id='discrepancy-filter-slider', min=0, max=100, step=1, value=0,
                                   marks={0: '0', 25: '25', 50: '50', 75: '75', 100: '100'}), lg=8),
                dbc.Col(html.Div(id='discrepancy-filter-value', children="0", className='fw-bold text-end'), lg=1)
            ], className="mb-4"),

            # Data Table
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div(id="matches-table-container")
                        ])
                    ], className="shadow-sm")
                ])
            ]),

            # Modal for match details
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle(id="modal-title"), close_button=True),
                dbc.ModalBody(id="modal-body", style={"maxHeight": "75vh", "overflowY": "auto"}),
                dbc.ModalFooter(
                    dbc.Button([html.I(className="fas fa-times me-2"), "Close"],
                              id="close-modal", color="secondary")
                ),
            ], id="match-modal", size="xl", scrollable=True),

            # Store for data
            dcc.Store(id="matches-data-store"),

        ], fluid=True, className="p-4", style={"backgroundColor": "#f0f2f5", "minHeight": "100vh"})

    def _create_table(self, df: pd.DataFrame):
        """Create interactive data table."""
        if df.empty:
            return dbc.Alert([
                html.I(className="fas fa-info-circle me-2"),
                "No matches found with current filters"
            ], color="info", className="text-center")

        # Keep match_id in data but hide it visually with CSS
        # Include safe_outcome and discrepancy_pct for the table
        cols = ['match_id', 'datetime', 'home', 'away', 'value', 'quick_suggestions', 'safe_outcome', 'discrepancy', 'discrepancy_pct', 'sources']

        # use intersection in case some columns are missing
        cols = [c for c in cols if c in df.columns]
        display_df = df[cols].copy()
        # Keep Tips Value as numeric for correct sorting; formatting handled by DataTable
        # (the DataTable column will use a format specifier to show 2 decimals)
        # Set row id so DataTable.active_cell may provide row_id across pagination
        display_df['id'] = display_df['match_id']

        return dash_table.DataTable(
            id='matches-table',
            columns=[
                {"name": "", "id": "match_id"},  # Empty name, will hide with CSS
                {"name": "Date & Time", "id": "datetime"},
                {"name": "Home Team", "id": "home"},
                {"name": "Away Team", "id": "away"},
                {"name": "Tips Value", "id": "value", "type": "numeric", "format": {"specifier": ".2f"}},
                {"name": "Quick Suggestions", "id": "quick_suggestions"},
                {"name": "Safe Outcome", "id": "safe_outcome"},
                {"name": "Discrepancy", "id": "discrepancy", "type": "numeric"},
                {"name": "Discrepancy %", "id": "discrepancy_pct", "type": "numeric"},
            ],
            data=display_df.to_dict('records'),
            sort_action='native',
            sort_mode='multi',
            row_selectable=False,
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '15px',
                'fontFamily': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                'fontSize': '14px',
                'whiteSpace': 'normal',
                'height': 'auto',
            },

            # Ensure quick suggestions column preserves newlines and wraps
            style_cell_conditional=[
                {
                    'if': {'column_id': 'match_id'},
                    'display': 'none'
                },
                {
                    'if': {'column_id': 'quick_suggestions'},
                    'whiteSpace': 'pre-wrap',
                    'maxWidth': '320px',
                    'textOverflow': 'ellipsis'
                }
            ],
            style_header={
                'backgroundColor': '#1a1a2e',
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'center',
                'padding': '15px',
                'fontSize': '15px'
            },
            style_data={
                'backgroundColor': 'white',
                'border': '1px solid #e0e0e0'
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#f8f9fa'},
                # Use same color for discrepancy-related columns so they read as a group
                # Use same color for discrepancy-related columns so they read as a group
                {'if': {'column_id': 'discrepancy'}, 'backgroundColor': '#fff8e6'},
                {'if': {'column_id': 'discrepancy_pct'}, 'backgroundColor': '#fff8e6'},
                {'if': {'column_id': 'safe_outcome'}, 'backgroundColor': '#fff8e6'},
                # Make Tips Value and Quick Suggestions share the same highlight/background
                {'if': {'column_id': 'value'}, 'backgroundColor': "#9da2e7"},
                {'if': {'column_id': 'quick_suggestions'}, 'backgroundColor': "#9da2e7"},
                {'if': {'state': 'active'}, 'backgroundColor': '#e3f2fd', 'border': '2px solid #2196F3'},
            ],
            css=[{
                'selector': 'tr:hover td',
                'rule': 'background-color: #e3f2fd !important; cursor: pointer;'
            }],
            page_size=25,
            page_action='native',
        )

    def _create_match_detail(self, match: Match, min_conf: float = 1.0) -> html.Div:
        """Create detailed match view."""
        # Calculate statistics safely
        unique_sources = len(set(tip.source for tip in match.predictions.tips)) if match.predictions.tips else 0
        avg_confidence = sum(tip.confidence for tip in match.predictions.tips) / len(match.predictions.tips) if match.predictions.tips else 0

        # Run analysis and extract value, team scores and suggestions
        analysis = self.analyzer.analyze_match(match)
        value = analysis.get('value', {}).get('score', 0.0)
        discrepancy_score = analysis.get('discrepancy', {}).get('score', 0.0)
        disc_details = analysis.get('discrepancy', {}).get('details', {})
        home_team_score = disc_details.get('home_team_score', getattr(match.home_team, 'league_points', 0))
        away_team_score = disc_details.get('away_team_score', getattr(match.away_team, 'league_points', 0))
        suggestions = analysis.get('suggestions', [])

        # Compute support counts per suggestion (use details.count when available, fallback to evidence_count)
        support_counts = []
        for s in suggestions:
            ev = s.get('evidence', []) or []
            if ev:
                # sum counts if present, otherwise count evidence items
                cnts = [e.get('details', {}).get('count') for e in ev if isinstance(e.get('details', {}), dict) and e.get('details', {}).get('count') is not None]
                if cnts:
                    support_counts.append(sum(cnts))
                else:
                    support_counts.append(len(ev))
            else:
                support_counts.append(0)

        max_support = max(2, max(support_counts) if support_counts else 2)

        return html.Div([
            # Match Header
            dbc.Card([
                dbc.CardBody([
                    html.H3(f"{match.home_team.name} vs {match.away_team.name}", className="text-center mb-2"),
                    html.H5(match.datetime.strftime('%A, %B %d, %Y at %H:%M'), className="text-center text-white-50"),
                ])
            ], className="mb-4 text-white", style={"background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"}),

            # Match Value & Overview
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="fas fa-star fa-2x mb-2", style={"color": self._get_value_color(value)}),
                            ], className="text-center"),
                            html.H5("Tips Value", className="card-title text-center text-muted"),
                            html.H2(f"{float(value):.2f}", className="text-center mb-0", style={"color": self._get_value_color(value)})
                        ])
                    ], className="shadow-sm h-100")
                ], md=4),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="fas fa-database fa-2x mb-2 text-primary"),
                            ], className="text-center"),
                            html.H5("Unique Sources", className="card-title text-center text-muted"),
                            html.H2(unique_sources, className="text-center text-primary mb-0")
                        ])
                    ], className="shadow-sm h-100")
                ], md=4),

                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.I(className="fas fa-exclamation-triangle fa-2x mb-2 text-warning"),
                            ], className="text-center"),
                            html.H5("Discrepancy", className="card-title text-center text-muted"),
                            html.H2(f"{float(discrepancy_score):.2f}", className="text-center text-warning mb-0")
                        ])
                    ], className="shadow-sm h-100")
                ], md=4),
            ], className="mb-4"),

            # Teams Comparison
            dbc.Row([
                # Home Team
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-home me-2"),
                            html.H4(match.home_team.name, className="d-inline")
                        ], className="bg-success text-white"),
                        dbc.CardBody([
                            html.Div([
                                html.Strong("League Points: "),
                                html.Span(str(match.home_team.league_points),
                                         style={"fontSize": "20px", "color": "#2196F3", "fontWeight": "bold"})
                            ], className="mb-3"),
                            html.Div([
                                html.Strong("Form: "),
                                self._render_form(match.home_team.form)
                            ], className="mb-3"),
                            html.Div([
                                html.Strong("Team Score: "),
                                html.Span(str(home_team_score),
                                         style={"fontSize": "20px", "fontWeight": "bold", "color": "#4CAF50"})
                            ])
                        ])
                    ], className="shadow-sm h-100")
                ], md=6, className="mb-3 mb-md-0"),

                # Away Team
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-plane me-2"),
                            html.H4(match.away_team.name, className="d-inline")
                        ], className="bg-info text-white"),
                        dbc.CardBody([
                            html.Div([
                                html.Strong("League Points: "),
                                html.Span(str(match.away_team.league_points),
                                         style={"fontSize": "20px", "color": "#2196F3", "fontWeight": "bold"})
                            ], className="mb-3"),
                            html.Div([
                                html.Strong("Form: "),
                                self._render_form(match.away_team.form)
                            ], className="mb-3"),
                            html.Div([
                                html.Strong("Team Score: "),
                                html.Span(str(away_team_score),
                                         style={"fontSize": "20px", "fontWeight": "bold", "color": "#4CAF50"})
                            ])
                        ])
                    ], className="shadow-sm h-100")
                ], md=6),
            ], className="mb-4"),

            # Combined probabilities & averaged predicted score (left/right)
            self._render_probabilities_and_scores(match.predictions.probabilities, match.predictions.scores),

            # Suggestions controls (min sources + min confidence) and container
            *([
                dbc.Row([
                    dbc.Col(html.H4([html.I(className="fas fa-lightbulb me-2"), "Aggregated Suggestions"], className="mb-3"), md=6),
                    dbc.Col(html.Div(), md=6),
                ], className="mb-2"),

                dbc.Row([
                    dbc.Col([
                        html.Label("Min Sources", className="fw-bold small mb-1"),
                        dcc.Slider(
                            id='suggestions-min-sources-slider',
                            min=2,
                            max=max_support,
                            step=1,
                            value=2,
                            marks={i: str(i) for i in range(2, max(3, max_support+1))},
                        )
                    ], md=6),
                    dbc.Col([
                        html.Label("Min Confidence (%)", className="fw-bold small mb-1"),
                        dcc.Slider(
                            id='suggestions-min-confidence-slider',
                            min=0,
                            max=100,
                            step=1,
                            value=75,
                            marks={0: '0', 25: '25', 50: '50', 75: '75', 100: '100'},
                        )
                    ], md=6),
                ], className="mb-3"),

                # Suggestions container: initial render (compact cards)
                html.Div(id='modal-suggestions-container', children=[
                    self._render_suggestions_section(suggestions, min_sources=2, min_conf=75, compact=True)
                ])
            ] if suggestions else []),

            # Tips header + filters (min sources + min confidence)
            dbc.Row([
                dbc.Col(html.H4([html.I(className="fas fa-lightbulb me-2"), "Betting Tips"], className="mb-3"), md=6),
                dbc.Col([
                    html.Label("Min Sources", className="fw-bold small mb-1"),
                    dcc.Slider(
                        id='tips-min-sources-slider',
                        min=1,
                        max=max(1, unique_sources),
                        step=1,
                        value=2,
                        marks={i: str(i) for i in range(1, max(2, unique_sources+1))},
                    )
                ], md=3),
                dbc.Col([
                    html.Label("Min Confidence (%)", className="fw-bold small mb-1"),
                    dcc.Slider(
                        id='tips-confidence-slider',
                        min=0,
                        max=100,
                        step=1,
                        value=75,
                        marks={0: '0', 50: '50', 100: '100'},
                    )
                ], md=3),
            ], className="align-items-center mb-3"),

            # Tips container: populated initially with slider defaults (min_conf=75, min_sources=2)
            html.Div(id='modal-tips-container', children=[
                # Initial render should match slider defaults: min_sources=2, min_conf=75
                self._render_tips_section(match.predictions.tips, min_conf=75, min_sources=2, show_header=False)
            ]),

            # Statistics Comparison
            self._render_statistics_comparison(match.home_team, match.away_team),

        ])

    def _render_probabilities_section(self, probabilities: List[Probability]) -> html.Div:
        """Render probabilities section."""
        if not probabilities:
            return html.Div()

        return html.Div([
            html.H4([html.I(className="fas fa-chart-pie me-2"), "Probabilities"], className="mb-3"),
            dbc.Card([
                dbc.CardBody([
                    *[self._render_probability(prob) for prob in probabilities]
                ])
            ], className="mb-4 shadow-sm")
        ])

    def _render_probabilities_and_scores(self, probabilities: List[Probability], scores: List[Score]) -> html.Div:
        """Render averaged probabilities (left) and averaged predicted score (right).

        Provides a collapsible per-source detail view when clicked.
        """
        # Defensive defaults
        probs = probabilities or []
        scores_list = scores or []

        # Average probabilities across sources
        avg_home = avg_draw = avg_away = 0.0
        if probs:
            avg_home = sum(getattr(p, 'home', 0.0) for p in probs) / len(probs)
            avg_draw = sum(getattr(p, 'draw', 0.0) for p in probs) / len(probs)
            avg_away = sum(getattr(p, 'away', 0.0) for p in probs) / len(probs)

        # Average predicted score
        avg_home_score = avg_away_score = None
        if scores_list:
            avg_home_score = sum(getattr(s, 'home', 0) for s in scores_list) / len(scores_list)
            avg_away_score = sum(getattr(s, 'away', 0) for s in scores_list) / len(scores_list)

        # Build per-source details HTML
        prob_details = []
        for p in probs:
            prob_details.append(html.Div([
                dbc.Badge(p.source, color='dark', className='me-2'),
                html.Span(f"Home {p.home}%, Draw {p.draw}%, Away {p.away}%")
            ], className='mb-1'))

        score_details = []
        for s in scores_list:
            score_details.append(html.Div([
                dbc.Badge(s.source, color='dark', className='me-2'),
                html.Span(f"{int(s.home)} - {int(s.away)}")
            ], className='mb-1'))

        left = dbc.Card([
            dbc.CardBody([
                html.H6("Averaged Probabilities", className='card-title mb-2'),
                dbc.Progress([
                    dbc.Progress(value=avg_home, label=f"Home {avg_home:.0f}%", color="success", bar=True),
                    dbc.Progress(value=avg_draw, label=f"Draw {avg_draw:.0f}%", color="warning", bar=True),
                    dbc.Progress(value=avg_away, label=f"Away {avg_away:.0f}%", color="info", bar=True),
                ], style={"height": "28px"}),
                html.Details([
                    html.Summary("Show per-source probabilities"),
                    html.Div(prob_details, style={"marginTop": "8px"})
                ], className='mt-2')
            ])
        ], className='shadow-sm')

        right_children = [
            html.H6("Averaged Prediction", className='card-title mb-2')
        ]
        if avg_home_score is not None and avg_away_score is not None:
            right_children.append(html.Div(html.Span(f"{avg_home_score:.1f} - {avg_away_score:.1f}", style={"fontSize": "24px", "fontWeight": "bold"})))
        else:
            right_children.append(html.Div("N/A"))

        right_children.append(html.Details([
            html.Summary("Show per-source predicted scores"),
            html.Div(score_details, style={"marginTop": "8px"})
        ], className='mt-2'))

        right = dbc.Card([
            dbc.CardBody(right_children)
        ], className='shadow-sm')

        return dbc.Row([
            dbc.Col(left, md=6),
            dbc.Col(right, md=6)
        ], className='mb-4')

    def _render_suggestions_section(self, suggestions: List[Dict[str, Any]], min_sources: int = 2, min_conf: float = 10.0, compact: bool = False) -> html.Div:
        """Render aggregated suggestions from MatchAnalyzer.

        Args:
            suggestions: list of merged suggestion dicts (with 'evidence' and 'evidence_count')
            min_sources: minimum evidence_count required to show a suggestion (inclusive)
            min_conf: minimum confidence (0..100) required to show a suggestion (inclusive)
            compact: if True, render suggestions as compact square cards similar to tip cards
        """
        if not suggestions:
            return html.Div()

        # Filter suggestions by provided thresholds.
        # For support count, prefer per-evidence 'details.count' when available (scores), otherwise fallback to evidence_count.
        def _support_count(sug: Dict[str, Any]) -> int:
            ev = sug.get('evidence', []) or []
            if not ev:
                return sug.get('evidence_count', 0)
            cnts = []
            for e in ev:
                try:
                    c = int(e.get('details', {}).get('count'))
                    cnts.append(c)
                except Exception:
                    # fallback
                    pass
            if cnts:
                return sum(cnts)
            return len(ev)

        try:
            filtered = [s for s in suggestions if _support_count(s) >= int(min_sources) and s.get('confidence', 0.0) >= float(min_conf)]
        except Exception:
            filtered = suggestions or []

        if not filtered:
            # Provide a small debug view so users can inspect analyzer output when filters hide everything
            try:
                dbg = json.dumps(suggestions, default=str, indent=2)
                if len(dbg) > 8000:
                    dbg = dbg[:8000] + "\n... (truncated)"
            except Exception:
                dbg = "(unable to serialize suggestions)"

            return html.Div([
                html.P("No suggestions meet the selected filters."),
                html.Details([
                    html.Summary("Show analyzer suggestions (debug)"),
                    html.Pre(dbg, style={"whiteSpace": "pre-wrap", "maxHeight": "300px", "overflowY": "auto"})
                ])
            ])

        # Sort by evidence_count then confidence
        sorted_sugs = sorted(filtered, key=lambda s: (s.get('evidence_count', 0), s.get('confidence', 0.0)), reverse=True)

        if compact:
            # Render compact cards (similar style to tip cards)
            cols = []
            for s in sorted_sugs:
                label = s.get('suggestion')
                conf = s.get('confidence', 0.0)

                # Confidence color mapping for suggestions (0..100)
                if conf >= 66:
                    conf_color = "#4CAF50"
                elif conf >= 33:
                    conf_color = "#ff9800"
                else:
                    conf_color = "#f44336"

                # Suggestion card: show label as primary info and confidence; no source/evidence
                card = dbc.Card([
                    dbc.CardBody([
                        html.H6(label, className="card-title mb-2 text-info"),
                        html.Div([
                            html.Strong("Confidence: "),
                            html.Span(f"{conf}%", style={"color": conf_color, "fontWeight": "bold"})
                        ], className="mb-1")
                    ])
                ], className="mb-3 h-100 shadow-sm", style={"borderLeft": f"5px solid {conf_color}"})

                cols.append(dbc.Col(card, lg=3, md=4, sm=6))

            return dbc.Row(cols, className="mb-4")

        # Full view: show evidence details
        items = []
        for s in sorted_sugs:
            label = s.get('suggestion')
            conf = s.get('confidence', 0.0)
            evidence = s.get('evidence', []) or []
            evidence_count = s.get('evidence_count', len(evidence))

            # Confidence color mapping for suggestions (0..100)
            if conf >= 66:
                conf_color = "#4CAF50"
            elif conf >= 33:
                conf_color = "#ff9800"
            else:
                conf_color = "#f44336"

            # Build a compact evidence list view
            evidence_rows = []
            for ev in evidence:
                ev_src = ev.get('source')
                ev_conf = ev.get('confidence')
                ev_details = ev.get('details', {})
                evidence_rows.append(html.Div([
                    dbc.Badge(ev_src or 'unknown', color='dark', className='me-2'),
                    html.Span(f"{ev_conf}%", style={"fontWeight": "bold", "marginRight": "8px"}),
                    html.Span(json.dumps(ev_details, default=str))
                ], style={"marginBottom": "6px"}))

            items.append(
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col(html.H6(f"{label}", className="card-title mb-0")),
                            dbc.Col(html.H5(f"{conf}%", className="text-end", style={"color": conf_color, "fontWeight": "bold"}), width=2)
                        ], align='center'),
                        html.Div([html.Strong(f"Evidence ({evidence_count}):")], className='mt-2'),
                        html.Div(evidence_rows, style={"whiteSpace": "pre-wrap", "marginTop": "6px"})
                    ])
                ], className="mb-2")
            )

        return html.Div([
            dbc.Card([
                dbc.CardBody(items)
            ], className="mb-4 shadow-sm")
        ])

    def _render_scores_section(self, scores: List[Score]) -> html.Div:
        """Render predicted scores section."""
        if not scores:
            return html.Div()

        return html.Div([
            html.H4([html.I(className="fas fa-bullseye me-2"), "Predicted Scores"], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            dbc.Badge(score.source, color="primary", className="mb-2"),
                            html.Div([
                                html.Span(f"{int(score.home)} - {int(score.away)}",
                                         style={"fontSize": "24px", "fontWeight": "bold"})
                            ], className="text-center")
                        ], className="text-center")
                    ], className="shadow-sm")
                ], lg=3, md=4, sm=6, xs=12, className="mb-3") for score in scores
            ], className="mb-4")
        ])

    def _render_tips_section(self, tips: List[Tip], min_conf: float = 0.0, min_sources: int = 2, show_header: bool = True) -> html.Div:
        """Render aggregated tips section.

        Merges tips that normalize to the same text (via Tip.to_text()), averages confidence
        (0-100), picks minimum odds among sources (if any), and collects all source labels.

        Args:
            tips: list of Tip objects
            min_conf: minimum average confidence (0..100) to show an aggregated tip
            min_sources: minimum unique sources required to show the aggregated tip (default 2)
            show_header: whether to render the 'Betting Tips' header
        """
        if not tips:
            return html.Div()

        # Group tips by normalized text
        groups = {}
        for t in tips:
            try:
                key = t.to_text()
            except Exception:
                key = getattr(t, 'raw_text', '') or ''

            if not key:
                continue

            groups.setdefault(key, []).append(t)

        # Build aggregated entries
        aggregated = []
        for label, group in groups.items():
            sources = [getattr(t, 'source', 'unknown') for t in group]
            unique_sources = len(set(sources))
            # average confidence (expecting 0..100)
            confs = [float(getattr(t, 'confidence', 0) or 0) for t in group]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            # minimum odds among available ones
            odds_list = [float(t.odds) for t in group if getattr(t, 'odds', None) is not None]
            min_odds = min(odds_list) if odds_list else None

            aggregated.append({
                'label': label,
                'avg_confidence': avg_conf,
                'sources': list(dict.fromkeys(sources)),
                'unique_sources': unique_sources,
                'count': len(group),
                'min_odds': min_odds,
                'items': group,
            })

        # Filter by thresholds
        try:
            filtered = [a for a in aggregated if a['avg_confidence'] >= float(min_conf) and a['unique_sources'] >= int(min_sources)]
        except Exception:
            filtered = aggregated

        if not filtered:
            return html.Div([html.P("No tips meet the selected filters.")])

        # Sort by number of unique sources then confidence
        sorted_agg = sorted(filtered, key=lambda a: (a['unique_sources'], a['avg_confidence']), reverse=True)

        children = []
        if show_header:
            children.append(html.H4([html.I(className="fas fa-lightbulb me-2"), "Betting Tips"], className="mb-3"))

        cards = []
        for a in sorted_agg:
            # Color mapping based on avg_confidence
            conf = a['avg_confidence']
            if conf >= 66:
                conf_color = "#4CAF50"
            elif conf >= 33:
                conf_color = "#ff9800"
            else:
                conf_color = "#f44336"

            src_badges = [dbc.Badge(s, color='dark', className='me-1') for s in a['sources']]
            odds_text = f"{a['min_odds']:.2f}" if a['min_odds'] is not None else "N/A"

            card = dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(html.H6(a['label'], className="card-title mb-0")),
                        dbc.Col(html.H5(f"{conf:.0f}%", className="text-end", style={"color": conf_color, "fontWeight": "bold"}), width=3)
                    ], align='center'),
                    html.Div([html.Strong("Sources: "), html.Span(src_badges)] , className='mt-2'),
                    html.Div([html.Strong("Odds (min): "), html.Span(odds_text)], className='mt-2')
                ])
            ], className='mb-3 h-100 shadow-sm', style={"borderLeft": f"5px solid {conf_color}"})

            cards.append(dbc.Col(card, lg=3, md=4, sm=12))

        children.append(dbc.Row(cards, className='mb-4'))
        return html.Div(children)

    def _render_form(self, form: str) -> html.Div:
        """Render team form with colored badges."""
        if not form:
            return html.Span("N/A", className="text-muted")

        badges = []
        for result in form:
            if result == 'W':
                color = "success"
                icon = "✓"
            elif result == 'D':
                color = "warning"
                icon = "−"
            else:
                color = "danger"
                icon = "✗"

            badges.append(
                dbc.Badge(icon, color=color, className="me-1", pill=True, style={"fontSize": "14px", "padding": "6px 10px"})
            )

        return html.Div(badges, style={"display": "inline-block"})

    def _render_probability(self, prob: Probability) -> html.Div:
        """Render probability bar chart."""
        total = prob.home + prob.draw + prob.away
        home_pct = (prob.home / total * 100) if total > 0 else 0
        draw_pct = (prob.draw / total * 100) if total > 0 else 0
        away_pct = (prob.away / total * 100) if total > 0 else 0

        return html.Div([
            html.Div([
                dbc.Badge(prob.source, color="primary", className="me-2"),
                html.Span("Source", className="text-muted small")
            ], className="mb-2"),
            dbc.Progress([
                dbc.Progress(value=home_pct, label=f"Home {int(prob.home)}%", color="success", bar=True, style={"fontSize": "13px"}),
                dbc.Progress(value=draw_pct, label=f"Draw {int(prob.draw)}%", color="warning", bar=True, style={"fontSize": "13px"}),
                dbc.Progress(value=away_pct, label=f"Away {int(prob.away)}%", color="info", bar=True, style={"fontSize": "13px"}),
            ], className="mb-3", style={"height": "35px"})
        ])

    def _render_h2h(self, h2h: H2H, home_name: str, away_name: str) -> html.Div:
        """Render head-to-head statistics."""
        total = h2h.home + h2h.draw + h2h.away
        if total == 0:
            return html.Div()

        return html.Div([
            html.H4([html.I(className="fas fa-history me-2"), "Head to Head"], className="mb-3"),
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Div(home_name, className="text-center fw-bold mb-2 small text-muted"),
                            html.H2(str(h2h.home), className="text-center text-success mb-0")
                        ], md=4),
                        dbc.Col([
                            html.Div("Draws", className="text-center fw-bold mb-2 small text-muted"),
                            html.H2(str(h2h.draw), className="text-center text-warning mb-0")
                        ], md=4),
                        dbc.Col([
                            html.Div(away_name, className="text-center fw-bold mb-2 small text-muted"),
                            html.H2(str(h2h.away), className="text-center text-info mb-0")
                        ], md=4),
                    ])
                ])
            ], className="mb-4 shadow-sm")
        ])

    def _render_tip(self, tip: Tip) -> dbc.Card:
        """Render individual tip card."""
        confidence_color = self._get_confidence_color(tip.confidence)

        # Get tip text from raw_text if available, fallback to tip
        tip_text = getattr(tip, 'raw_text', None) or getattr(tip, 'tip', 'No tip text')

        # Handle odds safely
        odds_value = tip.odds if tip.odds is not None and tip.odds > 0 else None

        return dbc.Card([
            dbc.CardBody([
                html.H6(tip_text, className="card-title mb-3"),
                html.Div([
                    html.I(className="fas fa-chart-line me-2"),
                    html.Strong("Confidence: "),
                    html.Span(f"{tip.confidence:.2f}",
                             style={"color": confidence_color, "fontSize": "18px", "fontWeight": "bold"})
                ], className="mb-2"),
                html.Div([
                    html.I(className="fas fa-coins me-2"),
                    html.Strong("Odds: "),
                    html.Span(f"{odds_value:.2f}" if odds_value else "N/A", className="text-muted")
                ], className="mb-2"),
                html.Div([
                    dbc.Badge(tip.source, color="dark", pill=True, className="mt-2")
                ], className="text-end")
            ])
        ], className="mb-3 h-100 shadow-sm", style={"borderLeft": f"5px solid {confidence_color}"})

    def _render_statistics_comparison(self, home_team: Team, away_team: Team) -> html.Div:
        """Render statistics comparison between teams."""
        # Check if either team has no statistics
        if not home_team.statistics or not away_team.statistics:
            return html.Div()

        stats = [
            ("Avg Corners", "avg_corners"),
            ("Avg Offsides", "avg_offsides"),
            ("Avg GK Saves", "avg_gk_saves"),
            ("Avg Yellow Cards", "avg_yellow_cards"),
            ("Avg Fouls", "avg_fouls"),
            ("Avg Tackles", "avg_tackles"),
            ("Avg Scored", "avg_scored"),
            ("Avg Conceded", "avg_conceded"),
            ("Avg Shots on Target", "avg_shots_on_target"),
            ("Avg Possession", "avg_possession"),
        ]

        rows = []
        has_any_stat = False

        for label, attr in stats:
            home_val = getattr(home_team.statistics, attr, None)
            away_val = getattr(away_team.statistics, attr, None)

            # Skip if both values are None or 0
            if (home_val is None or home_val == 0) and (away_val is None or away_val == 0):
                continue

            has_any_stat = True

            # Convert to string, handle None
            home_str = str(home_val) if home_val is not None else "N/A"
            away_str = str(away_val) if away_val is not None else "N/A"

            # Convert possession to numeric for comparison
            if attr == "avg_possession":
                try:
                    home_num = float(home_val.replace("%", "")) if isinstance(home_val, str) else float(home_val) if home_val else 0
                    away_num = float(away_val.replace("%", "")) if isinstance(away_val, str) else float(away_val) if away_val else 0
                except:
                    home_num = 0
                    away_num = 0
            else:
                home_num = float(home_val) if home_val is not None else 0
                away_num = float(away_val) if away_val is not None else 0

            # Determine better stat (lower is better for conceded, fouls, cards)
            if attr in ["avg_conceded", "avg_fouls", "avg_yellow_cards"]:
                home_better = home_num < away_num and home_num > 0
            else:
                home_better = home_num > away_num

            rows.append(
                html.Tr([
                    html.Td(home_str, style={
                        "fontWeight": "bold" if home_better else "normal",
                        "color": "#4CAF50" if home_better else "inherit",
                        "fontSize": "15px"
                    }),
                    html.Td(label, className="text-center fw-bold text-muted"),
                    html.Td(away_str, style={
                        "fontWeight": "bold" if not home_better and away_num > 0 else "normal",
                        "color": "#4CAF50" if not home_better and away_num > 0 else "inherit",
                        "fontSize": "15px"
                    }, className="text-end"),
                ])
            )

        # If no statistics to show, return empty div
        if not has_any_stat:
            return html.Div()

        # Ensure each cell uses equal width thirds for consistent sizing
        styled_rows = []
        for tr in rows:
            # tr is already an html.Tr built above with three html.Td; set widths
            # We assume each tr.children is a list of three td elements
            tds = tr.children
            new_tds = []
            for i, td in enumerate(tds):
                styles = td.get('props', {}).get('style', {}) if hasattr(td, 'get') else {}
                # merge width style
                merged = {**styles, 'width': '33%'}
                # rebuild td with same children and new style
                new_tds.append(html.Td(td.children, style=merged, className=td.props.get('className', '') if hasattr(td, 'props') else None))
            styled_rows.append(html.Tr(new_tds))

        return html.Div([
            html.H4([html.I(className="fas fa-chart-bar me-2"), "Statistics Comparison"], className="mb-3"),
            dbc.Card([
                dbc.CardBody([
                    dbc.Table([
                        html.Thead([
                            html.Tr([
                                html.Th(home_team.name, className="text-start bg-success text-white", style={"width": "33%"}),
                                html.Th("Statistic", className="text-center bg-light", style={"width": "33%"}),
                                html.Th(away_team.name, className="text-end bg-info text-white", style={"width": "33%"}),
                            ])
                        ]),
                        html.Tbody(styled_rows)
                    ], bordered=True, hover=True, responsive=True, striped=True)
                ])
            ], className="shadow-sm")
        ])

    def _get_value_color(self, value: int) -> str:
        """Get color based on match value."""
        if value >= 5:
            return "#f44336"  # Red - high value
        elif value >= 3.5:
            return "#ff9800"  # Orange
        else:
            return "#4CAF50"  # Green - low value

    def _get_confidence_color(self, confidence: float) -> str:
        """Get color based on confidence level."""
        if confidence >= 75:
            return "#4CAF50"  # Green - high confidence
        elif confidence >= 50:
            return "#ff9800"  # Orange
        else:
            return "#f44336"  # Red - low confidence

    def _setup_callbacks(self):
        """Setup all dashboard callbacks."""

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
            ]
        )
        def update_table(data_json, search_text, date_from, date_to, discrepancy_filter):
            if not data_json:
                return dbc.Alert("No data available. Click Refresh to load matches.", color="warning")

            df = pd.read_json(StringIO(data_json), orient='split')

            # Apply filters
            if search_text:
                mask = df['home'].str.contains(search_text, case=False, na=False) | \
                       df['away'].str.contains(search_text, case=False, na=False)
                df = df[mask]

            if date_from:
                df = df[df['timestamp'] >= pd.to_datetime(date_from)]

            if date_to:
                df = df[df['timestamp'] <= pd.to_datetime(date_to) + pd.Timedelta(days=1)]

            # Apply discrepancy % filter if provided
            try:
                if discrepancy_filter is not None and discrepancy_filter > 0:
                    # ensure column exists
                    if 'discrepancy_pct' in df.columns:
                        df = df[df['discrepancy_pct'] >= float(discrepancy_filter)]
            except Exception:
                pass

            return self._create_table(df)

        @self.app.callback(
            Output('discrepancy-filter-value', 'children'),
            Input('discrepancy-filter-slider', 'value'),
            prevent_initial_call=False
        )
        def update_discrepancy_value(val):
            try:
                return str(int(val))
            except Exception:
                return '0'

        @self.app.callback(
            [
                Output("match-modal", "is_open"),
                Output("modal-title", "children"),
                Output("modal-body", "children"),
                Output("current-match-id", "data"),
            ],
            [
                Input("matches-table", "active_cell"),
                Input("close-modal", "n_clicks"),
            ],
            [State("match-modal", "is_open"), State("matches-table", "derived_virtual_data")],
            prevent_initial_call=True
        )
        def toggle_modal(active_cell, close_clicks, is_open, derived_virtual_data):
            ctx = callback_context
            if not ctx.triggered:
                return False, "", "", None

            trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

            if trigger_id == "close-modal":
                return False, "", "", None

            # Use derived_virtual_data which reflects current sorting/filtering/pagination
            if trigger_id == "matches-table" and active_cell and derived_virtual_data:
                # Prefer row_id if provided (more robust across pagination)
                row_id = active_cell.get('row_id') if isinstance(active_cell, dict) else None
                if row_id:
                    match_id = row_id
                    if match_id and match_id in self.matches_dict:
                        match = self.matches_dict[match_id]
                        return True, "Match Details", self._create_match_detail(match, min_conf=1.0), match_id

                row_idx = active_cell.get('row') if isinstance(active_cell, dict) else None
                # Some versions of DataTable may provide row as int; guard against None
                if row_idx is None:
                    return is_open, "", "", None

                # Ensure the row index exists in the currently displayed data
                if derived_virtual_data and 0 <= row_idx < len(derived_virtual_data):
                    row = derived_virtual_data[row_idx]
                    match_id = row.get('match_id') or row.get('id')
                    # Look up the match in our dictionary
                    if match_id and match_id in self.matches_dict:
                        match = self.matches_dict[match_id]
                        # return modal open, title, body and store the current match id
                        return True, "Match Details", self._create_match_detail(match, min_conf=1.0), match_id

            return is_open, "", "", None

        @self.app.callback(
            Output("modal-tips-container", "children"),
            [
                Input("tips-confidence-slider", "value"),
                Input("tips-min-sources-slider", "value")
            ],
            State("current-match-id", "data"),
            prevent_initial_call=True
        )
        def update_modal_tips(min_conf, min_sources, match_id):
            # When slider changes, re-render the tips area for the currently open match
            if not match_id or match_id not in self.matches_dict:
                return html.Div()

            match = self.matches_dict.get(match_id)
            tips = []
            try:
                preds = getattr(match, 'predictions', None)
                tips = preds.tips if preds and getattr(preds, 'tips', None) else []
            except Exception:
                tips = []

            # Ensure a sensible minimum of 2 sources when slider is unset/null
            return self._render_tips_section(tips, min_conf=(min_conf or 0), min_sources=(min_sources or 2), show_header=False)

        @self.app.callback(
            Output("modal-suggestions-container", "children"),
            [
                Input("suggestions-min-sources-slider", "value"),
                Input("suggestions-min-confidence-slider", "value")
            ],
            State("current-match-id", "data"),
            prevent_initial_call=True
        )
        def update_modal_suggestions(min_sources, min_conf, match_id):
            if not match_id or match_id not in self.matches_dict:
                return html.Div()

            match = self.matches_dict.get(match_id)
            try:
                analysis = self.analyzer.analyze_match(match) or {}
                suggestions = analysis.get('suggestions', [])
            except Exception:
                suggestions = []

            # min_conf slider supplies values 10..100 (percent)
            return self._render_suggestions_section(suggestions, min_sources=min_sources or 2, min_conf=min_conf or 10, compact=True)

    def run(self, debug=True, port=8050):
        """Run the dashboard server."""
        print(f"Starting dashboard on http://localhost:{port}")
        self.app.run(debug=debug, port=port)

if __name__ == "__main__":
    from bet_framework.DatabaseManager import DatabaseManager
    db_manager = DatabaseManager()
    dashboard = MatchesDashboard(db_manager)
    dashboard.run(debug=True, port=8050)