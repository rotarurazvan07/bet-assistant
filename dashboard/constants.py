"""
dashboard/constants.py
══════════════════════
Single source of truth for:
  • Style tokens  (colours, fonts, border radii, shadows …)
  • Chart tokens  (_CHART_LAYOUT, _CHART_COLORS)
  • Tooltip text  (TOOLTIP_TEXTS)
  • Config field metadata  (ALL_MARKET_TYPES, _NULLABLE_CONFIG_FIELDS, …)

Every other module imports from here — nothing is hard-coded elsewhere.
"""

from typing import Dict, List

# ─────────────────────────────────────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────────────────────────────────────

COLORS = {
    # Brand / primary
    "primary":       "#4361ee",
    "primary_dark":  "#3f37c9",
    "accent":        "#764ba2",

    # Semantic
    "success":       "#28a745",
    "danger":        "#dc3545",
    "warning":       "#fd7e14",
    "info":          "#17a2b8",
    "live":          "#ff4b4b",

    # Neutral
    "bg_page":       "#f8f9fe",
    "bg_card":       "#ffffff",
    "bg_light":      "#f8f9fa",
    "border":        "#dee2e6",
    "border_subtle": "#e9ecef",
    "muted":         "#6c757d",
    "text_dark":     "#212529",

    # Status backgrounds
    "bg_won":        "#d1e7dd",
    "bg_lost":       "#f8d7da",
    "bg_pending":    "#f8f9fa",
    "bg_live":       "#fff3cd",
}

# ─────────────────────────────────────────────────────────────────────────────
# Typography
# ─────────────────────────────────────────────────────────────────────────────

FONT_FAMILY = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
FONT_SIZE_XS = "0.65rem"
FONT_SIZE_SM = "0.75rem"
FONT_SIZE_MD = "0.85rem"
FONT_SIZE_BASE = "13px"

# ─────────────────────────────────────────────────────────────────────────────
# Spacing / shape
# ─────────────────────────────────────────────────────────────────────────────

RADIUS_SM  = "8px"
RADIUS_MD  = "12px"
RADIUS_LG  = "20px"

SHADOW_SM  = "0 1px 3px rgba(0,0,0,.08)"
SHADOW_MD  = "0 4px 12px rgba(0,0,0,.10)"
SHADOW_LG  = "0 8px 30px rgba(0,0,0,.12)"

# ─────────────────────────────────────────────────────────────────────────────
# Shared inline style dicts  (reusable across components)
# ─────────────────────────────────────────────────────────────────────────────

STYLE_CARD = {
    "borderRadius": RADIUS_MD,
    "boxShadow":    SHADOW_SM,
    "border":       "none",
    "backgroundColor": COLORS["bg_card"],
}

STYLE_HEADER_GRADIENT = {
    "background":    f"linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['primary_dark']} 100%)",
    "borderRadius":  RADIUS_LG,
    "marginTop":     "20px",
}

STYLE_LIVE_BADGE = {
    "backgroundColor": COLORS["live"],
    "color":           "white",
    "borderRadius":    RADIUS_SM,
    "padding":         "2px 8px",
    "fontSize":        FONT_SIZE_SM,
    "fontWeight":      "bold",
    "letterSpacing":   "0.5px",
}

STYLE_TOOLTIP_ICON = {
    "cursor":       "pointer",
    "fontSize":     FONT_SIZE_XS,
    "border":       f"1px solid {COLORS['muted']}",
    "borderRadius": "50%",
    "padding":      "1px 5px",
    "verticalAlign": "middle",
}

# ─────────────────────────────────────────────────────────────────────────────
# Chart constants
# ─────────────────────────────────────────────────────────────────────────────

CHART_COLORS: List[str] = [
    COLORS["accent"],
    COLORS["primary"],
    COLORS["success"],
    COLORS["warning"],
    COLORS["danger"],
    COLORS["info"],
]

CHART_LAYOUT = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family=FONT_FAMILY, size=12),
    margin=dict(l=45, r=25, t=30, b=45),
    hovermode="x unified",
    xaxis=dict(gridcolor="#f0f0f0"),
    yaxis=dict(gridcolor="#f0f0f0"),
)

# ─────────────────────────────────────────────────────────────────────────────
# Table / DataTable style tokens
# ─────────────────────────────────────────────────────────────────────────────

TABLE_STYLE_HEADER = {
    "backgroundColor": COLORS["accent"],
    "color":           "white",
    "fontWeight":      "bold",
    "textAlign":       "center",
    "padding":         "14px",
    "border":          "none",
}

