import { useEffect, useState, useCallback, useMemo } from 'react';
import {
    ResponsiveContainer, Line, BarChart, Bar, AreaChart, Area,
    XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, ComposedChart, Cell,
} from 'recharts';
import { fetchAnalytics } from '../api/data';
import { SectionHeader, TooltipIcon } from '../components/ui';
import { ProfileSelector } from '../components/ui/ProfileSelector';
import type { GlobalFilters } from '../components/Layout';
import type { AnalyticsData, MarketBreakdown, SlipStats } from '../types';
import { useProfileSelection } from '../hooks/useProfileSelection';

// ── Shared tooltip style ───────────────────────────────────────────────────────

const TT: React.CSSProperties = {
    background: 'var(--bg-card)',
    border: '1px solid var(--border-strong)',
    borderRadius: 8,
    fontSize: 11,
    fontFamily: 'JetBrains Mono, monospace',
    color: 'var(--text-secondary)',
    padding: '10px 14px',
};

// ── Chart wrapper ──────────────────────────────────────────────────────────────

function ChartCard({ title, tip, children, className = '' }: {
    title: string; tip?: string; children: React.ReactNode; className?: string;
}) {
    return (
        <div className={`card p-4 ${className}`}>
            <div className="flex items-center gap-2 mb-4">
                <p className="font-mono text-[11px] tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>{title}</p>
                {tip && <TooltipIcon text={tip} align="right" />}
            </div>
            {children}
        </div>
    );
}

// ── Hero KPI Card ──────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, color, tip }: {
    label: string; value: string | number; sub?: string;
    color?: string; tip?: string;
}) {
    return (
        <div className="card px-5 py-4 flex flex-col gap-1"
            style={{ borderTop: `2px solid ${color ?? 'var(--border-strong)'}` }}>
            <div className="flex items-center gap-1 mb-1">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>{label}</span>
                {tip && <TooltipIcon text={tip} align="center" />}
            </div>
            <span className="font-display font-bold text-3xl leading-none"
                style={{ color: color ?? 'var(--text-bright)' }}>{value}</span>
            {sub && (
                <span className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>{sub}</span>
            )}
        </div>
    );
}

// ── Stat Tile ──────────────────────────────────────────────────────────────────

function StatTile({ label, value, sub, color, tip, highlight = false }: {
    label: string; value: string | number; sub?: string;
    color?: string; tip?: string; highlight?: boolean;
}) {
    return (
        <div className="card px-4 py-3 flex flex-col gap-1"
            style={highlight ? { border: '1px solid var(--border-accent)', background: 'var(--bg-hover)' } : {}}>
            <div className="flex items-center gap-1">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>{label}</span>
                {tip && <TooltipIcon text={tip} align="center" />}
            </div>
            <span className="font-display font-bold text-xl leading-none"
                style={{ color: color ?? 'var(--text-bright)' }}>{value}</span>
            {sub && <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>{sub}</span>}
        </div>
    );
}

// ── Financials Row ─────────────────────────────────────────────────────────────
// Requires these optional fields added to SlipStats on the backend:
//   biggest_win_units: float      — highest single-slip net win
//   biggest_loss_units: float     — worst single-slip net loss (negative)
//   current_streak: int           — positive = win streak, negative = loss streak
//   longest_win_streak: int       — all-time best consecutive wins
//   longest_loss_streak: int      — all-time worst consecutive losses
//   profit_factor: float          — gross_wins / abs(gross_losses); >1 = profitable
//   current_bankroll: float       — optional: starting_bankroll + net_profit

function FinancialTile({ label, value, sub, color, tip, badge }: {
    label: string;
    value: string | number;
    sub?: string;
    color?: string;
    tip?: string;
    badge?: { text: string; color: string };
}) {
    return (
        <div className="card px-4 py-3 flex flex-col gap-1">
            <div className="flex items-center gap-1">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>{label}</span>
                {tip && <TooltipIcon text={tip} align="center" />}
            </div>
            <div className="flex items-baseline gap-2">
                <span className="font-display font-bold text-xl leading-none"
                    style={{ color: color ?? 'var(--text-bright)' }}>{value}</span>
                {badge && (
                    <span className="text-[9px] font-mono tracking-wide uppercase px-1.5 py-0.5 rounded"
                        style={{ color: badge.color, background: `color-mix(in srgb, ${badge.color} 15%, transparent)` }}>
                        {badge.text}
                    </span>
                )}
            </div>
            {sub && <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>{sub}</span>}
        </div>
    );
}

