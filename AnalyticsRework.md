# Analytics Tab — Phased Implementation Plan

---

# PHASE 1 — Value Visibility
*The stats bar and core charts need to answer "are you actually good?" before anything else.*

---

## 1.1 — Stats Bar Overhaul

The current stats bar shows: Total Bet · Gross Return · Net Profit · Win Rate · ROI · Settled.
This is a scoreboard, not an evaluation tool. The overhaul adds the market comparison layer.

---

### Card: Avg Odds

**What it is:** The average `total_odds` across all settled slips in the current filter selection.

**Why it matters:** Every single other metric is meaningless without this anchor. A 55% win rate on avg odds 1.5 is terrible. On avg odds 2.2 it's exceptional. This card is the denominator for everything.

**Data needed:**
- `slips.total_odds` where `status = settled`
- Filtered by selected profiles

**Display:**
- Primary value: `@2.14` format (or however odds are formatted in your system)
- No secondary indicator needed — it's context, not a performance metric

**Placement:** Insert it immediately after Gross Return, before Net Profit. It needs to sit adjacent to the performance metrics it contextualises.

---

### Card: Implied Win Rate

**What it is:** The average of `(1 / total_odds)` across settled slips, expressed as a percentage. This is what the bookmaker's odds say your slips *should* win statistically.

**Why it matters:** The market is pricing in its own margin. If your implied win rate is 48% and your actual win rate is 51.5%, you're genuinely beating the market. If implied is 55% and actual is 51.5%, you're losing value every single bet regardless of feeling like you're winning.

**Data needed:**
- `slips.total_odds` where `status = settled`
- Formula per slip: `1 / total_odds`
- Final value: `avg(1 / total_odds) * 100`

**Display:**
- Primary value: e.g. `48.20%`
- Subtle label: "Market implies" underneath
- Color: neutral grey — this is market data, not your performance

**Placement:** Immediately after Win Rate, so the two percentages sit side by side and the comparison is instant.

---

### Card: Edge

**What it is:** `Actual Win Rate − Implied Win Rate`. The single number that tells you if you're a profitable bettor or a lucky one.

**Why it matters:**
- Positive edge means you're identifying outcomes the market is undervaluing
- Negative edge means the market is smarter than your selections, and your profits are variance
- Trending edge over time (Phase 3) tells you if your skill is improving or decaying

**Data needed:** Derived from the two cards above — no new queries needed.

**Display:**
- Primary value: `+3.32%` or `-1.84%`
- Color: green if positive, red if negative — this is the one card that must be color-coded clearly
- Threshold indicator: a small icon or label distinguishing `Significant` (>2%) from `Marginal` (<2%) from `Negative`
- Tooltip: explain what edge means for users who don't know

**Placement:** Immediately after Implied Win Rate. The trio of Win Rate · Implied Win Rate · Edge should sit together as a visual unit.

---

### Card: Pending

**What it is:** Count of slips where `status = pending` (or whatever your non-settled status is), filtered by selected profiles.

**Why it matters:** Operational context. When you're evaluating your ROI and edge, you need to know how much of the picture is still unresolved. A 13% ROI with 40 pending slips is a very different situation than with 4.

**Data needed:**
- `slips` count where `status != settled`

**Display:**
- Primary value: count (e.g. `12`)
- Secondary: total units at risk from pending slips (`Σ units pending: 14.5 U`)
- Color: amber — it's not performance, it's exposure

**Placement:** Alongside or replacing the current Settled card. Consider a split card: `Settled: 33 | Pending: 12` in one tile.

---

### Card: Avg Units / Slip

**What it is:** `avg(units)` across settled slips for selected profiles.

**Why it matters:** Surfaces staking inconsistency. If your avg is 1.5U but your standard deviation is 1.2U, you're sizing wildly inconsistently — probably emotionally. This sets up the staking quality analysis in Phase 4.

**Data needed:**
- `slips.units` where `status = settled`

**Display:**
- Primary value: `1.50 U`
- Secondary: `σ 0.4 U` (standard deviation) — even this small addition immediately flags inconsistency
- No color coding needed

**Placement:** After Settled/Pending, at the end of the bar.

---

### Stats Bar Final Layout

```
Total Bet | Gross Return | Avg Odds | Net Profit | Win Rate | Implied Win Rate | Edge | ROI | Avg Units/Slip | Settled/Pending
```