TABLE_STYLE_DATA = {
    "backgroundColor": "white",
    "border":          "none",
    "borderBottom":    f"1px solid {COLORS['border_subtle']}",
}

TABLE_STYLE_CELL = {
    "textAlign":    "center",
    "padding":      "12px",
    "fontFamily":   FONT_FAMILY,
    "fontSize":     FONT_SIZE_BASE,
    "whiteSpace":   "pre-line",
    "height":       "auto",
}

# ─────────────────────────────────────────────────────────────────────────────
# Config field metadata
# ─────────────────────────────────────────────────────────────────────────────

ALL_MARKET_TYPES: List[str] = ["result", "over_under_2.5", "btts"]

# Fields that live in the YAML but are NOT part of BetSlipConfig
DASHBOARD_ONLY_KEYS = {"units", "run_daily_count"}

# BetSlipConfig fields that are always None in saved profiles (runtime-only)
RUNTIME_ONLY_FIELDS = {"date_from", "date_to", "excluded_urls"}

# Fields that are Optional[...] and can be toggled None ↔ manual via the UI
NULLABLE_CONFIG_FIELDS = {"max_legs_overflow", "tolerance_factor", "stop_threshold"}

# ─────────────────────────────────────────────────────────────────────────────
# Tooltip texts
# ─────────────────────────────────────────────────────────────────────────────

TOOLTIP_TEXTS: Dict[str, str] = {
    "target_odds": (
        "Desired cumulative odds for the entire slip. "
        "The algorithm stops building once it gets close enough to this number."
    ),
    "target_legs": (
        "Desired number of selections (legs) on the slip. Range: 1-10."
    ),
    "max_legs_overflow": (
        "How many extra legs beyond target_legs are allowed. "
        "Auto = 0 for singles, +1 for 2-4 legs, +2 for 5+ legs."
    ),
    "probability_floor": (
        "Minimum prediction confidence (%). Picks below this threshold are "
        "discarded before any scoring. E.g. 50 = only picks where 50 %+ of "
        "historical results agree with the prediction."
    ),
    "min_odds": (
        "Minimum bookmaker odds to consider. "
        "Filters out near-certain outcomes where the margin is unattractive. "
        "Range: 1.01-10.0."
    ),
    "included_market_types": (
        "Which bet markets to include. "
        "Results = 1/X/2, O/U 2.5 = goals over/under, BTTS = both teams score."
    ),
    "tolerance_factor": (
        "±% band around the ideal per-leg odds. A pick within this band is "
        "'Tier 1 balanced' and always ranked above out-of-band picks. "
        "Auto = wider for few legs, tighter for many. Range: 5 %-80 %."
    ),
    "stop_threshold": (
        "The builder stops when current_total_odds ≥ target_odds × threshold "
        "AND enough legs are filled. Auto is derived per target_legs. Range: 0.50-1.00."
    ),
    "min_legs_fill_ratio": (
        "Fraction of target_legs that must be filled before early-stop is allowed. "
        "E.g. 0.70 = need at least 70 % of legs before stopping early. Range: 0.50-1.00."
    ),
    "quality_vs_balance": (
        "Trade-off between pick quality and odds balance.\n"
        "0.0 = care only about matching the target odds per leg\n"
        "0.5 = equal weight (default)\n"
        "1.0 = care only about quality (best prob/sources wins)"
    ),
    "prob_vs_sources": (
        "Within the quality score, how much weight goes to probability vs data sources.\n"
        "0.0 = sources only\n"
        "0.5 = equal weight (default)\n"
        "1.0 = probability only"
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# Slip / leg status colours
# ─────────────────────────────────────────────────────────────────────────────

STATUS_STYLES = {
    "Won":  {"bg": COLORS["bg_won"],    "text": "success", "badge": "success"},
    "Lost": {"bg": COLORS["bg_lost"],   "text": "danger",  "badge": "danger"},
    "Live": {"bg": COLORS["bg_live"],   "text": "warning", "badge": "warning"},
}
STATUS_STYLES_DEFAULT = {"bg": COLORS["bg_pending"], "text": "dark", "badge": "secondary"}

LEG_ICON = {
    "Won":  "fa-check-circle text-success",
    "Lost": "fa-times-circle text-danger",
    "Live": "fa-circle-notch fa-spin text-warning",
}
LEG_ICON_DEFAULT = "fa-clock text-secondary"