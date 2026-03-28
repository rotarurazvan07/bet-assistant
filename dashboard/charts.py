"""
dashboard/charts.py
════════════════════
All Plotly chart builders.

Every function is pure:
  • takes plain data (lists / dicts / DataFrames)
  • returns a dcc.Graph or dbc.Alert
  • imports styling tokens from constants.py
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from dashboard.constants import CHART_COLORS, CHART_LAYOUT, COLORS

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _empty_chart(message: str) -> dbc.Alert:
    """Placeholder shown when there is no data yet."""
    return dbc.Alert(
        [html.I(className="fas fa-hourglass-half me-2"), message],
        color="info",
        className="m-2",
    )


def render_history_charts(daily_summary: list[dict]):
    if not daily_summary:
        return [_empty_chart("No history data yet.")]

    dates = [d["date"] for d in daily_summary]

    # 1. Total Bet units over time
    fig_bet = go.Figure(layout=CHART_LAYOUT)
    fig_bet.add_trace(
        go.Scatter(
            x=dates,
            y=[d["cumulative_bet"] for d in daily_summary],
            name="Total Bet",
            line=dict(color=CHART_COLORS[0], width=3),
            fill="tozeroy",
            fillcolor="rgba(0, 123, 255, 0.1)",
        )
    )
    fig_bet.update_layout(
        title="Cumulative Units Bet", xaxis_title="Date", yaxis_title="Units"
    )

    # 2. Total Profit over time
    fig_profit = go.Figure(layout=CHART_LAYOUT)
    fig_profit.add_trace(
        go.Scatter(
            x=dates,
            y=[d["cumulative_profit"] for d in daily_summary],
            name="Profit",
            line=dict(
                color=COLORS["success"]
                if daily_summary[-1]["cumulative_profit"] >= 0
                else COLORS["danger"],
                width=3,
            ),
            fill="tozeroy",
            fillcolor="rgba(40, 167, 69, 0.1)",
        )
    )
    fig_profit.update_layout(
        title="Cumulative Net Profit", xaxis_title="Date", yaxis_title="Units"
    )

    # 3. ROI over time
    fig_roi = go.Figure(layout=CHART_LAYOUT)
    fig_roi.add_trace(
        go.Scatter(
            x=dates,
            y=[d["roi_percentage"] for d in daily_summary],
            name="ROI %",
            line=dict(color=CHART_COLORS[2], width=2),
        )
    )
    fig_roi.update_layout(
        title="ROI % Over Time", xaxis_title="Date", yaxis_title="ROI %"
    )

    # 4. Win Rate over time
    fig_winrate = go.Figure(layout=CHART_LAYOUT)
    fig_winrate.add_trace(
        go.Scatter(
            x=dates,
            y=[d["win_rate"] for d in daily_summary],
            name="Win Rate %",
            line=dict(color=CHART_COLORS[3], width=2),
        )
    )
    fig_winrate.update_layout(
        title="Win Rate % Over Time", xaxis_title="Date", yaxis_title="Win Rate %"
    )

    return [_graph(fig_bet), _graph(fig_profit), _graph(fig_roi), _graph(fig_winrate)]


def render_market_accuracy_chart(market_stats: list[dict]):
    if not market_stats:
        return _empty_chart("No market data yet.")

    mtypes = [m["market"] for m in market_stats]
    won = [m["won"] for m in market_stats]
    lost = [m["lost"] for m in market_stats]

    fig = go.Figure(layout=CHART_LAYOUT)
    fig.add_trace(go.Bar(name="Won", x=mtypes, y=won, marker_color=COLORS["success"]))
    fig.add_trace(go.Bar(name="Lost", x=mtypes, y=lost, marker_color=COLORS["danger"]))

    fig.update_layout(
        barmode="group",
        title="Market Accuracy (Won vs Lost)",
        xaxis_title="Market Type",
        yaxis_title="Count",
    )
    return _graph(fig)


def render_correlation_charts(correlation_data: list[dict]):
    if not correlation_data:
        return [_empty_chart("No correlation data yet.")]

    df = pd.DataFrame(correlation_data)

    # 1. Legs count vs Win Rate
    legs_stats = (
        df.groupby("legs_count")
        .agg(total=("status", "count"), won=("status", lambda x: (x == "Won").sum()))
        .reset_index()
    )
    legs_stats["win_rate"] = (legs_stats["won"] / legs_stats["total"]) * 100

    fig_legs = go.Figure(layout=CHART_LAYOUT)
    fig_legs.add_trace(
        go.Bar(
            x=legs_stats["legs_count"],
            y=legs_stats["win_rate"],
            marker_color=CHART_COLORS[4],
        )
    )
    fig_legs.update_layout(
        title="Win Rate by Number of Legs",
        xaxis_title="Number of Legs",
        yaxis_title="Win Rate %",
    )

    # 2. Profit Distribution by Legs Count
    fig_profit_legs = go.Figure(layout=CHART_LAYOUT)
    for legs in sorted(df["legs_count"].unique()):
        fig_profit_legs.add_trace(
            go.Box(y=df[df["legs_count"] == legs]["profit"], name=f"{legs} Legs")
        )
    fig_profit_legs.update_layout(
        title="Profit Distribution by Legs Count",
        xaxis_title="Number of Legs",
        yaxis_title="Profit (Units)",
    )

    return [_graph(fig_legs), _graph(fig_profit_legs)]


def _graph(fig: go.Figure) -> dcc.Graph:
    return dcc.Graph(figure=fig, config={"displayModeBar": False})