If the bar gets too crowded, split into two rows: Row 1 = financial output, Row 2 = quality evaluation.

---

## 1.2 — Odds Bucket Chart Upgrade

**Current state:** A bar chart showing win rate per odds bucket (1.0–1.5, 1.5–2.0, 5.0–10.0). The 5.0–10.0 bucket is already showing red (losing), which is interesting but unexplained.

**The problem:** 80% win rate in the 1.0–1.5 bucket sounds good until you realise that at those odds, you need ~67%+ to break even. Without implied win rate context, the chart is decorative.

---

### Upgrade: Add Implied Win Rate as a Second Series

Transform the chart from a single-bar chart into a grouped bar chart (or bar + line overlay):

**Series 1 — Actual Win Rate (keep as is):** Green bars, current behavior.

**Series 2 — Implied Win Rate:** Calculated as `avg(1 / slip_odds)` for all slips in that bucket. Display as a red/amber horizontal line overlaid on each bucket, or as a second grouped bar in a contrasting color (e.g. blue).

**The visual story this tells:**
- Bucket 1.0–1.5: actual 80%, implied 75% → green zone, +5% edge
- Bucket 1.5–2.0: actual 62%, implied 58% → positive, solid
- Bucket 5.0–10.0: actual 20%, implied 16% → looks bad but might actually be positive edge

**Add a third element:** An edge value label on each bucket. Small text above each group: `+5.2%` or `-3.1%`. This makes the insight instant without needing to eyeball bar heights.

---

### Upgrade: Bucket Granularity

Your current buckets are very coarse (only 3 visible). Add more:
- 1.0–1.3
- 1.3–1.6
- 1.6–2.0
- 2.0–2.5
- 2.5–3.5
- 3.5–5.0
- 5.0+

This only makes sense once you have more data volume, so treat it as a conditional: if fewer than 5 slips in a bucket, merge it with the adjacent one and display a `low sample` indicator.

---

### Upgrade: Volume Indicator

Add a small number above each bucket showing slip count. Right now you can't tell if the 5.0–10.0 bucket is 2 slips or 20. Small label, e.g. `n=4`, greyed out. Essential for statistical credibility signaling.

---

## 1.3 — Replace ROI Over Time with Rolling Edge Chart

**Current state:** ROI % over time as a line chart. The shape closely mirrors the Cumulative Net Profit chart, making it redundant. Both show "things got good then leveled off."

**Replacement: Rolling Edge (14-day window)**

**What it shows:** On any given date, the edge = `rolling_win_rate − rolling_implied_win_rate` over the past 14 days.

**Why this is more valuable than ROI over time:**
- ROI over time is dominated by a few large wins/losses
- Rolling edge smooths that out and shows whether your *selections* are consistently beating the market
- A rising profit line with a falling edge line is the most important warning sign you can have — it means variance is working for you but your picks are getting worse
- A falling profit line with a stable positive edge means you're running bad but your process is sound — keep going

**Display:**
- Same line chart format
- Zero line clearly marked (dotted horizontal line at y=0)
- Color fill: green above zero, red below zero (area fill, not just line color)
- Add a second light line: `rolling_win_rate` at reduced opacity, so you can see what's driving edge changes
- Window selector: allow toggling between 7-day, 14-day, 30-day rolling windows

**Data construction:**
For each date with at least one settled slip, look back N days, take all settled slips in that window, calculate `(wins/total) − avg(1/odds)`.

---

## 1.4 — Replace Win Rate Cumulative with Drawdown Chart

**Current state:** A cumulative win rate line that sits around 50% and barely moves. It's visually flat and tells you nothing actionable.

**Replacement: Bankroll Drawdown Chart**

**What it shows:**
- Track the running peak of cumulative net profit
- At each point in time, plot the distance from that peak: `current_profit − peak_profit_to_date`
- The result is a chart that always touches 0 at new highs, and dips below 0 during losing runs

**Why it matters:**
- It answers "what is the worst I've experienced and how long did it last?"
- This is the primary risk metric for evaluating a strategy's psychological and financial viability
- A strategy with +13% ROI but a -8U max drawdown needs a much larger bankroll to survive than one with a -2U max drawdown

**Display:**
- Area chart, filled red below zero (which is always)
- Add annotated markers at: max drawdown point, longest drawdown duration
- Add a horizontal reference line at your current drawdown level (are you currently in a drawdown?)
- Secondary stat below the chart: `Max Drawdown: -3.2U over 8 days | Current: -0.4U`

