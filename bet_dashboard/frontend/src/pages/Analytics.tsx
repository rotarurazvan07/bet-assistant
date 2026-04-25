import { useEffect, useState, useCallback, useMemo } from 'react';
import {
    ResponsiveContainer, LineChart, Line, BarChart, Bar, AreaChart, Area,
    XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, ComposedChart,
    ScatterChart, Scatter, Cell, Legend,
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

// ── EV Health panel ────────────────────────────────────────────────────────────

function EVHealthPanel({ stats, marketBreakdown, drawdown }: {
    stats: SlipStats;
    marketBreakdown: MarketBreakdown[];
    drawdown: { drawdown: number }[];
}) {
    const maxDD = drawdown.length ? Math.min(...drawdown.map(d => d.drawdown)) : 0;
    const bestMarket = marketBreakdown[0];
    const worstMarket = [...marketBreakdown].sort((a, b) => a.edge - b.edge)[0];

    const signals = [
        {
            label: 'Overall Edge',
            value: `${stats.edge > 0 ? '+' : ''}${stats.edge}%`,
            status: stats.edge > 2 ? 'good' : stats.edge > 0 ? 'warn' : 'bad',
            tip: 'Actual Win Rate minus Implied Win Rate. Positive = beating the market.',
        },
        {
            label: 'Sharpe Ratio',
            value: stats.sharpe_ratio !== null && stats.sharpe_ratio !== undefined
                ? stats.sharpe_ratio.toFixed(2)
                : '—',
            status: stats.sharpe_ratio === null ? 'neutral'
                : stats.sharpe_ratio > 1.5 ? 'good'
                : stats.sharpe_ratio > 0.5 ? 'warn' : 'bad',
            tip: 'Risk-adjusted return. >1.5 = consistent, 0.5–1.5 = acceptable, <0.5 = volatile.',
        },
        {
            label: 'Max Drawdown',
            value: `${maxDD.toFixed(1)}U`,
            status: maxDD > -3 ? 'good' : maxDD > -8 ? 'warn' : 'bad',
            tip: 'Worst peak-to-trough decline. Smaller magnitude is better.',
        },
        {
            label: 'Best Market',
            value: bestMarket ? bestMarket.market : '—',
            sub: bestMarket ? `+${bestMarket.edge}% edge` : '',
            status: bestMarket && bestMarket.edge > 0 ? 'good' : 'neutral',
            tip: 'Market with highest edge (actual win rate vs implied).',
        },
        {
            label: 'Avoid Market',
            value: worstMarket && worstMarket.edge < 0 ? worstMarket.market : '—',
            sub: worstMarket && worstMarket.edge < 0 ? `${worstMarket.edge}% edge` : '',
            status: worstMarket && worstMarket.edge < -2 ? 'bad' : 'neutral',
            tip: 'Market with lowest (most negative) edge.',
        },
    ];

    const statusColor: Record<string, string> = {
        good: 'var(--win)', warn: 'var(--pending)', bad: 'var(--loss)', neutral: 'var(--text-secondary)',
    };
    const statusBg: Record<string, string> = {
        good: 'var(--win-bg)', warn: 'var(--pending-bg)', bad: 'var(--loss-bg)', neutral: 'var(--bg-raised)',
    };

    return (
        <div className="card p-4 mb-5" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2 mb-3">
                <span className="text-[10px] font-mono tracking-widest uppercase"
                    style={{ color: 'var(--text-secondary)' }}>Strategy Health</span>
                <TooltipIcon text="At-a-glance overview of your betting strategy's key signals." align="right" />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {signals.map(sig => (
                    <div key={sig.label}
                        className="rounded-xl px-4 py-3"
                        style={{ background: statusBg[sig.status], border: `1px solid ${statusColor[sig.status]}22` }}>
                        <p className="text-[10px] font-mono uppercase mb-1"
                            style={{ color: 'var(--text-secondary)' }}>{sig.label}</p>
                        <p className="font-display font-bold text-xl leading-none"
                            style={{ color: statusColor[sig.status] }}>{sig.value}</p>
                        {sig.sub && (
                            <p className="text-[10px] font-mono mt-1"
                                style={{ color: statusColor[sig.status], opacity: 0.8 }}>{sig.sub}</p>
                        )}
                        <TooltipIcon text={sig.tip} align="center" />
                    </div>
                ))}
            </div>
        </div>
    );
}

// ── Extended stat card ─────────────────────────────────────────────────────────

function StatTile({
    label, value, sub, color, tip, highlight = false,
}: {
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
            <span className="font-display font-bold text-2xl leading-none"
                style={{ color: color ?? 'var(--text-bright)' }}>{value}</span>
            {sub && <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>{sub}</span>}
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

function WeekendTick({ x, y, payload, ...rest }: any) {
    const date = new Date(payload.value);
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    return (
        <text x={x} y={y} {...rest}
            style={{ fontWeight: isWeekend ? 'bold' : 'normal',
                fill: isWeekend ? 'var(--text-bright)' : 'var(--text-secondary)' }}>
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
                },
                history: [], odds_distribution: [], pnl_by_market: [],
                market_accuracy: [], correlation: [], profile_scatter: [],
                profiles: [], market_breakdown: [], rolling_edge: [],
                drawdown: [], return_distribution: null, time_patterns: null,
            });
        } finally { setLoading(false); }
    }, [selectedProfiles, filters, refreshKey]);

    useEffect(() => { load(); }, [load]);

    // ── Derived rolling edge data (green above / red below zero) ───────────────
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

            {/* Header */}
            <div className="flex items-center justify-between mb-5">
                <h1 className="font-display font-bold text-xl"
                    style={{ color: 'var(--text-bright)' }}>Analytics</h1>
            </div>

            {/* Profile selector */}
            <div className="mb-5">
                <ProfileSelector
                    profiles={data.profiles}
                    selectedProfiles={selectedProfiles}
                    onChange={setSelectedProfiles}
                    profileData={data}
                />
            </div>

            {/* Strategy Health */}
            <EVHealthPanel
                stats={stats}
                marketBreakdown={data.market_breakdown ?? []}
                drawdown={data.drawdown ?? []}
            />

            {/* ── Stats grid ──────────────────────────────────────────────────── */}
            <div className="grid grid-cols-3 md:grid-cols-5 gap-3 mb-2">
                <StatTile label="Total Bet" value={`${stats.total_units_bet} U`} />
                <StatTile label="Gross Return" value={`${stats.gross_return} U`} />
                <StatTile
                    label="Net Profit"
                    value={`${stats.net_profit > 0 ? '+' : ''}${stats.net_profit} U`}
                    color={stats.net_profit > 0 ? 'var(--win)' : stats.net_profit < 0 ? 'var(--loss)' : undefined}
                />
                <StatTile
                    label="Win Rate"
                    value={`${stats.win_rate}%`}
                    color={stats.win_rate > 50 ? 'var(--win)' : undefined}
                />
                <StatTile
                    label="Implied Win Rate"
                    value={`${stats.implied_win_rate}%`}
                    sub="Market expects"
                    tip="avg(1/odds) — what the market says you should win."
                />
            </div>
            <div className="grid grid-cols-3 md:grid-cols-5 gap-3 mb-6">
                <StatTile
                    label="Edge ★"
                    value={`${stats.edge > 0 ? '+' : ''}${stats.edge}%`}
                    sub="vs market"
                    color={stats.edge > 0 ? 'var(--win)' : stats.edge < 0 ? 'var(--loss)' : undefined}
                    tip="Edge = Win Rate − Implied Win Rate. The single most important metric."
                    highlight
                />
                <StatTile
                    label="ROI"
                    value={`${stats.roi_percentage}%`}
                    color={stats.roi_percentage > 0 ? 'var(--win)' : stats.roi_percentage < 0 ? 'var(--loss)' : undefined}
                />
                <StatTile
                    label="Avg Odds"
                    value={`@${stats.avg_odds}`}
                    tip="Average total odds across settled slips — context for all other metrics."
                />
                <StatTile
                    label="Avg Units"
                    value={`${stats.avg_units} U`}
                    sub={stats.units_std ? `σ ${stats.units_std}` : undefined}
                    tip="Average stake per slip. σ shows staking consistency."
                />
                <StatTile
                    label="Settled / Pending"
                    value={stats.total_settled}
                    sub={`${stats.pending_count} pending`}
                    tip="Settled slips vs currently active (pending) slips."
                />
            </div>

            {/* ── History Tracking ────────────────────────────────────────────── */}
            <SectionHeader icon="⟳" title="History Tracking" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">

                {/* Cumulative P&L */}
                <ChartCard title="Cumulative Net Profit"
                    tip="Total net profit accumulated over time.">
                    <ResponsiveContainer width="100%" height={240}>
                        <AreaChart data={data.history ?? []} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                            <defs>
                                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--win)" stopOpacity={0.25} />
                                    <stop offset="95%" stopColor="var(--win)" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                            <XAxis dataKey="date" tick={<WeekendTick fontSize={10} />}
                                tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                axisLine={false} tickFormatter={v => `${v}U`} width={48} />
                            <Tooltip contentStyle={TT} content={({ active, payload, label }) => {
                                if (!active || !payload?.length) return null;
                                const v = Number(payload[0].value);
                                return (
                                    <div style={TT}>
                                        <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{label}</p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Net Profit: </span>
                                            <span style={{ color: v >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                {v >= 0 ? '+' : ''}{v.toFixed(2)}U</span></p>
                                    </div>
                                );
                            }} />
                            <ReferenceLine y={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Area dataKey="cumulative_profit" stroke="var(--win)" strokeWidth={2}
                                fill="url(#pnlGrad)" dot={false} type="monotone" />
                        </AreaChart>
                    </ResponsiveContainer>
                </ChartCard>

                {/* Rolling Edge — replaces ROI over time */}
                <ChartCard title="Rolling Edge (14-day window)"
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
                                <XAxis dataKey="date" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
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

                {/* Drawdown — replaces Win Rate cumulative */}
                <ChartCard title="Bankroll Drawdown"
                    tip="Distance from peak profit at each point. 0 = new high water mark. Deep dips indicate rough patches. Annotates the worst drawdown.">
                    {(data.drawdown ?? []).length < 2 ? (
                        <div className="flex items-center justify-center h-60">
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
                                    <XAxis dataKey="date" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
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
                                    <div className="flex gap-4 mt-2">
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

                {/* Odds bucket with implied win rate overlay */}
                <ChartCard title="Odds Range — Win Rate vs Implied"
                    tip="Bars show actual win rate per odds bucket. Line shows what the market implies you should win. Gap above the line = your edge in that range.">
                    <ResponsiveContainer width="100%" height={240}>
                        <ComposedChart data={data.odds_distribution ?? []} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                            <XAxis dataKey="range" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                axisLine={false} width={45} domain={[0, 100]} tickFormatter={v => `${v}%`} />
                            <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                if (!active || !payload?.length) return null;
                                const d = payload[0]?.payload;
                                return (
                                    <div style={TT}>
                                        <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{d.range}</p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Actual: </span>
                                            <span style={{ color: d.win_rate >= d.implied_win_rate ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                {d.win_rate}%</span></p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Implied: </span>
                                            <span style={{ color: 'var(--pending)' }}>{d.implied_win_rate}%</span></p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>Edge: </span>
                                            <span style={{ color: d.edge >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                {d.edge >= 0 ? '+' : ''}{d.edge}%</span></p>
                                        <p><span style={{ color: 'var(--text-secondary)' }}>n= </span>{d.count}</p>
                                    </div>
                                );
                            }} />
                            <ReferenceLine y={50} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Bar dataKey="win_rate" name="Actual Win %" radius={[3, 3, 0, 0]}>
                                {(data.odds_distribution ?? []).map((entry, i) => (
                                    <Cell key={i}
                                        fill={entry.win_rate >= entry.implied_win_rate ? 'var(--win)' : 'var(--loss)'}
                                        fillOpacity={0.75} />
                                ))}
                            </Bar>
                            <Line dataKey="implied_win_rate" name="Implied Win %" stroke="var(--pending)"
                                strokeWidth={2} dot={{ r: 4, fill: 'var(--pending)', stroke: 'var(--bg-card)', strokeWidth: 2 }}
                                type="monotone" />
                        </ComposedChart>
                    </ResponsiveContainer>
                </ChartCard>
            </div>

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

            {/* ── Risk & Variance ──────────────────────────────────────────────── */}
            <SectionHeader icon="◈" title="Risk & Variance" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">

                {/* Return distribution histogram */}
                <ChartCard title="Return Distribution"
                    tip="Frequency of per-slip P&L. Right-skewed = dependent on rare big wins. Symmetric = consistent edge. Mean vs Median gap reveals skew.">
                    {!data.return_distribution?.bins.length ? (
                        <div className="flex items-center justify-center h-60">
                            <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>Not enough data.</p>
                        </div>
                    ) : (
                        <>
                            <ResponsiveContainer width="100%" height={220}>
                                <BarChart data={data.return_distribution.bins}
                                    margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4"
                                        vertical={false} strokeOpacity={0.4} />
                                    <XAxis dataKey="range" tick={{ fill: 'var(--text-secondary)', fontSize: 9 }}
                                        tickLine={false} axisLine={{ stroke: 'var(--border)' }}
                                        tickFormatter={v => `${v}U`} />
                                    <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                        tickLine={false} axisLine={false} width={35} />
                                    <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                        if (!active || !payload?.length) return null;
                                        const d = payload[0]?.payload;
                                        return (
                                            <div style={TT}>
                                                <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>
                                                    {d.range}U to {d.range_end}U</p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Count: </span>
                                                    <span style={{ fontWeight: 'bold' }}>{d.count}</span></p>
                                            </div>
                                        );
                                    }} />
                                    <ReferenceLine x="0.0" stroke="rgba(255,255,255,0.3)" strokeDasharray="4 2" />
                                    <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                                        {data.return_distribution.bins.map((entry, i) => (
                                            <Cell key={i}
                                                fill={entry.is_positive ? 'var(--win)' : 'var(--loss)'}
                                                fillOpacity={0.75} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                            <div className="flex gap-4 mt-2">
                                <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                                    Mean: <span style={{ color: data.return_distribution.mean >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                        {data.return_distribution.mean >= 0 ? '+' : ''}{data.return_distribution.mean}U</span>
                                </span>
                                <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                                    Median: <span style={{ color: data.return_distribution.median >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                        {data.return_distribution.median >= 0 ? '+' : ''}{data.return_distribution.median}U</span>
                                </span>
                                {data.return_distribution.mean !== data.return_distribution.median && (
                                    <span className="text-[11px] font-mono" style={{ color: 'var(--pending)' }}>
                                        ⚠ Mean≠Median (skewed)
                                    </span>
                                )}
                            </div>
                        </>
                    )}
                </ChartCard>

                {/* Day of week pattern */}
                <ChartCard title="Win Rate by Day of Week"
                    tip="Leg-level win rate per day. Reveals systematic patterns — e.g. consistently worse on Sundays. Bars below 50% are red.">
                    {!(data.time_patterns?.day_of_week?.length) ? (
                        <div className="flex items-center justify-center h-60">
                            <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                                Not enough data with leg datetimes.
                            </p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={data.time_patterns.day_of_week}
                                margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                <CartesianGrid stroke="var(--border)" strokeDasharray="4 4"
                                    vertical={false} strokeOpacity={0.4} />
                                <XAxis dataKey="key" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                                    tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                                <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                    axisLine={false} domain={[0, 100]} tickFormatter={v => `${v}%`} width={45} />
                                <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                    if (!active || !payload?.length) return null;
                                    const d = payload[0]?.payload;
                                    return (
                                        <div style={TT}>
                                            <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>{d.key}</p>
                                            <p><span style={{ color: 'var(--text-secondary)' }}>Win Rate: </span>
                                                <span style={{ color: d.win_rate >= 50 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                    {d.win_rate}%</span></p>
                                            <p><span style={{ color: 'var(--text-secondary)' }}>n= </span>{d.total} legs</p>
                                        </div>
                                    );
                                }} />
                                <ReferenceLine y={50} stroke="rgba(255,255,255,0.3)" strokeDasharray="4 2" />
                                <Bar dataKey="win_rate" radius={[4, 4, 0, 0]}>
                                    {(data.time_patterns.day_of_week ?? []).map((entry, i) => (
                                        <Cell key={i}
                                            fill={entry.win_rate >= 50 ? 'var(--win)' : 'var(--loss)'}
                                            fillOpacity={0.75} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </ChartCard>
            </div>

            {/* ── Correlation Analysis ─────────────────────────────────────────── */}
            <SectionHeader icon="⬡" title="Correlation Analysis" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">

                {/* Win rate by legs — improved with implied overlay */}
                <ChartCard title="Win Rate vs Slip Complexity"
                    tip="Win rate by number of legs. Bars = actual win rate. Line = implied win rate at those odds. The gap is your edge per complexity level.">
                    {(() => {
                        const byLegs: Record<number, { total: number; won: number; sum_implied: number }> = {};
                        (data.correlation ?? []).forEach(r => {
                            if (!byLegs[r.legs_count]) byLegs[r.legs_count] = { total: 0, won: 0, sum_implied: 0 };
                            byLegs[r.legs_count].total++;
                            byLegs[r.legs_count].sum_implied += r.total_odds > 0 ? 1 / r.total_odds : 0;
                            if (r.status === 'Won') byLegs[r.legs_count].won++;
                        });
                        const legsData = Object.entries(byLegs).map(([k, v]) => ({
                            legs: +k,
                            win_rate: Math.round((v.won / v.total) * 100),
                            implied_win_rate: Math.round((v.sum_implied / v.total) * 100),
                            count: v.total,
                        })).sort((a, b) => a.legs - b.legs);
                        return (
                            <ResponsiveContainer width="100%" height={250}>
                                <ComposedChart data={legsData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                                    <XAxis dataKey="legs" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                        tickLine={false} axisLine={{ stroke: 'var(--border)' }}
                                        label={{ value: 'Legs', fill: 'var(--text-secondary)', fontSize: 10, dy: 12 }} />
                                    <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                        axisLine={false} width={45} domain={[0, 100]} tickFormatter={v => `${v}%`} />
                                    <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                        if (!active || !payload?.length) return null;
                                        const d = payload[0]?.payload;
                                        return (
                                            <div style={TT}>
                                                <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>
                                                    {d.legs} Leg{d.legs !== 1 ? 's' : ''}</p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Win Rate: </span>
                                                    <span style={{ color: d.win_rate >= d.implied_win_rate ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                        {d.win_rate}%</span></p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Implied: </span>
                                                    <span style={{ color: 'var(--pending)' }}>{d.implied_win_rate}%</span></p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>n= </span>{d.count}</p>
                                            </div>
                                        );
                                    }} />
                                    <ReferenceLine y={50} stroke="var(--border-strong)" strokeDasharray="4 2" />
                                    <Bar dataKey="win_rate" fill="var(--chart-1)" fillOpacity={0.75} radius={[3, 3, 0, 0]} />
                                    <Line dataKey="implied_win_rate" stroke="var(--pending)" strokeWidth={2}
                                        dot={{ r: 4, fill: 'var(--pending)', stroke: 'var(--bg-card)', strokeWidth: 2 }}
                                        type="monotone" />
                                </ComposedChart>
                            </ResponsiveContainer>
                        );
                    })()}
                </ChartCard>

                {/* Profile scatter with break-even line */}
                <ChartCard title="Profile — Avg Odds vs Win Rate"
                    tip="Bubble size = volume. The curved line is the break-even threshold (win rate = 1/avg_odds). Bubbles ABOVE the curve are profitable regardless of luck.">
                    {!(data.profile_scatter?.length) ? (
                        <div className="flex items-center justify-center h-60">
                            <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>No profile data.</p>
                        </div>
                    ) : (() => {
                        // Generate break-even curve points
                        const allOdds = data.profile_scatter.map(p => p.avg_odds);
                        const minO = Math.max(1.1, Math.min(...allOdds) - 0.3);
                        const maxO = Math.max(...allOdds) + 0.3;
                        const breakEvenLine = Array.from({ length: 20 }, (_, i) => {
                            const o = minO + (i / 19) * (maxO - minO);
                            return { x: parseFloat(o.toFixed(2)), y: parseFloat((100 / o).toFixed(1)) };
                        });
                        return (
                            <ResponsiveContainer width="100%" height={250}>
                                <ComposedChart margin={{ left: 0, right: 20, top: 5, bottom: 10 }}>
                                    <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" strokeOpacity={0.4} />
                                    <XAxis type="number" dataKey="x" name="Avg Odds"
                                        tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                        axisLine={{ stroke: 'var(--border)' }} tickFormatter={v => `@${v}`}
                                        label={{ value: 'Avg Odds', fill: 'var(--text-secondary)', fontSize: 10, dy: 14 }} />
                                    <YAxis type="number" dataKey="y" name="Win Rate %"
                                        tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false}
                                        axisLine={false} tickFormatter={v => `${v}%`} domain={[0, 100]} width={45} />
                                    <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                        if (!active || !payload?.length) return null;
                                        const d = payload[0]?.payload;
                                        if (!d?.profile) return null;
                                        return (
                                            <div style={TT}>
                                                <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>{d.profile}</p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Avg Odds: </span>@{d.avg_odds}</p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Win Rate: </span>
                                                    <span style={{ color: d.win_rate >= d.break_even_win_rate ? 'var(--win)' : 'var(--loss)' }}>
                                                        {d.win_rate}%</span></p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Break-even: </span>{d.break_even_win_rate}%</p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>P&L: </span>
                                                    <span style={{ color: d.net_profit >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                        {d.net_profit >= 0 ? '+' : ''}{d.net_profit}U</span></p>
                                                <p><span style={{ color: 'var(--text-secondary)' }}>Volume: </span>{d.volume}</p>
                                            </div>
                                        );
                                    }} />
                                    {/* Break-even curve */}
                                    <Line
                                        data={breakEvenLine}
                                        dataKey="y"
                                        stroke="rgba(245,158,11,0.5)"
                                        strokeWidth={1.5}
                                        strokeDasharray="6 3"
                                        dot={false}
                                        type="monotone"
                                        legendType="none"
                                    />
                                    {/* Profile bubbles */}
                                    <ScatterChart>
                                        <Scatter
                                            data={data.profile_scatter.map(p => ({
                                                ...p, x: p.avg_odds, y: p.win_rate,
                                            }))}
                                            shape={(props: any) => {
                                                const { cx, cy, payload } = props;
                                                const r = Math.max(5, Math.min(16, payload.volume * 2.5));
                                                const isAboveBreakEven = payload.win_rate >= payload.break_even_win_rate;
                                                const color = isAboveBreakEven ? 'var(--win)' : 'var(--loss)';
                                                return (
                                                    <g>
                                                        <circle cx={cx} cy={cy} r={r}
                                                            fill={color} fillOpacity={0.3} stroke={color} strokeWidth={2} />
                                                        <text x={cx} y={cy + 1} textAnchor="middle"
                                                            fontSize={9} fill={color} fontWeight="bold" dominantBaseline="middle">
                                                            {payload.profile.slice(0, 3).toUpperCase()}
                                                        </text>
                                                    </g>
                                                );
                                            }}
                                        />
                                    </ScatterChart>
                                </ComposedChart>
                            </ResponsiveContainer>
                        );
                    })()}
                    <p className="text-[10px] font-mono mt-2" style={{ color: 'var(--text-secondary)' }}>
                        <span style={{ color: 'var(--pending)', opacity: 0.7 }}>— — </span>Break-even line
                        (above = profitable)
                    </p>
                </ChartCard>
            </div>
        </div>
    );
}