function FinancialsRow({ stats }: { stats: SlipStats }) {
    const biggestWin: number | null = stats.biggest_win_units ?? null;
    const biggestLoss: number | null = stats.biggest_loss_units ?? null;
    const bestDayPnl: number | null = stats.best_day_pnl ?? null;
    const worstDayPnl: number | null = stats.worst_day_pnl ?? null;
    const currentStreak: number | null = stats.current_streak ?? null;
    const longestWin: number | null = stats.longest_win_streak ?? null;
    const longestLoss: number | null = stats.longest_loss_streak ?? null;
    const profitFactor: number | null = stats.profit_factor ?? null;
    const currentBankroll: number | null = stats.gross_return ?? null;

    // Streak display helpers
    const streakDir = currentStreak === null ? null : currentStreak > 0 ? 'win' : currentStreak < 0 ? 'loss' : null;
    const streakAbs = currentStreak !== null ? Math.abs(currentStreak) : null;
    const streakColor = streakDir === 'win' ? 'var(--win)' : streakDir === 'loss' ? 'var(--loss)' : 'var(--text-secondary)';
    const streakLabel = streakDir === 'win' ? 'W' : streakDir === 'loss' ? 'L' : '';

    // Profit factor rating
    const pfColor = profitFactor === null ? 'var(--text-secondary)'
        : profitFactor >= 2 ? 'var(--win)'
        : profitFactor >= 1.2 ? 'var(--pending)'
        : profitFactor >= 1 ? 'var(--text-bright)'
        : 'var(--loss)';
    const pfGrade = profitFactor === null ? null
        : profitFactor >= 2 ? 'Strong' : profitFactor >= 1.2 ? 'Good' : profitFactor >= 1 ? 'Breakeven' : 'Negative';

    return (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">

            {/* Current Bankroll */}
            <FinancialTile
                label="Bankroll"
                value={currentBankroll !== null ? `${currentBankroll.toFixed(1)}U` : '—'}
                sub={currentBankroll !== null ? `${stats.net_profit >= 0 ? '+' : ''}${stats.net_profit}U all-time` : 'add starting_bankroll'}
                color={currentBankroll !== null
                    ? (currentBankroll >= 0 ? 'var(--win)' : 'var(--loss)')
                    : 'var(--text-secondary)'}
                tip="Current bankroll = starting bankroll + net profit."
            />

            {/* Biggest Win */}
            <div className="card px-4 py-3 flex flex-col gap-1">
                <div className="flex items-center gap-1 mb-1">
                    <span className="text-[10px] font-mono tracking-widest uppercase"
                        style={{ color: 'var(--text-secondary)' }}>Biggest Win</span>
                    <TooltipIcon text="Largest single-slip net profit. Best day shows highest daily P&L." align="center" />
                </div>
                <div className="flex justify-between items-end gap-4">
                    <div className="flex flex-col items-start gap-0.5">
                        <span className="text-[9px] font-mono" style={{ color: 'var(--text-secondary)' }}>slip</span>
                        <span className="font-display font-bold text-xl leading-none"
                            style={{ color: biggestWin !== null ? 'var(--win)' : 'var(--text-secondary)' }}>
                            {biggestWin !== null ? `+${biggestWin.toFixed(2)}U` : '—'}
                        </span>
                    </div>
                    <div className="flex flex-col items-end gap-0.5">
                        <span className="text-[9px] font-mono" style={{ color: 'var(--text-secondary)' }}>best day</span>
                        <span className="font-display font-bold text-xl leading-none"
                            style={{ color: bestDayPnl !== null ? 'var(--win)' : 'var(--text-secondary)' }}>
                            {bestDayPnl !== null ? `+${bestDayPnl.toFixed(2)}U` : '—'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Biggest Loss */}
            <div className="card px-4 py-3 flex flex-col gap-1">
                <div className="flex items-center gap-1 mb-1">
                    <span className="text-[10px] font-mono tracking-widest uppercase"
                        style={{ color: 'var(--text-secondary)' }}>Biggest Loss</span>
                    <TooltipIcon text="Largest single-slip net loss. Worst day shows lowest daily P&L." align="center" />
                </div>
                <div className="flex justify-between items-end gap-4">
                    <div className="flex flex-col items-start gap-0.5">
                        <span className="text-[9px] font-mono" style={{ color: 'var(--text-secondary)' }}>slip</span>
                        <span className="font-display font-bold text-xl leading-none"
                            style={{ color: biggestLoss !== null ? 'var(--loss)' : 'var(--text-secondary)' }}>
                            {biggestLoss !== null ? `${biggestLoss.toFixed(2)}U` : '—'}
                        </span>
                    </div>
                    <div className="flex flex-col items-end gap-0.5">
                        <span className="text-[9px] font-mono" style={{ color: 'var(--text-secondary)' }}>worst day</span>
                        <span className="font-display font-bold text-xl leading-none"
                            style={{ color: worstDayPnl !== null ? 'var(--loss)' : 'var(--text-secondary)' }}>
                            {worstDayPnl !== null ? `${worstDayPnl.toFixed(2)}U` : '—'}
                        </span>
                    </div>
                </div>
            </div>

            {/* Profit Factor */}
            <FinancialTile
                label="Profit Factor"
                value={profitFactor !== null ? profitFactor.toFixed(2) : '—'}
                sub={pfGrade ?? undefined}
                color={pfColor}
                tip="Gross wins ÷ gross losses. Above 1.0 = overall profitable. Above 2.0 = strong edge."
            />

            {/* Current Day Streak */}
            <FinancialTile
                label="Day Streak"
                value={streakAbs !== null ? streakAbs : '—'}
                badge={streakDir ? { text: streakLabel, color: streakColor } : undefined}
                color={streakColor}
                sub={streakDir === 'win' ? 'consecutive winning days' : streakDir === 'loss' ? 'consecutive losing days' : undefined}
                tip="Current unbroken sequence of winning/losing days based on daily P&L."
            />

            {/* Day Streak Records */}
            <div className="card px-4 py-3 flex flex-col gap-1">
                <div className="flex items-center gap-1 mb-1">
                    <span className="text-[10px] font-mono tracking-widest uppercase"
                        style={{ color: 'var(--text-secondary)' }}>Day Streak Records</span>
                    <TooltipIcon text="All-time longest sequences of consecutive winning/losing days based on daily P&L." align="center" />
                </div>
                <div className="flex items-center justify-between">
                    <div className="flex flex-col gap-0.5">
                        <span className="text-[9px] font-mono" style={{ color: 'var(--win)' }}>Longest Win</span>
                        <span className="font-display font-bold text-lg leading-none"
                            style={{ color: 'var(--win)' }}>
                            {longestWin !== null ? longestWin : '—'}
                        </span>
                    </div>
                    <div className="h-8 w-px" style={{ background: 'var(--border)' }} />
                    <div className="flex flex-col gap-0.5 items-end">
                        <span className="text-[9px] font-mono" style={{ color: 'var(--loss)' }}>Longest Loss</span>
                        <span className="font-display font-bold text-lg leading-none"
                            style={{ color: 'var(--loss)' }}>
                            {longestLoss !== null ? longestLoss : '—'}
                        </span>
                    </div>
                </div>
            </div>

        </div>
    );
}