---

# PHASE 2 — Market Intelligence
*Understanding which markets you're good at, and which are silently bleeding you.*

---

## 2.1 — Market Breakdown Table

**Current state:** Two charts — a horizontal bar chart of win rates per market, and a stacked bar of won vs lost per market. Both show activity volume and raw win rate. Neither shows value.

**The problem:** These charts would look identical for a profitable bettor and a losing one with the same win rate but different odds. They're structured analysis but missing the critical dimension.

---

### Replace Both Charts with a Multi-Metric Market Table

This is a sortable, filterable table (not a chart) with one row per market type found in your `legs.market` column.

**Columns:**

| Column | Calculation | Notes |
|---|---|---|
| Market | `legs.market` | Group label |
| Legs | count of legs for this market | Volume indicator |
| Win Rate | `wins / settled_legs` | Existing metric |
| Implied Win Rate | `avg(1 / leg_odds)` | New — requires per-leg odds |
| Edge | Win Rate − Implied | New — color coded green/red |
| Avg Odds | `avg(legs.odds)` | New |
| Legs in Winning Slips | count of legs from slips where slip won | Shows market's contribution to overall success |
| P&L Attribution | estimated net from legs in this market | Requires assumption (equal attribution per leg in a multi-leg slip) |

**Sorting:** Default sort by Edge descending — your best markets float to the top immediately.

**Color coding:** Edge column only. Green gradient for positive, red for negative. Rest of the table stays neutral to avoid visual noise.

**Important note on P&L Attribution:** Multi-leg slips make exact P&L per market impossible without assumption. Use this approach: if a slip has 3 legs and wins, attribute `net_profit / 3` to each leg's market. If it loses, attribute `-units / 3` to each. This is an approximation but it's informative directionally.

---

### Keep a Visual Summary Alongside the Table

Directly above or below the table, keep one compact chart:

**Edge per Market — Horizontal Bar Chart**
- One bar per market
- Bar length = edge value (centered on zero axis)
- Color: green right of zero, red left of zero
- This gives instant visual ranking while the table gives the detail

---

## 2.2 — Leg-Level Market × Market Type Cross-Tab

**What it is:** A matrix heatmap where:
- Rows = `legs.market` values (1, BTTS Yes, Over 2.5, etc.)
- Columns = `legs.market_type` values
- Cells = win rate or edge for legs matching that combination

**Why it matters:** Your market-level analysis might show "Over 2.5 has 55% win rate." But the cross-tab might reveal "Over 2.5 in market_type A has 70% win rate, while Over 2.5 in market_type B has 35%." You're losing the signal by aggregating. This is where per-leg granularity pays off.

**Display:**
- Heatmap: green = high win rate / positive edge, red = low / negative
- Cell value: show `win_rate%` inside each cell if space allows, or on hover
- Grayed out cells with `n<3` indicator where sample is too small
- Toggle: switch between showing win rate and showing edge (requires avg odds per cell)

**Interaction:**
- Clicking a cell filters the main market table to show only slips matching that market × market_type combination
- This lets you drill into the exact slips driving a good or bad cell

---

## 2.3 — Legs vs Win Rate — Full Rebuild

**Current state:** A bar chart with two data points (1 leg and 4 legs). This is almost useless at current granularity.

**Rebuild into a 3-series grouped bar chart:**

**Series 1 — Actual Win Rate:** Same as current, one bar per leg count bucket.

**Series 2 — Implied Win Rate:** `avg(1 / total_odds)` per leg count bucket. Critical — because a 4-leg accumulator will have much lower implied win rate than a single, so you need to compare apples to apples.

**Series 3 — Avg Total Odds:** Secondary axis (right side), line chart. This shows the natural relationship: more legs = longer odds, and makes the viewer understand why win rate drops with more legs.

**Buckets:** 1 leg, 2 legs, 3 legs, 4 legs, 5+ legs.

**Small table underneath:** Slip count per bucket so you can see statistical weight.

**The key question this answers:** "Is my edge consistent across single bets and accumulators, or am I better at one than the other?"

---

## 2.4 — Profile Bubble Chart — Break-Even Line Addition

**Current state:** Profiles plotted as bubbles with avg odds on X, win rate on Y, bubble size = volume. Useful but missing the break-even reference.

**The single most important upgrade:** Add the break-even curve.

