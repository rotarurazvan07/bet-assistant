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

from collections import defaultdict
from typing import Any, List

import pandas as pd
import plotly.graph_objects as go
from dash import dcc
import dash_bootstrap_components as dbc
from dash import html

from dashboard.constants import CHART_COLORS, CHART_LAYOUT, COLORS


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _empty_chart(message: str) -> dbc.Alert:
    """Placeholder shown when there is no data yet."""
    return dbc.Alert(
        [html.I(className="fas fa-hourglass-half me-2"), message],
        color="info", className="m-2",
    )


def _graph(fig: go.Figure) -> dcc.Graph:
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Balance curve
# ─────────────────────────────────────────────────────────────────────────────

def render_balance_chart(history: list) -> Any:
    """
    Running cumulative net-profit chart.
    Shows one line per profile + a bold combined line.
    When the filter is for a single profile the combined line is omitted.
    """
    if not history:
        return _empty_chart("No settled slips yet — balance chart will appear here.")

    by_profile: dict = defaultdict(list)
    for item in history:
        by_profile[item["profile"]].append(item)

    show_combined = len(by_profile) > 1
    fig = go.Figure()

    if show_combined:
        cum, dates, vals = 0.0, [], []
        for item in history:
            net   = (item["total_odds"] - 1) * item["units"] if item["status"] == "Won" else -item["units"]
            cum  += net
            dates.append(item["date"])
            vals.append(round(cum, 2))

        fig.add_trace(go.Scatter(
            x=dates, y=vals, mode="lines+markers",
            name="All Profiles",
            line=dict(color=COLORS["accent"], width=3),
            marker=dict(size=5),
        ))

    for i, (profile, items) in enumerate(by_profile.items()):
        cum, dates, vals = 0.0, [], []
        for item in items:
            net   = (item["total_odds"] - 1) * item["units"] if item["status"] == "Won" else -item["units"]
            cum  += net
            dates.append(item["date"])
            vals.append(round(cum, 2))

        color = CHART_COLORS[i % len(CHART_COLORS)]
        fig.add_trace(go.Scatter(
            x=dates, y=vals, mode="lines+markers",
            name=profile.upper(),
            line=dict(color=color, width=2,
                      dash="dot" if show_combined else "solid"),
            marker=dict(size=5),
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="#adb5bd", line_width=1)
    fig.update_layout(**CHART_LAYOUT)
    fig.update_layout(
        yaxis_title="Net Profit (Units)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _graph(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Profile ROI comparison
# ─────────────────────────────────────────────────────────────────────────────

def render_profile_comparison(per_profile: dict) -> Any:
    """Horizontal bar chart — ROI % per profile."""
    if not per_profile:
        return _empty_chart("No profile data yet.")

    profiles    = sorted(per_profile.keys())
    rois        = [per_profile[p]["roi"]        for p in profiles]
    net_profits = [per_profile[p]["net_profit"] for p in profiles]
    settled     = [per_profile[p]["settled"]    for p in profiles]
    win_rates   = [per_profile[p]["win_rate"]   for p in profiles]

    bar_colors = [COLORS["success"] if r >= 0 else COLORS["danger"] for r in rois]

    fig = go.Figure(go.Bar(
        y=[p.upper() for p in profiles], x=rois,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{r:+.1f}%" for r in rois], textposition="outside",
        customdata=list(zip(net_profits, settled, win_rates)),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "ROI: %{x:+.1f}%<br>"
            "Net Profit: %{customdata[0]:+.2f}u<br>"
            "Settled: %{customdata[1]}<br>"
            "Win Rate: %{customdata[2]}%"
            "<extra></extra>"
        ),
    ))

    fig.add_vline(x=0, line_dash="dash", line_color="#adb5bd", line_width=1)
    fig.update_layout(**CHART_LAYOUT)
    fig.update_layout(
        xaxis_title="ROI %",
        xaxis=dict(gridcolor="#f0f0f0", zeroline=False),
        yaxis=dict(gridcolor=None, showgrid=False),
        showlegend=False,
        bargap=0.35,
    )
    return _graph(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Market accuracy
# ─────────────────────────────────────────────────────────────────────────────

def render_market_accuracy(market_stats: list) -> Any:
    """
    Stacked bar (Won / Lost counts) per market with a win-rate line
    on a secondary axis. Markets sorted by win rate descending.
    """
    if not market_stats:
        return _empty_chart("No market data yet.")

    agg: dict = defaultdict(lambda: {"won": 0, "lost": 0})
    for row in market_stats:
        m = row["market"]
        if row["status"] == "Won":
            agg[m]["won"]  += row["count"]
        else:
            agg[m]["lost"] += row["count"]

    markets = sorted(
        agg.keys(),
        key=lambda m: (agg[m]["won"] / (agg[m]["won"] + agg[m]["lost"])
                       if (agg[m]["won"] + agg[m]["lost"]) else 0),
        reverse=True,
    )

    won_counts  = [agg[m]["won"]  for m in markets]
    lost_counts = [agg[m]["lost"] for m in markets]
    totals      = [agg[m]["won"] + agg[m]["lost"] for m in markets]
    win_rates   = [round(agg[m]["won"] / t * 100, 1) if t else 0
                   for m, t in zip(markets, totals)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=markets, y=won_counts, name="Won",
        marker_color=COLORS["success"],
        text=won_counts, textposition="inside", insidetextanchor="middle",
    ))
    fig.add_trace(go.Bar(
        x=markets, y=lost_counts, name="Lost",
        marker_color=COLORS["danger"],
        text=lost_counts, textposition="inside", insidetextanchor="middle",
    ))
    fig.add_trace(go.Scatter(
        x=markets, y=win_rates,
        mode="lines+markers+text", name="Win Rate %",
        yaxis="y2",
        line=dict(color=COLORS["accent"], width=2),
        marker=dict(size=8),
        text=[f"{w}%" for w in win_rates],
        textposition="top center",
        textfont=dict(size=10, color=COLORS["accent"]),
    ))

    fig.update_layout(**CHART_LAYOUT)
    fig.update_layout(
        barmode="stack",
        yaxis=dict(title="Legs", gridcolor="#f0f0f0"),
        yaxis2=dict(
            title="Win Rate %", overlaying="y", side="right",
            range=[0, 125], showgrid=False, zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor="#f0f0f0"),
    )
    return _graph(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Source reliability
# ─────────────────────────────────────────────────────────────────────────────

def render_source_analysis(settled_legs: list, analyzer_df: pd.DataFrame) -> Any:
    """
    Correlates number of data sources with leg win rate.
    Joins settled leg outcomes with the match DataFrame on result_url.
    """
    if not settled_legs:
        return _empty_chart("No settled legs yet for source analysis.")

    if analyzer_df is None or analyzer_df.empty:
        return _empty_chart("Match data not loaded — click Refresh Data first.")

    legs_df = pd.DataFrame(settled_legs)
    merged  = legs_df.merge(
        analyzer_df[["result_url", "sources"]].drop_duplicates("result_url"),
        on="result_url", how="inner",
    )

    if merged.empty:
        return _empty_chart(
            "No overlap between settled legs and current match data. "
            "The matches may have aged out of the DB."
        )

    max_s        = int(merged["sources"].max()) if not merged.empty else 7
    BUCKET_ORDER = ["1"] + [f"{i}-{i+2}" for i in range(2, max_s - 1, 3)]

    if BUCKET_ORDER and int(BUCKET_ORDER[-1].split("-")[-1]) < max_s:
        BUCKET_ORDER.append(f"{int(BUCKET_ORDER[-1].split('-')[-1]) + 1}+")
    elif BUCKET_ORDER:
        BUCKET_ORDER[-1] = BUCKET_ORDER[-1].split("-")[0] + "+"

    def _bucket(n: int) -> str:
        if n <= 1:
            return "1"
        for b in BUCKET_ORDER[1:]:
            if "+" in b:
                return b
            low, high = map(int, b.split("-"))
            if low <= n <= high:
                return b
        return BUCKET_ORDER[-1]

    merged["bucket"] = merged["sources"].apply(_bucket)

    counts: dict = defaultdict(lambda: {"won": 0, "total": 0})
    for _, row in merged.iterrows():
        b = row["bucket"]
        counts[b]["total"] += 1
        if row["status"] == "Won":
            counts[b]["won"] += 1

    labels    = [b for b in BUCKET_ORDER if b in counts]
    totals    = [counts[b]["total"] for b in labels]
    win_rates = [
        round(counts[b]["won"] / counts[b]["total"] * 100, 1)
        if counts[b]["total"] else 0
        for b in labels
    ]

    bar_colors = [
        COLORS["success"] if w >= 55 else COLORS["warning"] if w >= 40 else COLORS["danger"]
        for w in win_rates
    ]

    fig = go.Figure(go.Bar(
        x=labels, y=win_rates,
        marker_color=bar_colors,
        text=[f"{w}%<br><sub style='font-size:9px'>n={t}</sub>"
              for w, t in zip(win_rates, totals)],
        textposition="outside",
        hovertemplate=(
            "<b>Sources: %{x}</b><br>"
            "Win Rate: %{y:.1f}%<br>"
            "Legs: %{customdata}<extra></extra>"
        ),
        customdata=totals,
    ))

    fig.add_hline(
        y=50, line_dash="dash", line_color="#adb5bd", line_width=1,
        annotation_text="50% baseline",
        annotation_position="top right",
        annotation_font_size=10,
    )
    fig.update_layout(**CHART_LAYOUT)
    fig.update_layout(
        xaxis_title="Number of Sources Backing the Pick",
        yaxis_title="Win Rate %",
        yaxis=dict(range=[0, 115], gridcolor="#f0f0f0"),
        xaxis=dict(
            gridcolor="#f0f0f0",
            categoryorder="array",
            categoryarray=BUCKET_ORDER,
        ),
        showlegend=False,
    )
    return _graph(fig)