// ── Edge Trend Card ────────────────────────────────────────────────────────────

function EdgeTrendCard({ stats }: { stats: SlipStats }) {
    const trendColor = stats.edge_trend === 'growing' ? 'var(--win)'
        : stats.edge_trend === 'declining' ? 'var(--loss)'
        : 'var(--text-secondary)';
    const trendIcon = stats.edge_trend === 'growing' ? '↑'
        : stats.edge_trend === 'declining' ? '↓' : '→';
    const trendLabel = stats.edge_trend
        ? stats.edge_trend.charAt(0).toUpperCase() + stats.edge_trend.slice(1)
        : 'Neutral';

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>Edge Trend</span>
                <TooltipIcon text="Trend of your edge over the last 14 days. Growing = improving, declining = worsening." align="right" />
            </div>
            <p className="font-display font-bold text-2xl leading-none mb-2" style={{ color: trendColor }}>
                {trendIcon} {trendLabel}
            </p>
            <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Recent</span>
                <span className="text-[12px] font-mono font-bold"
                    style={{ color: stats.recent_edge_value > 0 ? 'var(--win)' : stats.recent_edge_value < 0 ? 'var(--loss)' : 'var(--text-secondary)' }}>
                    {stats.recent_edge_value > 0 ? '+' : ''}{stats.recent_edge_value.toFixed(2)}%
                </span>
            </div>
        </div>
    );
}

// ── Target Stake Card ──────────────────────────────────────────────────────────

function TargetStakeCard({ stats }: { stats: SlipStats }) {
    const kellyRatio = stats.avg_units && stats.avg_units > 0
        ? (stats.kelly_suggested_units / stats.avg_units).toFixed(1) : '0.0';
    const isAggressive = parseFloat(kellyRatio) > 1.5;

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>Target Stake</span>
                <TooltipIcon text="Suggested stake size based on Kelly Criterion and current performance." align="right" />
            </div>
            <p className="font-display font-bold text-2xl leading-none mb-2"
                style={{ color: 'var(--text-bright)' }}>
                {stats.kelly_suggested_units !== undefined ? `${stats.kelly_suggested_units.toFixed(2)}U` : '0.00U'}
            </p>
            <span className="text-[10px] font-mono"
                style={{ color: isAggressive ? 'var(--pending)' : 'var(--text-secondary)' }}>
                {kellyRatio}× avg units{isAggressive ? ' — aggressive' : ''}
            </span>
        </div>
    );
}

// ── Sharpe Ratio Card ──────────────────────────────────────────────────────────

function SharpeCard({ stats }: { stats: SlipStats }) {
    const sharpe = stats.sharpe_ratio;
    const color = sharpe == null ? 'var(--text-secondary)'
        : sharpe > 1.5 ? 'var(--win)'
        : sharpe > 0.5 ? 'var(--pending)'
        : 'var(--loss)';
    const grade = sharpe == null ? '—'
        : sharpe > 2 ? 'Excellent'
        : sharpe > 1.5 ? 'Good'
        : sharpe > 0.5 ? 'Fair'
        : 'Poor';

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>Sharpe Ratio</span>
                <TooltipIcon text="Risk-adjusted return. &gt;1.5 = good, &gt;0.5 = fair, &lt;0.5 = poor." align="right" />
            </div>
            <p className="font-display font-bold text-2xl leading-none mb-1" style={{ color }}>
                {sharpe != null ? sharpe.toFixed(2) : '—'}
            </p>
            <span className="text-[10px] font-mono" style={{ color }}>{grade}</span>
        </div>
    );
}

// ── Max Drawdown Card ──────────────────────────────────────────────────────────