The break-even win rate at any given avg odds is `1 / avg_odds`. This plots as a hyperbolic curve across the chart. Any profile bubble sitting above this curve is profitable. Any bubble below it is losing money despite whatever win rate it shows.

**Additional upgrades:**

- Color the bubble interior: green if above break-even curve, red if below
- Add a label on each bubble: show the edge value (`+2.1%`, `-0.8%`)
- Add a third dimension option: toggle bubble size between volume (slips) and total units staked
- If multiple profiles cluster together, consider whether combining them for analysis makes sense — surface this as a suggestion tooltip

---

# PHASE 3 — Risk & Variance Layer
*Knowing how much of your performance is real vs lucky, and how stable your edge is.*

---

## 3.1 — Return Distribution Histogram

**What it is:** A frequency histogram where:
- X axis = per-slip net profit/loss in units (bucketed: e.g. -5U to -4U, -4U to -3U, ... +3U to +4U, etc.)
- Y axis = number of slips in each bucket
- Two colors: red bars for losing slips, green bars for winning slips

**Why it matters:**
- A normally distributed result suggests your edge, if any, comes from consistent selections
- A right-skewed distribution (most slips small losses, rare large wins) means you're dependent on a few big accumulators — your strategy has high variance and requires a much larger bankroll
- A left-skewed distribution (most slips small wins, rare large losses) is ideal — consistent grinding with occasional bad runs

**Additional overlays:**
- Vertical line at x=0 (break-even)
- Vertical line at your average slip P&L
- A fitted normal distribution curve in light gray — visual comparison to theoretical randomness
- Small stats below: `Mean: +0.19U | Median: -0.25U | Skew: +1.2 | Kurtosis: 3.4`

**The median vs mean gap is very telling:** If mean is higher than median, a few big wins are flattering your numbers.

---

## 3.2 — Daily Volume & P&L Dual-Axis Chart

**What it is:** A combined chart showing:
- Bar chart (left axis): units staked per day
- Line overlay (right axis): net P&L for that day
- Color the bars: green on days with positive P&L, red on negative days

**Why it matters:**
- Reveals overtrading — days with very high staking volume that coincide with poor results
- Shows betting frequency patterns — are you betting every day or concentrated on certain days?
- If high-volume days consistently underperform, that's a signal you're forcing bets rather than waiting for value

**Additional metric to derive:** A scatter in the tooltip — show "on your 5 highest staking days, average P&L was X." If X is negative, overtrading is hurting you.

**Interaction:** Click a bar to filter the main slips table to that day's slips.

---

## 3.3 — Time Pattern Heatmaps

Two heatmaps using `legs.match_datetime`:

### Heatmap A: Day of Week × Market Type
- Rows: Monday through Sunday
- Columns: each `market_type`
- Cells: win rate or edge
- This answers: "Am I systematically worse on Sundays?" or "Does my edge only exist on midweek games?"

### Heatmap B: Hour of Kickoff × Market
- Rows: time buckets (12:00–14:00, 14:00–16:00, 16:00–18:00, 18:00–20:00, 20:00+)
- Columns: each `market`
- Cells: win rate + n count
- This answers: "Is my BTTS edge specific to evening games?" — a very common pattern

**Display for both:**
- Consistent color scale across both heatmaps (same green–red range)
- Minimum n threshold: gray out cells with fewer than 3 legs
- Hover tooltip: show win rate, implied win rate, edge, and leg count for each cell
- These charts should be placed in a new dedicated section: "Time & Pattern Analysis"

---

## 3.4 — Sharpe Ratio Card (Stats Bar Addition)

**What it is:** `avg_daily_pnl / std_dev_daily_pnl × sqrt(252)` (using 252 betting days convention).

**Why it matters:** Two strategies with identical ROI can have completely different risk profiles. A Sharpe of 2.0+ means consistent returns. A Sharpe of 0.4 means your ROI is riding on a few volatile days.

