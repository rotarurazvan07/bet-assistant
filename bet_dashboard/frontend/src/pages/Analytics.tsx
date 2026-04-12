import { useEffect, useState, useCallback } from 'react';
import {
    ResponsiveContainer, LineChart, Line, BarChart, Bar,
    XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
    ScatterChart, Scatter, Cell, Legend,
} from 'recharts';
import { fetchAnalytics, fetchProfiles } from '../api/data';
import { StatCard, SectionHeader } from '../components/ui';
import type { GlobalFilters } from '../components/Layout';
import type { AnalyticsData, ProfilesMap } from '../types';

const tooltipStyle = {
    background: 'var(--bg-card)', border: '1px solid var(--border-strong)',
    borderRadius: 8, fontSize: 11, fontFamily: 'JetBrains Mono, monospace',
    color: 'var(--text-secondary)',
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
};

const enhancedTooltipStyle = {
    ...tooltipStyle,
    padding: '10px 14px',
};

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="card p-4">
            <p className="font-mono text-[11px] tracking-widest uppercase mb-4"
                style={{ color: 'var(--text-secondary)' }}>{title}</p>
            {children}
        </div>
    );
}

const STORAGE_KEY = 'analytics_state';

interface Props { filters: GlobalFilters; refreshKey: number }

export default function Analytics({ filters, refreshKey }: Props) {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [profile, setProfile] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).profile : 'all';
    });
    const [loading, setLoading] = useState(false);
    const [profiles, setProfiles] = useState<ProfilesMap>({});

    // Persist profile to localStorage
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ profile }));
    }, [profile]);

    // Load profiles on mount
    useEffect(() => {
        fetchProfiles().then(p => setProfiles(p ?? {})).catch(() => setProfiles({}));
    }, []);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const d = await fetchAnalytics({
                profile: profile === 'all' ? undefined : profile,
                date_from: filters.dateFrom || undefined,
                date_to: filters.dateTo || undefined,
            });
            // Debug: log analytics response
            console.log('[Analytics] Response:', {
                profile,
                history: d.history?.length ?? 0,
                pnl_by_market: d.pnl_by_market?.length ?? 0,
                profile_scatter: d.profile_scatter?.length ?? 0,
                odds_distribution: d.odds_distribution?.length ?? 0,
                stats: d.stats,
            });
            setData(d);
        } catch (err) {
            console.error('[Analytics] Error:', err);
            // Set empty state on error
            setData({
                stats: { total_settled: 0, total_won_count: 0, win_rate: 0, total_units_bet: 0, gross_return: 0, net_profit: 0, roi_percentage: 0 },
                history: [], odds_distribution: [], pnl_by_market: [], market_accuracy: [],
                correlation: [], profile_scatter: [],
            });
        } finally { setLoading(false); }
    }, [profile, filters, refreshKey]);

    useEffect(() => { load(); }, [load]);

    // Empty state - show clean message when no data
    if (!data || !data.stats) return (
        <div>
            <div className="flex items-center justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Analytics
                </h1>
            </div>
            <div className="card text-center py-16">
                <p className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                    No analytics data available.
                </p>
                <p className="font-mono text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                    Analytics will appear once you have generated and settled some betting slips.
                </p>
            </div>
        </div>
    );

    const stats = data.stats;

    return (
        <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .2s' }}>

            {/* Header + profile filter */}
            <div className="flex items-center justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Analytics
                </h1>
                <select className="field w-44" value={profile} onChange={e => setProfile(e.target.value)}>
                    <option value="all">All Profiles</option>
                    {Object.keys(profiles).map(name => (
                        <option key={name} value={name}>{name.toUpperCase()}</option>
                    ))}
                    <option value="manual">MANUAL</option>
                </select>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-8">
                <StatCard label="Total Bet" value={`${stats.total_units_bet} U`} accent />
                <StatCard label="Net Profit" value={`${stats.net_profit > 0 ? '+' : ''}${stats.net_profit} U`}
                    positive={stats.net_profit > 0} negative={stats.net_profit < 0} />
                <StatCard label="Win Rate" value={`${stats.win_rate}%`} positive={stats.win_rate > 50} />
                <StatCard label="ROI" value={`${stats.roi_percentage}%`}
                    positive={stats.roi_percentage > 0} negative={stats.roi_percentage < 0} />
                <StatCard label="Settled" value={stats.total_settled} />
                <StatCard label="Won" value={stats.total_won_count} positive={stats.total_won_count > 0} />
            </div>

            {/* ── History ──────────────────────────────────────────────────────── */}
            <SectionHeader icon="⟳" title="History Tracking" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">

                {/* Cumulative P&L */}
                <ChartCard title="Cumulative Net Profit">
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={data.history ?? []} margin={{ left: 5, right: 10, top: 5, bottom: 0 }}>
                            <CartesianGrid
                                stroke="var(--border)"
                                strokeDasharray="4 4"
                                vertical={false}
                                strokeOpacity={0.4}
                            />
                            <XAxis
                                dataKey="date"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                            />
                            <YAxis
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={(value) => `${value} U`}
                                width={50}
                            />
                            <Tooltip
                                contentStyle={enhancedTooltipStyle}
                                content={({ active, payload, label }) => {
                                    if (!active || !payload?.length) return null;
                                    const value = Number(payload[0].value);
                                    return (
                                        <div style={enhancedTooltipStyle}>
                                            <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                {label}
                                            </p>
                                            <p style={{ margin: '3px 0' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Net Profit: </span>
                                                <span style={{ color: value >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                    {value >= 0 ? '+' : ''}{value.toFixed(2)} U
                                                </span>
                                            </p>
                                        </div>
                                    );
                                }}
                            />
                            <ReferenceLine y={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Line
                                dataKey="cumulative_profit"
                                name="Net Profit"
                                stroke="var(--chart-2)"
                                strokeWidth={2}
                                dot={false}
                                type="monotone"
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </ChartCard>

                {/* Cumulative + Rolling Win Rate */}
                <ChartCard title="Win Rate — Cumulative vs Rolling (10)">
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={data.history ?? []} margin={{ left: 5, right: 10, top: 5, bottom: 0 }}>
                            <CartesianGrid
                                stroke="var(--border)"
                                strokeDasharray="4 4"
                                vertical={false}
                                strokeOpacity={0.4}
                            />
                            <XAxis
                                dataKey="date"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                            />
                            <YAxis
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                domain={[0, 100]}
                                unit="%"
                                tickFormatter={(value) => `${value}%`}
                                width={45}
                            />
                            <Tooltip
                                contentStyle={enhancedTooltipStyle}
                                content={({ active, payload, label }) => {
                                    if (!active || !payload?.length) return null;
                                    const cumWin = payload.find(p => p.dataKey === 'win_rate')?.value;
                                    const rollWin = payload.find(p => p.dataKey === 'rolling_win_rate')?.value;
                                    return (
                                        <div style={enhancedTooltipStyle}>
                                            <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                {label}
                                            </p>
                                            {cumWin != null && (
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--chart-1)' }}>●</span>
                                                    <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>Cumulative: </span>
                                                    <span style={{ fontWeight: 'bold' }}>{Number(cumWin).toFixed(1)}%</span>
                                                </p>
                                            )}
                                            {rollWin != null && (
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--chart-3)' }}>●</span>
                                                    <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>Rolling (10): </span>
                                                    <span style={{ fontWeight: 'bold' }}>{Number(rollWin).toFixed(1)}%</span>
                                                </p>
                                            )}
                                        </div>
                                    );
                                }}
                            />
                            <ReferenceLine y={50} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Line
                                dataKey="win_rate"
                                name="Cumulative Win%"
                                stroke="var(--chart-1)"
                                strokeWidth={2}
                                dot={false}
                                type="monotone"
                            />
                            <Line
                                dataKey="rolling_win_rate"
                                name="Rolling Win% (10)"
                                stroke="var(--chart-3)"
                                strokeWidth={1.5}
                                strokeDasharray="5 3"
                                dot={false}
                                type="monotone"
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </ChartCard>

                {/* ROI Over Time */}
                <ChartCard title="ROI % Over Time">
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={data.history ?? []} margin={{ left: 5, right: 10, top: 5, bottom: 0 }}>
                            <CartesianGrid
                                stroke="var(--border)"
                                strokeDasharray="4 4"
                                vertical={false}
                                strokeOpacity={0.4}
                            />
                            <XAxis
                                dataKey="date"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                            />
                            <YAxis
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                unit="%"
                                tickFormatter={(value) => `${value}%`}
                                width={45}
                            />
                            <Tooltip
                                contentStyle={enhancedTooltipStyle}
                                content={({ active, payload, label }) => {
                                    if (!active || !payload?.length) return null;
                                    const value = Number(payload[0].value);
                                    return (
                                        <div style={enhancedTooltipStyle}>
                                            <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                {label}
                                            </p>
                                            <p style={{ margin: '3px 0' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>ROI: </span>
                                                <span style={{ color: value >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                    {value >= 0 ? '+' : ''}{value.toFixed(2)}%
                                                </span>
                                            </p>
                                        </div>
                                    );
                                }}
                            />
                            <ReferenceLine y={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Line
                                dataKey="roi_percentage"
                                name="ROI %"
                                stroke="var(--chart-5)"
                                strokeWidth={2}
                                dot={false}
                                type="monotone"
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </ChartCard>

                {/* Odds Distribution */}
                <ChartCard title="Odds Range — Win Rate by Bucket">
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={data.odds_distribution ?? []} margin={{ left: 5, right: 10, top: 5, bottom: 0 }}>
                            <CartesianGrid
                                stroke="var(--border)"
                                strokeDasharray="4 4"
                                vertical={false}
                                strokeOpacity={0.4}
                            />
                            <XAxis
                                dataKey="range"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                            />
                            <YAxis
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                unit="%"
                                tickFormatter={(value) => `${value}%`}
                                width={45}
                                domain={[0, 100]}
                            />
                            <Tooltip
                                contentStyle={enhancedTooltipStyle}
                                content={({ active, payload }) => {
                                    if (!active || !payload?.length) return null;
                                    const data = payload[0].payload;
                                    return (
                                        <div style={enhancedTooltipStyle}>
                                            <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                {data.range}
                                            </p>
                                            <p style={{ margin: '3px 0' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Win Rate: </span>
                                                <span style={{
                                                    color: data.win_rate >= 50 ? 'var(--win)' : 'var(--loss)',
                                                    fontWeight: 'bold'
                                                }}>
                                                    {data.win_rate.toFixed(1)}%
                                                </span>
                                            </p>
                                            <p style={{ margin: '3px 0' }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Bets: </span>
                                                <span style={{ fontWeight: 'bold' }}>{data.count}</span>
                                            </p>
                                        </div>
                                    );
                                }}
                            />
                            <ReferenceLine y={50} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Bar dataKey="win_rate" name="Win Rate %" radius={[3, 3, 0, 0]}>
                                {(data.odds_distribution ?? []).map((entry, i) => (
                                    <Cell key={i}
                                        fill={entry.win_rate >= 50 ? 'var(--chart-2)' : 'var(--chart-4)'} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </ChartCard>
            </div>

            {/* ── Market Statistics ─────────────────────────────────────────────── */}
            <SectionHeader icon="◎" title="Market Statistics" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">

                {/* P&L by Market */}
                <ChartCard title="Net Profit Contribution by Market">
                    {(
                        <ResponsiveContainer width="100%" height={250}>
                            <BarChart data={data.pnl_by_market} layout="vertical"
                                margin={{ left: 5, right: 20, top: 5, bottom: 0 }}>
                                <CartesianGrid
                                    stroke="var(--border)"
                                    strokeDasharray="4 4"
                                    vertical={false}
                                    strokeOpacity={0.4}
                                />
                                <XAxis
                                    type="number"
                                    tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                    tickLine={false}
                                    unit=" U"
                                    tickFormatter={(value) => `${value} U`}
                                    axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                                />
                                <YAxis
                                    type="category"
                                    dataKey="market"
                                    width={65}
                                    tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                    tickLine={false}
                                    axisLine={false}
                                />
                                <Tooltip
                                    contentStyle={enhancedTooltipStyle}
                                    content={({ active, payload }) => {
                                        if (!active || !payload?.length) return null;
                                        const data = payload[0].payload;
                                        return (
                                            <div style={enhancedTooltipStyle}>
                                                <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                    {data.market}
                                                </p>
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--text-secondary)' }}>Net Profit: </span>
                                                    <span style={{
                                                        color: data.net_profit >= 0 ? 'var(--win)' : 'var(--loss)',
                                                        fontWeight: 'bold'
                                                    }}>
                                                        {data.net_profit >= 0 ? '+' : ''}{data.net_profit.toFixed(2)} U
                                                    </span>
                                                </p>
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--text-secondary)' }}>Won/Lost: </span>
                                                    <span style={{ fontWeight: 'bold' }}>{data.won} / {data.lost}</span>
                                                </p>
                                            </div>
                                        );
                                    }}
                                />
                                <ReferenceLine x={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                                <Bar dataKey="net_profit" name="Net Profit (U)" radius={[0, 3, 3, 0]}>
                                    {data.pnl_by_market.map((entry, i) => (
                                        <Cell key={i}
                                            fill={entry.net_profit >= 0 ? 'var(--chart-2)' : 'var(--chart-4)'} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </ChartCard>

                {/* Market Accuracy (Won vs Lost stacked) */}
                <ChartCard title="Market Accuracy — Won vs Lost">
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={data.market_accuracy ?? []} margin={{ left: 5, right: 10, top: 5, bottom: 0 }}>
                            <CartesianGrid
                                stroke="var(--border)"
                                strokeDasharray="4 4"
                                vertical={false}
                                strokeOpacity={0.4}
                            />
                            <XAxis
                                dataKey="market"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                            />
                            <YAxis
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={(value) => `${value}`}
                            />
                            <Tooltip
                                contentStyle={enhancedTooltipStyle}
                                content={({ active, payload }) => {
                                    if (!active || !payload?.length) return null;
                                    const data = payload[0].payload;
                                    const total = data.won + data.lost;
                                    const accuracy = total > 0 ? (data.won / total * 100).toFixed(1) : '0.0';
                                    return (
                                        <div style={enhancedTooltipStyle}>
                                            <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                {data.market}
                                            </p>
                                            <p style={{ margin: '3px 0' }}>
                                                <span style={{ color: 'var(--chart-2)' }}>●</span>
                                                <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>Won: </span>
                                                <span style={{ fontWeight: 'bold', color: 'var(--win)' }}>{data.won}</span>
                                            </p>
                                            <p style={{ margin: '3px 0' }}>
                                                <span style={{ color: 'var(--chart-4)' }}>●</span>
                                                <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>Lost: </span>
                                                <span style={{ fontWeight: 'bold', color: 'var(--loss)' }}>{data.lost}</span>
                                            </p>
                                            <p style={{ margin: '3px 0', borderTop: '1px solid var(--border)', paddingTop: 4, marginTop: 4 }}>
                                                <span style={{ color: 'var(--text-secondary)' }}>Accuracy: </span>
                                                <span style={{ fontWeight: 'bold', color: parseFloat(accuracy) >= 50 ? 'var(--win)' : 'var(--loss)' }}>
                                                    {accuracy}%
                                                </span>
                                            </p>
                                        </div>
                                    );
                                }}
                            />
                            <Legend wrapperStyle={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }} />
                            <Bar dataKey="won" name="Won" stackId="a" fill="var(--chart-2)" radius={[0, 0, 0, 0]} />
                            <Bar dataKey="lost" name="Lost" stackId="a" fill="var(--chart-4)" radius={[3, 3, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </ChartCard>
            </div>

            {/* ── Correlation ───────────────────────────────────────────────────── */}
            <SectionHeader icon="⬡" title="Correlation Analysis" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">

                {/* Win rate by legs count */}
                <ChartCard title="Win Rate by Number of Legs">
                    {(() => {
                        const byLegs: Record<number, { total: number; won: number }> = {};
                        (data.correlation ?? []).forEach(r => {
                            if (!byLegs[r.legs_count]) byLegs[r.legs_count] = { total: 0, won: 0 };
                            byLegs[r.legs_count].total++;
                            if (r.status === 'Won') byLegs[r.legs_count].won++;
                        });
                        const legsData = Object.entries(byLegs).map(([k, v]) => ({
                            legs: +k, win_rate: Math.round((v.won / v.total) * 100),
                        })).sort((a, b) => a.legs - b.legs);
                        return (
                            <ResponsiveContainer width="100%" height={250}>
                                <BarChart data={legsData} margin={{ left: 5, right: 10, top: 5, bottom: 0 }}>
                                    <CartesianGrid
                                        stroke="var(--border)"
                                        strokeDasharray="4 4"
                                        vertical={false}
                                        strokeOpacity={0.4}
                                    />
                                    <XAxis
                                        dataKey="legs"
                                        tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                        tickLine={false}
                                        axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                                        label={{ value: 'Legs', fill: 'var(--text-secondary)', fontSize: 10, dy: 12 }}
                                    />
                                    <YAxis
                                        tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                        tickLine={false}
                                        axisLine={false}
                                        unit="%"
                                        tickFormatter={(value) => `${value}%`}
                                        width={45}
                                        domain={[0, 100]}
                                    />
                                    <Tooltip
                                        contentStyle={enhancedTooltipStyle}
                                        content={({ active, payload }) => {
                                            if (!active || !payload?.length) return null;
                                            const data = payload[0].payload;
                                            return (
                                                <div style={enhancedTooltipStyle}>
                                                    <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                        {data.legs} Leg{data.legs !== 1 ? 's' : ''}
                                                    </p>
                                                    <p style={{ margin: '3px 0' }}>
                                                        <span style={{ color: 'var(--text-secondary)' }}>Win Rate: </span>
                                                        <span style={{
                                                            color: data.win_rate >= 50 ? 'var(--win)' : 'var(--loss)',
                                                            fontWeight: 'bold'
                                                        }}>
                                                            {data.win_rate}%
                                                        </span>
                                                    </p>
                                                </div>
                                            );
                                        }}
                                    />
                                    <ReferenceLine y={50} stroke="var(--border-strong)" strokeDasharray="4 2" />
                                    <Bar dataKey="win_rate" name="Win Rate %" fill="var(--chart-1)"
                                        radius={[3, 3, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        );
                    })()}
                </ChartCard>

                {/* Profile scatter: avg odds vs win rate */}
                <ChartCard title="Profile — Avg Odds vs Win Rate (bubble = volume)">
                    {(!data.profile_scatter || data.profile_scatter.length === 0) ? (
                        <div className="text-center py-8">
                            <p className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                                No profile data available
                            </p>
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={250}>
                            <ScatterChart margin={{ left: 5, right: 20, top: 5, bottom: 10 }}>
                                <CartesianGrid
                                    stroke="var(--border)"
                                    strokeDasharray="4 4"
                                    strokeOpacity={0.4}
                                />
                                <XAxis
                                    type="number"
                                    dataKey="avg_odds"
                                    name="Avg Odds"
                                    tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                    tickLine={false}
                                    axisLine={{ stroke: 'var(--border)', strokeWidth: 1 }}
                                    label={{ value: 'Avg Odds', fill: 'var(--text-secondary)', fontSize: 10, dy: 14 }}
                                    tickFormatter={(value) => `@${value}`}
                                />
                                <YAxis
                                    type="number"
                                    dataKey="win_rate"
                                    name="Win Rate %"
                                    tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                    tickLine={false}
                                    axisLine={false}
                                    unit="%"
                                    domain={[0, 100]}
                                    tickFormatter={(value) => `${value}%`}
                                    width={45}
                                />
                                <Tooltip
                                    contentStyle={enhancedTooltipStyle}
                                    content={({ active, payload }) => {
                                        if (!active || !payload?.length) return null;
                                        const d = payload[0].payload;
                                        return (
                                            <div style={enhancedTooltipStyle}>
                                                <p style={{ color: 'var(--text-bright)', marginBottom: 6, fontSize: 11, fontWeight: 'bold' }}>
                                                    {d.profile}
                                                </p>
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--text-secondary)' }}>Avg Odds: </span>
                                                    <span style={{ fontWeight: 'bold' }}>@{d.avg_odds.toFixed(2)}</span>
                                                </p>
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--text-secondary)' }}>Win Rate: </span>
                                                    <span style={{
                                                        color: d.win_rate >= 50 ? 'var(--win)' : 'var(--loss)',
                                                        fontWeight: 'bold'
                                                    }}>
                                                        {d.win_rate.toFixed(1)}%
                                                    </span>
                                                </p>
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--text-secondary)' }}>P&L: </span>
                                                    <span style={{
                                                        color: d.net_profit >= 0 ? 'var(--win)' : 'var(--loss)',
                                                        fontWeight: 'bold'
                                                    }}>
                                                        {d.net_profit >= 0 ? '+' : ''}{d.net_profit.toFixed(2)} U
                                                    </span>
                                                </p>
                                                <p style={{ margin: '3px 0' }}>
                                                    <span style={{ color: 'var(--text-secondary)' }}>Volume: </span>
                                                    <span style={{ fontWeight: 'bold' }}>{d.volume}</span>
                                                </p>
                                            </div>
                                        );
                                    }}
                                />
                                <Scatter data={data.profile_scatter}>
                                    {data.profile_scatter.map((entry, i) => (
                                        <Cell key={i}
                                            fill={entry.net_profit >= 0 ? 'var(--chart-2)' : 'var(--chart-4)'}
                                            r={Math.max(4, Math.min(14, entry.volume * 3))} />
                                    ))}
                                </Scatter>
                            </ScatterChart>
                        </ResponsiveContainer>
                    )}
                </ChartCard>
            </div>
        </div>
    );
}