function MaxDrawdownCard({ drawdown }: { drawdown: { drawdown: number }[] }) {
    const maxDD = drawdown.length ? Math.min(...drawdown.map(d => d.drawdown)) : 0;
    const cur = drawdown.length ? drawdown[drawdown.length - 1].drawdown : 0;
    const ddColor = maxDD > -3 ? 'var(--win)' : maxDD > -8 ? 'var(--pending)' : 'var(--loss)';

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>Max Drawdown</span>
                <TooltipIcon text="Worst peak-to-trough loss. Closer to 0 = better capital protection." align="right" />
            </div>
            <p className="font-display font-bold text-2xl leading-none mb-1" style={{ color: ddColor }}>
                {maxDD.toFixed(1)}U
            </p>
            <span className="text-[10px] font-mono"
                style={{ color: cur < 0 ? 'var(--loss)' : 'var(--text-secondary)' }}>
                Current: {cur.toFixed(2)}U
            </span>
        </div>
    );
}

// ── Market Signals Card ────────────────────────────────────────────────────────

function MarketSignalsCard({ marketBreakdown }: { marketBreakdown: MarketBreakdown[] }) {
    const sorted = [...marketBreakdown].sort((a, b) => b.edge - a.edge);
    const best = sorted[0];
    const worst = sorted[sorted.length - 1];

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-4">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>Market Signals</span>
                <TooltipIcon text="Best and worst performing markets based on edge value." align="right" />
            </div>
            <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg p-3 flex flex-col gap-1" style={{ background: 'var(--win-bg)' }}>
                    <span className="text-[9px] font-mono tracking-widest uppercase font-bold"
                        style={{ color: 'var(--win)' }}>↑ Best Market</span>
                    <span className="font-display font-bold text-lg leading-none"
                        style={{ color: 'var(--text-bright)' }}>
                        {best ? best.market : '—'}
                    </span>
                    {best && (
                        <span className="text-[11px] font-mono font-bold" style={{ color: 'var(--win)' }}>
                            +{best.edge.toFixed(1)}% edge
                        </span>
                    )}
                </div>
                <div className="rounded-lg p-3 flex flex-col gap-1" style={{ background: 'var(--loss-bg)' }}>
                    <span className="text-[9px] font-mono tracking-widest uppercase font-bold"
                        style={{ color: 'var(--loss)' }}>↓ Avoid</span>
                    <span className="font-display font-bold text-lg leading-none"
                        style={{ color: 'var(--text-bright)' }}>
                        {worst && worst.edge < 0 ? worst.market : '—'}
                    </span>
                    {worst && worst.edge < 0 && (
                        <span className="text-[11px] font-mono font-bold" style={{ color: 'var(--loss)' }}>
                            {worst.edge.toFixed(1)}% edge
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}

// ── Market Efficiency Card (with visual bar) ───────────────────────────────────

function MarketEfficiencyCard({ stats }: { stats: SlipStats }) {
    const diff = stats.win_rate - stats.implied_win_rate;
    const diffColor = diff > 0 ? 'var(--win)' : diff < 0 ? 'var(--loss)' : 'var(--text-secondary)';

    return (
        <div className="card p-4">
            <div className="flex items-center gap-2 mb-4">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>Market Efficiency</span>
                <TooltipIcon text="Actual win rate vs market-implied win rate. The gap between them is your edge." align="right" />
            </div>

            <div className="flex justify-between items-end mb-5">
                <div>
                    <p className="text-[9px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Actual Win Rate</p>
                    <p className="font-display font-bold text-2xl leading-none"
                        style={{ color: diff >= 0 ? 'var(--win)' : 'var(--loss)' }}>
                        {stats.win_rate.toFixed(1)}%
                    </p>
                </div>
                <div className="text-center">
                    <p className="text-[9px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Your Edge</p>
                    <p className="font-display font-bold text-xl leading-none" style={{ color: diffColor }}>
                        {diff > 0 ? '+' : ''}{diff.toFixed(1)}%
                    </p>
                </div>
                <div className="text-right">
                    <p className="text-[9px] font-mono uppercase mb-1" style={{ color: 'var(--text-secondary)' }}>Implied</p>
                    <p className="font-display font-bold text-2xl leading-none" style={{ color: 'var(--text-secondary)' }}>
                        {stats.implied_win_rate.toFixed(1)}%
                    </p>
                </div>
            </div>

            <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono w-12 shrink-0" style={{ color: 'var(--win)' }}>Actual</span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-raised)' }}>
                        <div className="h-2 rounded-full" style={{
                            width: `${Math.min(100, stats.win_rate)}%`,
                            background: 'var(--win)', opacity: 0.75,
                        }} />
                    </div>
                    <span className="text-[9px] font-mono w-9 text-right shrink-0" style={{ color: 'var(--win)' }}>
                        {stats.win_rate.toFixed(1)}%
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono w-12 shrink-0" style={{ color: 'var(--text-secondary)' }}>Implied</span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-raised)' }}>
                        <div className="h-2 rounded-full" style={{
                            width: `${Math.min(100, stats.implied_win_rate)}%`,
                            background: 'var(--text-secondary)', opacity: 0.4,
                        }} />
                    </div>
                    <span className="text-[9px] font-mono w-9 text-right shrink-0" style={{ color: 'var(--text-secondary)' }}>
                        {stats.implied_win_rate.toFixed(1)}%
                    </span>
                </div>
            </div>
        </div>
    );
}

// ── Market breakdown table ─────────────────────────────────────────────────────

function MarketTable({ data }: { data: MarketBreakdown[] }) {
    const [sortKey, setSortKey] = useState<keyof MarketBreakdown>('edge');
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

    const sorted = useMemo(() => {
        return [...data].sort((a, b) => {
            const va = a[sortKey] as number;
            const vb = b[sortKey] as number;
            return sortDir === 'desc' ? vb - va : va - vb;
        });
    }, [data, sortKey, sortDir]);

    const handleSort = (k: keyof MarketBreakdown) => {
        if (k === sortKey) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
        else { setSortKey(k); setSortDir('desc'); }
    };

    const cols: { key: keyof MarketBreakdown; label: string; tip: string }[] = [
        { key: 'market', label: 'Market', tip: 'Market type' },
        { key: 'legs', label: 'Legs', tip: 'Total settled legs' },
        { key: 'win_rate', label: 'Win %', tip: 'Actual win rate' },
        { key: 'implied_win_rate', label: 'Implied %', tip: 'Market-implied win rate (avg 1/odds)' },
        { key: 'edge', label: 'Edge', tip: 'Actual − Implied. Your value above market pricing.' },
        { key: 'avg_odds', label: 'Avg Odds', tip: 'Average leg odds for this market' },
        { key: 'net_profit', label: 'P&L (U)', tip: 'Estimated net profit from legs in this market' },
    ];

    return (
        <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--border)' }}>
            <table className="w-full" style={{ borderCollapse: 'collapse' }}>
                <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-raised)' }}>
                        {cols.map(col => (
                            <th key={col.key}
                                className="px-4 py-3 text-left cursor-pointer select-none"
                                onClick={() => col.key !== 'market' && handleSort(col.key)}>
                                <div className="flex items-center gap-1">
                                    <span className="text-[10px] font-mono tracking-widest uppercase"
                                        style={{ color: sortKey === col.key ? 'var(--accent)' : 'var(--text-secondary)' }}>
                                        {col.label}
                                    </span>
                                    <TooltipIcon text={col.tip} align="center" />
                                    {sortKey === col.key && (
                                        <span style={{ color: 'var(--accent)', fontSize: 10 }}>
                                            {sortDir === 'desc' ? '↓' : '↑'}
                                        </span>
                                    )}
                                </div>
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {sorted.map((row, i) => {
                        const edgeColor = row.edge > 2 ? 'var(--win)' : row.edge > 0 ? 'var(--pending)' : 'var(--loss)';
                        const edgeBg = row.edge > 2 ? 'var(--win-bg)' : row.edge > 0 ? 'var(--pending-bg)' : 'var(--loss-bg)';
                        return (
                            <tr key={i} style={{
                                borderBottom: '1px solid var(--border)',
                                background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                            }}>
                                <td className="px-4 py-3">
                                    <span className="font-mono font-bold text-sm"
                                        style={{ color: 'var(--text-bright)' }}>{row.market}</span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        {row.legs}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="font-mono text-sm"
                                        style={{ color: row.win_rate >= 50 ? 'var(--win)' : 'var(--loss)' }}>
                                        {row.win_rate}%
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        {row.implied_win_rate}%
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="font-mono font-bold text-sm px-2 py-0.5 rounded"
                                        style={{ color: edgeColor, background: edgeBg }}>
                                        {row.edge > 0 ? '+' : ''}{row.edge}%
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        @{row.avg_odds}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className="font-mono font-bold text-sm"
                                        style={{ color: row.net_profit >= 0 ? 'var(--win)' : 'var(--loss)' }}>
                                        {row.net_profit >= 0 ? '+' : ''}{row.net_profit}U
                                    </span>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

// ── Custom weekend X-axis tick ─────────────────────────────────────────────────

function WeekendTick({ x, y, payload }: any) {
    const date = new Date(payload.value);
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    return (
        <text x={x} y={y + 12} textAnchor="middle"
            style={{ fontWeight: isWeekend ? 'bold' : 'normal',
                fill: isWeekend ? 'var(--accent)' : 'var(--text-secondary)',
                fontSize: 10 }}>
            {payload.value}
        </text>
    );
}

// ── Main Analytics page ────────────────────────────────────────────────────────

interface Props { filters: GlobalFilters; refreshKey: number }

export default function Analytics({ filters, refreshKey }: Props) {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const { selectedProfiles, setSelectedProfiles } = useProfileSelection({
        page: 'analytics',
        allProfiles: data?.profiles ?? [],
    });
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params: Record<string, unknown> = {
                date_from: filters.dateFrom || undefined,
                date_to: filters.dateTo || undefined,
            };
            if (selectedProfiles.length > 0) params.profiles = selectedProfiles;
            const d = await fetchAnalytics(params as any);
            setData(d);
        } catch {
            setData({
                stats: {
                    total_settled: 0, total_won_count: 0, win_rate: 0,
                    implied_win_rate: 0, edge: 0, total_units_bet: 0,
                    gross_return: 0, net_profit: 0, roi_percentage: 0,
                    avg_odds: 0, avg_units: 0, units_std: 0,
                    pending_count: 0, sharpe_ratio: null,
                    kelly_suggested_units: 0,
                    edge_trend: "neutral",
                    recent_edge_value: 0,
                    // New fields
                    biggest_win_units: null,
                    biggest_loss_units: null,
                    best_day_pnl: null,
                    worst_day_pnl: null,
                    current_streak: 0,
                    longest_win_streak: 0,
                    longest_loss_streak: 0,
                    profit_factor: 0,
                },
                history: [], odds_distribution: [], pnl_by_market: [],
                market_accuracy: [], correlation: [], profile_scatter: [],
                profiles: [], market_breakdown: [], rolling_edge: [],
                drawdown: [], return_distribution: null, time_patterns: null,
            });
        } finally { setLoading(false); }
    }, [selectedProfiles, filters, refreshKey]);

    useEffect(() => { load(); }, [load]);

    const rollingEdgeData = useMemo(() =>
        (data?.rolling_edge ?? []).map(d => ({
            ...d,
            edgePos: Math.max(0, d.rolling_edge),
            edgeNeg: Math.min(0, d.rolling_edge),
        })),
    [data?.rolling_edge]);

    if (!data?.stats) return (
        <div>
            <h1 className="font-display font-bold text-xl mb-5"
                style={{ color: 'var(--text-bright)' }}>Analytics</h1>
            <ProfileSelector profiles={[]} selectedProfiles={selectedProfiles}
                onChange={setSelectedProfiles} profileData={null} />
            <div className="card text-center py-16 mt-5">
                <p className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                    No analytics data yet. Generate and settle some slips first.
                </p>
            </div>
        </div>
    );

    const { stats } = data;

    return (
        <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .2s' }}>

            {/* Header + Profile Selector */}
            <div className="flex items-center justify-between mb-4">
                <h1 className="font-display font-bold text-xl"
                    style={{ color: 'var(--text-bright)' }}>Analytics</h1>
            </div>
            <div className="mb-5">
                <ProfileSelector
                    profiles={data.profiles}
                    selectedProfiles={selectedProfiles}
                    onChange={setSelectedProfiles}
                    profileData={data}
                />
            </div>

            {/* ── Hero KPI Row ─────────────────────────────────────────────────── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
                <KpiCard
                    label="Net Profit"
                    value={`${stats.net_profit > 0 ? '+' : ''}${stats.net_profit}U`}
                    color={stats.net_profit > 0 ? 'var(--win)' : stats.net_profit < 0 ? 'var(--loss)' : undefined}
                    sub={`${stats.total_settled} settled slips`}
                    tip="Total net profit in units."
                />
                <KpiCard
                    label="ROI"
                    value={`${stats.roi_percentage > 0 ? '+' : ''}${stats.roi_percentage}%`}
                    color={stats.roi_percentage > 0 ? 'var(--win)' : stats.roi_percentage < 0 ? 'var(--loss)' : undefined}
                    sub={`${stats.gross_return}U gross return`}
                    tip="Return on investment as a percentage of total staked."
                />
                <KpiCard
                    label="Overall Edge"
                    value={`${stats.edge > 0 ? '+' : ''}${stats.edge.toFixed(1)}%`}
                    color={stats.edge > 0 ? 'var(--win)' : stats.edge < 0 ? 'var(--loss)' : undefined}
                    sub={`Implied: ${stats.implied_win_rate.toFixed(1)}%`}
                    tip="Actual win rate minus market-implied win rate."
                />
                <KpiCard
                    label="Win Rate"
                    value={`${stats.win_rate.toFixed(1)}%`}
                    color={stats.win_rate > stats.implied_win_rate ? 'var(--win)' : 'var(--text-bright)'}
                    sub={`${stats.total_won_count} of ${stats.total_settled} won`}
                    tip="Percentage of settled slips that returned a win."
                />
            </div>

            {/* ── Betting Summary Row ──────────────────────────────────────────── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                <StatTile label="Total Staked" value={`${stats.total_units_bet}U`} />
                <StatTile label="Avg Units / Slip" value={`${stats.avg_units}U`}
                    sub={`±${stats.units_std?.toFixed(2) ?? '—'}U std`} />
                <StatTile label="Avg Odds" value={`@${stats.avg_odds.toFixed(2)}`} />
                <StatTile label="Pending" value={stats.pending_count ?? 0}
                    sub="slips awaiting settlement" />
            </div>

            {/* ── Financials ───────────────────────────────────────────────────── */}
            <SectionHeader icon="₿" title="Financials" />
            <FinancialsRow stats={stats} />

            {/* ── Strategy Health ───────────────────────────────────────────────── */}
            <SectionHeader icon="◈" title="Strategy Health" />

            {/* Health KPI cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                <EdgeTrendCard stats={stats} />
                <TargetStakeCard stats={stats} />
                <SharpeCard stats={stats} />
                <MaxDrawdownCard drawdown={data.drawdown ?? []} />
            </div>

            {/* Market insight cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                <MarketSignalsCard marketBreakdown={data.market_breakdown ?? []} />
                <MarketEfficiencyCard stats={stats} />
            </div>

            {/* ── History Tracking ─────────────────────────────────────────────── */}
            <SectionHeader icon="⟳" title="History Tracking" />

            {/* P&L and Drawdown side-by-side */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">

                {/* Cumulative P&L with Daily Bars */}
                <ChartCard title="Cumulative Net Profit"
                    tip="Cumulative line shows total profit over time. Daily bars show individual day P&L. Green bars = winning day, red bars = losing day.">
                    <ResponsiveContainer width="100%" height={220}>
                        <ComposedChart data={data.history ?? []} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                            <defs>
                                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--win)" stopOpacity={0.25} />
                                    <stop offset="95%" stopColor="var(--win)" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                            <XAxis dataKey="date" tick={<WeekendTick fontSize={10} />}
                                tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                            {/* Primary Y-axis for cumulative profit */}
                            <YAxis yAxisId="cumulative" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                axisLine={false} tickFormatter={v => `${v}U`} width={48} orientation="left" />
                            {/* Secondary Y-axis for daily net profit */}
                            <YAxis yAxisId="daily" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                axisLine={false} tickFormatter={v => `${v}U`} width={48} orientation="right" />
                            <Tooltip contentStyle={TT} content={({ active, payload, label }) => {
                                if (!active || !payload?.length) return null;
                                const daily = payload.find(p => p.dataKey === 'net_profit');
                                const cumulative = payload.find(p => p.dataKey === 'cumulative_profit');
                                
                                const dailyNum = daily?.value as number | undefined;
                                const cumulativeNum = cumulative?.value as number | undefined;
                                
                                return (
                                    <div style={TT}>
                                        <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{label}</p>
                                        {dailyNum != null && (
                                            <p><span style={{ color: 'var(--text-secondary)' }}>Daily: </span>
                                                <span style={{ color: dailyNum >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                    {dailyNum >= 0 ? '+' : ''}{dailyNum.toFixed(2)}U</span></p>
                                        )}
                                        {cumulativeNum != null && (
                                            <p><span style={{ color: 'var(--text-secondary)' }}>Cumulative: </span>
                                                <span style={{ color: cumulativeNum >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                    {cumulativeNum >= 0 ? '+' : ''}{cumulativeNum.toFixed(2)}U</span></p>
                                        )}
                                    </div>
                                );
                            }} />
                            <ReferenceLine y={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            {/* Daily bars - use secondary Y-axis */}
                            <Bar yAxisId="daily" dataKey="net_profit" barSize={6} radius={[2, 2, 0, 0]} opacity={0.6}>
                                {(data.history ?? []).map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={entry.net_profit >= 0 ? 'var(--win)' : 'var(--loss)'}
                                    />
                                ))}
                            </Bar>
                            {/* Cumulative line - use primary Y-axis */}
                            <Area yAxisId="cumulative" dataKey="cumulative_profit" stroke="var(--win)" strokeWidth={2}
                                fill="url(#pnlGrad)" dot={false} type="monotone" />
                        </ComposedChart>
                    </ResponsiveContainer>
                    {/* Inline summary */}
                    {(data.history ?? []).length > 0 && (() => {
                        const last = data.history![data.history!.length - 1];
                        return (
                            <div className="flex gap-4 mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                                <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                                    Latest: <span style={{ color: last.cumulative_profit >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                        {last.cumulative_profit >= 0 ? '+' : ''}{last.cumulative_profit.toFixed(2)}U
                                    </span>
                                </span>
                            </div>
                        );
                    })()}
                </ChartCard>

                {/* Drawdown */}
                <ChartCard title="Bankroll Drawdown"
                    tip="Distance from peak profit at each point. 0 = new high water mark. Deep dips indicate rough patches.">
                    {(data.drawdown ?? []).length < 2 ? (
                        <div className="flex items-center justify-center h-[220px]">
                            <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                                Not enough history for drawdown analysis.
                            </p>
                        </div>
                    ) : (
                        <>
                            <ResponsiveContainer width="100%" height={220}>
                                <AreaChart data={data.drawdown ?? []} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="var(--loss)" stopOpacity={0.08} />
                                            <stop offset="95%" stopColor="var(--loss)" stopOpacity={0.35} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                                    <XAxis dataKey="date" tick={<WeekendTick fontSize={10} />}
                                        tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                                    <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                        axisLine={false} tickFormatter={v => `${v}U`} width={48} />
                                    <Tooltip contentStyle={TT} content={({ active, payload, label }) => {
                                        if (!active || !payload?.length) return null;
                                        const d = payload[0]?.payload;
                                        return (
                                            <div style={TT}>
                                                <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{label}</p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Drawdown: </span>
                                                    <span style={{ color: 'var(--loss)', fontWeight: 'bold' }}>{d.drawdown.toFixed(2)}U</span></p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Peak: </span>
                                                    <span style={{ color: 'var(--win)' }}>{d.peak.toFixed(2)}U</span></p>
                                            </div>
                                        );
                                    }} />
                                    <ReferenceLine y={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                                    <Area dataKey="drawdown" stroke="var(--loss)" strokeWidth={2}
                                        fill="url(#ddGrad)" dot={false} type="monotone" />
                                </AreaChart>
                            </ResponsiveContainer>
                            {(() => {
                                const dd = data.drawdown ?? [];
                                const maxDD = dd.length ? Math.min(...dd.map(d => d.drawdown)) : 0;
                                const cur = dd.length ? dd[dd.length - 1].drawdown : 0;
                                return (
                                    <div className="flex gap-4 mt-2 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                                        <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                                            Max: <span style={{ color: 'var(--loss)', fontWeight: 'bold' }}>{maxDD.toFixed(2)}U</span>
                                        </span>
                                        <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                                            Current: <span style={{ color: cur < 0 ? 'var(--loss)' : 'var(--win)', fontWeight: 'bold' }}>
                                                {cur.toFixed(2)}U</span>
                                        </span>
                                    </div>
                                );
                            })()}
                        </>
                    )}
                </ChartCard>
            </div>

            {/* Rolling Edge — full width */}
            <ChartCard title="Rolling Edge (14-day window)"
                className="mb-8"
                tip="Rolling win rate minus rolling implied win rate over the last 14 days. Green above zero = beating the market. A falling edge on a rising P&L curve is an early warning sign.">
                {rollingEdgeData.length < 3 ? (
                    <div className="flex items-center justify-center h-60">
                        <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                            Need more settled slips for rolling analysis (min 3).
                        </p>
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={240}>
                        <ComposedChart data={rollingEdgeData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                            <defs>
                                <linearGradient id="edgePosGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--win)" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="var(--win)" stopOpacity={0.02} />
                                </linearGradient>
                                <linearGradient id="edgeNegGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--loss)" stopOpacity={0.02} />
                                    <stop offset="95%" stopColor="var(--loss)" stopOpacity={0.3} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                            <XAxis dataKey="date" tick={<WeekendTick fontSize={10} />}
                                tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                axisLine={false} tickFormatter={v => `${v}%`} width={48} />
                            <Tooltip contentStyle={TT} content={({ active, payload, label }) => {
                                if (!active || !payload?.length) return null;
                                const d = payload[0]?.payload;
                                return (
                                    <div style={TT}>
                                        <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{label}</p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Edge: </span>
                                            <span style={{ color: d.rolling_edge >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                {d.rolling_edge >= 0 ? '+' : ''}{d.rolling_edge}%</span></p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Win Rate: </span>
                                            <span style={{ color: 'var(--text-primary)' }}>{d.rolling_win_rate}%</span></p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Implied: </span>
                                            <span style={{ color: 'var(--text-primary)' }}>{d.rolling_implied}%</span></p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Sample: </span>
                                            <span style={{ color: 'var(--text-primary)' }}>n={d.sample_size}</span></p>
                                    </div>
                                );
                            }} />
                            <ReferenceLine y={0} stroke="rgba(255,255,255,0.4)" strokeDasharray="4 2" strokeWidth={1.5} />
                            <Area dataKey="edgePos" fill="url(#edgePosGrad)" stroke="none" type="monotone" />
                            <Area dataKey="edgeNeg" fill="url(#edgeNegGrad)" stroke="none" type="monotone" />
                            <Line dataKey="rolling_edge" stroke="var(--chart-1)" strokeWidth={2.5}
                                dot={false} type="monotone" />
                        </ComposedChart>
                    </ResponsiveContainer>
                )}
            </ChartCard>

            {/* ── Market Intelligence ──────────────────────────────────────────── */}
            <SectionHeader icon="◎" title="Market Intelligence" />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">

                {/* Market breakdown table — 2/3 width */}
                <div className="lg:col-span-2">
                    <div className="card p-4">
                        <div className="flex items-center gap-2 mb-4">
                            <p className="font-mono text-[11px] tracking-widest uppercase"
                                style={{ color: 'var(--text-secondary)' }}>Market Breakdown</p>
                            <TooltipIcon text="Per-market stats with implied win rate from per-leg odds. Edge = Actual − Implied. Sort any column." align="right" />
                        </div>
                        {(data.market_breakdown ?? []).length === 0 ? (
                            <p className="font-mono text-xs text-center py-8" style={{ color: 'var(--text-secondary)' }}>
                                No per-leg data yet.
                            </p>
                        ) : (
                            <MarketTable data={data.market_breakdown ?? []} />
                        )}
                    </div>
                </div>

                {/* Edge per market — 1/3 width */}
                <ChartCard title="Edge by Market"
                    tip="Your edge (actual − implied win rate) per market. Green = profitable, Red = losing value.">
                    <ResponsiveContainer width="100%" height={260}>
                        <BarChart
                            data={[...(data.market_breakdown ?? [])].sort((a, b) => b.edge - a.edge)}
                            layout="vertical"
                            margin={{ left: 0, right: 30, top: 5, bottom: 0 }}>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4"
                                vertical={false} strokeOpacity={0.4} />
                            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false} tickFormatter={v => `${v}%`}
                                axisLine={{ stroke: 'var(--border)' }} />
                            <YAxis type="category" dataKey="market" width={70}
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false} axisLine={false} />
                            <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                if (!active || !payload?.length) return null;
                                const d = payload[0]?.payload;
                                return (
                                    <div style={TT}>
                                        <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>{d.market}</p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Edge: </span>
                                            <span style={{ color: d.edge >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                {d.edge >= 0 ? '+' : ''}{d.edge}%</span></p>
                                    </div>
                                );
                            }} />
                            <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" />
                            <Bar dataKey="edge" radius={[0, 3, 3, 0]}>
                                {(data.market_breakdown ?? []).map((entry, i) => (
                                    <Cell key={i} fill={entry.edge >= 0 ? 'var(--win)' : 'var(--loss)'} fillOpacity={0.8} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </ChartCard>
            </div>
        </div>
    );
}