**Display:**
- Add as a card in the stats bar (Phase 1's final slot or a second row)
- Benchmarks in tooltip: `< 0.5 = volatile`, `0.5–1.5 = acceptable`, `> 1.5 = consistent`
- Only display if ≥ 14 days of data exist, otherwise show `—` with a tooltip explaining why

---

# PHASE 4 — Strategic Tools
*Turning your historical data into forward-looking decision frameworks.*

---

## 4.1 — Kelly Criterion Comparison

**What it is:** For each profile, calculate the Kelly-optimal stake fraction and compare it to your actual average stake.

**Formula:**
`Kelly % = (b × p − q) / b`
Where:
- `b` = avg odds − 1 (net odds)
- `p` = your historical win rate for that profile
- `q` = 1 − p

Then convert Kelly % to units based on your defined bankroll.

**Display:**
- A grouped bar chart: one group per profile
- Bar 1: Kelly-recommended units
- Bar 2: Your actual avg units
- Color the gap: green if you're under Kelly (conservative, safe), red if over Kelly (aggressive, risky of ruin)
- Add a "Half Kelly" reference line — many professional bettors use half Kelly as the practical optimum

**Caveat to display in a tooltip:** Kelly assumes your historical win rate is your true win rate. With small samples, Kelly will overestimate. Show a `confidence-adjusted Kelly` using a credibility interval if sample size is under 50 slips per profile.

---

## 4.2 — Units Consistency Scatter

**What it is:** A scatter plot where:
- X axis: slip number (chronological order, 1 to N)
- Y axis: units staked on that slip
- Color: green dot if slip won, red dot if slip lost

**Why it matters:** You can immediately see if you're unconsciously increasing stakes after wins (overconfidence) or after losses (chasing). Both are detrimental. A flat band of dots at consistent units is what a disciplined bettor looks like.

**Overlay:**
- A rolling average line (e.g. 10-slip rolling avg of units) to smooth the noise and show the trend
- Horizontal reference line at your avg units
- Optional: highlight clusters of red dots followed by increased units (chasing pattern detection)

**Interaction:** Clicking a dot shows the slip details in a side panel or tooltip.

---

## 4.3 — Slip Quality Score Tracker

**What it is:** An assigned score per settled slip that measures selection quality independent of outcome.

**Score components:**
1. `Market Edge Score`: for each leg, `historical_win_rate_for_that_market − (1 / leg_odds)`. Average across legs.
2. `Odds Value Score`: `total_odds / implied_total_odds` (where implied total odds = product of `1/p` for each leg's market). Above 1.0 means you got better odds than your historical markets imply.
3. `Combined Quality Score`: weighted average of the two (50/50 or configurable).

**Display:**
- A line chart of rolling average Quality Score over time (same format as rolling edge)
- A scatter of Quality Score (X) vs actual outcome (Y: +net units or -net units) per slip — this should show positive correlation if your scoring is working
- Over time, you want to see if slips with high quality scores win more often than slips with low scores. If they do, the score is valid and you should only take high-score slips.

**Important note:** This score will be noisy early. It requires at minimum 30–50 settled legs per market to have meaningful historical win rates. Display a `Low Data` warning per market until this threshold is reached.

---

## 4.4 — Expected Value Dashboard Summary

A small dedicated panel (not a full section) that synthesizes Phases 1–4 into an at-a-glance strategic view:

| Signal | Value | Status |
|---|---|---|
| Overall Edge | +3.32% | ✅ Positive |
| Rolling Edge (14d) | +1.1% | ⚠️ Declining |
| Sharpe Ratio | 0.82 | ✅ Acceptable |
| Kelly Alignment | -0.3U vs recommended | ✅ Conservative |
| Max Drawdown | -3.2U | ✅ Within range |
| Best Market | Over 2.5 (+6.1% edge) | — |
| Worst Market | BTTS No (-2.3% edge) | ⚠️ Avoid |

This panel should sit at the very top of the Analytics tab, above the profile selector, as a strategic health check. Color each row's status indicator. This is the "executive summary" that tells you in 5 seconds whether your strategy is healthy.

---

## Implementation Dependency Map

```
Phase 1 (Cards + Chart upgrades)
    └── requires: slips.total_odds, slips.units, slips.status

Phase 2 (Market Intelligence)
    └── requires: legs.odds, legs.market, legs.market_type, legs.status
    └── depends on: Phase 1 (implied win rate concept established)

Phase 3 (Risk & Variance)
    └── requires: daily P&L aggregation, legs.match_datetime
    └── depends on: Phase 1 edge concept, Phase 2 market attribution

Phase 4 (Strategic Tools)
    └── requires: all of the above
    └── depends on: sufficient data volume (≥50 settled slips per profile recommended)
```

The legs table is the unlock for Phases 2, 3, and 4. Everything from Phase 2 onwards requires per-leg odds — confirm that `legs.odds` is being stored accurately per leg before building anything in those phases.