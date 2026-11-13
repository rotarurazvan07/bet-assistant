import { useMemo } from 'react';
import {
    ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Cell,
} from 'recharts';
import AnalyticsSection from './AnalyticsSection';
import TopWorstCard from './TopWorstCard';
import IntelligenceContainer, { type IntelligenceColumn } from './IntelligenceContainer';
import CorrelationContainer, { type ViewOption } from './CorrelationContainer';
import { marketLabel } from '../../config/marketConfig';
import {
    filterEligibleItems, rankTopWorst, MIN_SAMPLE_SIZE, type RankableItem,
} from '../../utils/analyticsRetrospection';
import type {
    MarketBreakdown, LeagueBreakdown, SourceBreakdown,
    AnalyticsData, SourceMarketCorrelation,
} from '../../types';

const TT: React.CSSProperties = {
    background: 'var(--bg-card)',
    border: '1px solid var(--border-strong)',
    borderRadius: 8,
    fontSize: 11,
    fontFamily: 'JetBrains Mono, monospace',
    color: 'var(--text-secondary)',
    padding: '10px 14px',
};

interface RetrospectionSectionProps {
    marketBreakdown: MarketBreakdown[];
    leagueBreakdown: LeagueBreakdown[];
    sourceBreakdown?: SourceBreakdown[];
    correlationMatrix?: AnalyticsData['correlation_matrix'];
    sourceMarketCorrelation?: SourceMarketCorrelation;
    defaultExpanded?: boolean;
}

export default function RetrospectionSection({
    marketBreakdown,
    leagueBreakdown,
    sourceBreakdown = [],
    correlationMatrix,
    sourceMarketCorrelation,
    defaultExpanded = false,
}: RetrospectionSectionProps) {
    // ── Quickview Top / Worst ranking ──────────────────────────────────────────

    // Markets
    const marketRankables: RankableItem[] = useMemo(() => {
        return marketBreakdown.map(m => ({
            name: m.market,
            edge: m.edge,
            legs: m.legs,
        }));
    }, [marketBreakdown]);
    const eligibleMarkets = useMemo(() => filterEligibleItems(marketRankables, MIN_SAMPLE_SIZE), [marketRankables]);
    const { top: topMarkets, worst: worstMarkets } = useMemo(() => rankTopWorst(eligibleMarkets, 3), [eligibleMarkets]);

    // Leagues
    const leagueRankables: RankableItem[] = useMemo(() => {
        return leagueBreakdown.map(l => ({
            name: l.league,
            edge: l.edge,
            legs: l.legs,
        }));
    }, [leagueBreakdown]);
    const eligibleLeagues = useMemo(() => filterEligibleItems(leagueRankables, MIN_SAMPLE_SIZE), [leagueRankables]);
    const { top: topLeagues, worst: worstLeagues } = useMemo(() => rankTopWorst(eligibleLeagues, 3), [eligibleLeagues]);

    // Sources
    const sourceRankables: RankableItem[] = useMemo(() => {
        return sourceBreakdown.map(s => {
            const edgeVal = s.edge ?? (s.accuracy - (s.implied_win_rate ?? 50.0));
            return {
                name: s.source,
                edge: Math.round(edgeVal * 10) / 10,
                legs: s.total_predictions,
            };
        });
    }, [sourceBreakdown]);
    const eligibleSources = useMemo(() => filterEligibleItems(sourceRankables, MIN_SAMPLE_SIZE), [sourceRankables]);
    const { top: topSources, worst: worstSources } = useMemo(() => rankTopWorst(eligibleSources, 3), [eligibleSources]);

    // ── Market Columns ─────────────────────────────────────────────────────────
    const marketColumns: IntelligenceColumn<MarketBreakdown>[] = [
        { key: 'legs', label: 'Legs', tip: 'Total settled legs', align: 'left' },
        {
            key: 'win_rate',
            label: 'Win %',
            tip: 'Actual win rate',
            render: row => (
                <span style={{ color: row.win_rate >= 50 ? 'var(--win)' : 'var(--loss)' }}>
                    {row.win_rate}%
                </span>
            ),
        },
        { key: 'implied_win_rate', label: 'Implied %', tip: 'Market-implied win rate', render: row => `${row.implied_win_rate}%` },
        {
            key: 'edge',
            label: 'Edge',
            tip: 'Actual − Implied',
            render: row => {
                const edgeColor = row.edge > 2 ? 'var(--win)' : row.edge > 0 ? 'var(--pending)' : 'var(--loss)';
                const edgeBg = row.edge > 2 ? 'var(--win-bg)' : row.edge > 0 ? 'var(--pending-bg)' : 'var(--loss-bg)';
                return (
                    <span className="font-bold px-2 py-0.5 rounded" style={{ color: edgeColor, background: edgeBg }}>
                        {row.edge > 0 ? '+' : ''}{row.edge}%
                    </span>
                );
            },
        },
        { key: 'avg_odds', label: 'Avg Odds', tip: 'Average leg odds', render: row => `@${row.avg_odds}` },
    ];

    // ── League Columns ─────────────────────────────────────────────────────────
    const leagueColumns: IntelligenceColumn<LeagueBreakdown>[] = [
        { key: 'legs', label: 'Legs', tip: 'Total settled legs', align: 'left' },
        {
            key: 'win_rate',
            label: 'Win %',
            tip: 'Actual win rate',
            render: row => (
                <span style={{ color: row.win_rate >= 50 ? 'var(--win)' : 'var(--loss)' }}>
                    {row.win_rate}%
                </span>
            ),
        },
        { key: 'implied_win_rate', label: 'Implied %', tip: 'Market-implied win rate', render: row => `${row.implied_win_rate}%` },
        {
            key: 'edge',
            label: 'Edge',
            tip: 'Actual − Implied',
            render: row => {
                const edgeColor = row.edge > 2 ? 'var(--win)' : row.edge > 0 ? 'var(--pending)' : 'var(--loss)';
                const edgeBg = row.edge > 2 ? 'var(--win-bg)' : row.edge > 0 ? 'var(--pending-bg)' : 'var(--loss-bg)';
                return (
                    <span className="font-bold px-2 py-0.5 rounded" style={{ color: edgeColor, background: edgeBg }}>
                        {row.edge > 0 ? '+' : ''}{row.edge}%
                    </span>
                );
            },
        },
        { key: 'avg_odds', label: 'Avg Odds', tip: 'Average leg odds', render: row => `@${row.avg_odds}` },
    ];

    // ── Source Columns (Exposing Accuracy & Score Error) ───────────────────────
    const sourceColumns: IntelligenceColumn<SourceBreakdown>[] = [
        { key: 'total_predictions', label: 'Predictions', tip: 'Total predictions made', align: 'left' },
        { key: 'correct_predictions', label: 'Correct', tip: 'Correct predictions', render: row => <span style={{ color: 'var(--win)' }}>{row.correct_predictions}</span> },
        {
            key: 'accuracy',
            label: 'Accuracy %',
            tip: 'Prediction accuracy percentage',
            render: row => {
                const color = row.accuracy >= 60 ? 'var(--win)' : row.accuracy >= 50 ? 'var(--pending)' : 'var(--loss)';
                const bg = row.accuracy >= 60 ? 'var(--win-bg)' : row.accuracy >= 50 ? 'var(--pending-bg)' : 'var(--loss-bg)';
                return (
                    <span className="font-bold px-2 py-0.5 rounded" style={{ color, background: bg }}>
                        {row.accuracy.toFixed(1)}%
                    </span>
                );
            },
        },
        {
            key: 'score_mae',
            label: 'Score MAE',
            tip: 'Mean Absolute Error in predicted goals (lower is better)',
            render: row => {
                const color = row.score_mae <= 1.0 ? 'var(--win)' : row.score_mae <= 2.0 ? 'var(--pending)' : 'var(--loss)';
                const bg = row.score_mae <= 1.0 ? 'var(--win-bg)' : row.score_mae <= 2.0 ? 'var(--pending-bg)' : 'var(--loss-bg)';
                return (
                    <span className="font-bold px-2 py-0.5 rounded" style={{ color, background: bg }}>
                        {row.score_mae.toFixed(2)}
                    </span>
                );
            },
        },
        {
            key: 'edge',
            label: 'Edge %',
            tip: 'Source edge above market implied win rate',
            render: row => {
                const edgeVal = row.edge ?? (row.accuracy - (row.implied_win_rate ?? 50.0));
                const color = edgeVal > 2 ? 'var(--win)' : edgeVal > 0 ? 'var(--pending)' : 'var(--loss)';
                return (
                    <span className="font-bold" style={{ color }}>
                        {edgeVal > 0 ? '+' : ''}{edgeVal.toFixed(1)}%
                    </span>
                );
            },
        },
    ];

    // Source signals (Best & Worst by accuracy and MAE)
    const sourceSignals = useMemo(() => {
        if (!sourceBreakdown || sourceBreakdown.length === 0) return null;
        const eligible = sourceBreakdown.filter(s => s.total_predictions >= MIN_SAMPLE_SIZE);
        const list = eligible.length > 0 ? eligible : sourceBreakdown;
        const bestAccuracy = list.reduce((b, s) => s.accuracy > b.accuracy ? s : b, list[0]);
        const worstAccuracy = list.reduce((w, s) => s.accuracy < w.accuracy ? s : w, list[0]);
        const bestMAE = list.reduce((b, s) => s.score_mae < b.score_mae ? s : b, list[0]);
        const worstMAE = list.reduce((w, s) => s.score_mae > w.score_mae ? s : w, list[0]);
        return { bestAccuracy, worstAccuracy, bestMAE, worstMAE };
    }, [sourceBreakdown]);

    // Correlation Views
    const leagueMarketViews: ViewOption[] = [
        {
            key: 'edge',
            label: 'Edge',
            getValue: cell => cell.edge,
            formatValue: val => `${val > 0 ? '+' : ''}${val.toFixed(1)}%`,
            getColor: val => {
                if (val > 5) return { color: 'var(--win)', bg: 'rgba(0, 200, 100, 0.15)' };
                if (val > 0) return { color: 'var(--win)', bg: 'rgba(0, 200, 100, 0.05)' };
                if (val < -5) return { color: 'var(--loss)', bg: 'rgba(255, 80, 80, 0.15)' };
                return { color: 'var(--loss)', bg: 'rgba(255, 80, 80, 0.05)' };
            },
        },
        {
            key: 'win_rate',
            label: 'Win Rate',
            getValue: cell => cell.win_rate,
            formatValue: val => `${val.toFixed(0)}%`,
            getColor: val => {
                if (val > 65) return { color: 'var(--win)', bg: 'rgba(0, 200, 100, 0.15)' };
                if (val > 50) return { color: 'var(--pending)', bg: 'rgba(255, 170, 0, 0.1)' };
                return { color: 'var(--loss)', bg: 'rgba(255, 80, 80, 0.15)' };
            },
        },
    ];

    const sourceMarketViews: ViewOption[] = [
        {
            key: 'accuracy',
            label: 'Accuracy',
            getValue: cell => cell.accuracy,
            formatValue: val => `${val.toFixed(1)}%`,
            getColor: val => {
                if (val >= 60) return { color: 'var(--win)', bg: 'rgba(0, 200, 100, 0.15)' };
                if (val >= 50) return { color: 'var(--pending)', bg: 'rgba(255, 170, 0, 0.1)' };
                return { color: 'var(--loss)', bg: 'rgba(255, 80, 80, 0.15)' };
            },
        },
    ];

    const quickviewContent = (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <TopWorstCard
                title="Markets"
                top={topMarkets}
                worst={worstMarkets}
                formatName={marketLabel}
                tip="Top and Worst markets ranked by edge among those with >= 10 legs."
            />
            <TopWorstCard
                title="Leagues"
                top={topLeagues}
                worst={worstLeagues}
                tip="Top and Worst leagues ranked by edge among those with >= 10 legs."
            />
            <TopWorstCard
                title="Sources"
                top={topSources}
                worst={worstSources}
                tip="Top and Worst prediction crawlers ranked by edge among those with >= 10 legs."
            />
        </div>
    );

    const detailContent = (
        <div className="flex flex-col gap-8">
            {/* 1. Market Intelligence */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2">
                    <IntelligenceContainer
                        title="Market Breakdown"
                        tip="Per-market statistics with edge (actual − implied). Greyed rows have < 10 legs."
                        data={marketBreakdown}
                        columns={marketColumns}
                        dimensionKey="market"
                        dimensionLabel="Market"
                        formatDimensionValue={val => marketLabel(String(val))}
                        defaultSortKey="edge"
                        legsKey="legs"
                    />
                </div>
                <div className="card p-4 flex flex-col h-full">
                    <span className="font-mono text-[11px] tracking-widest uppercase mb-4 text-[var(--text-secondary)]">
                        Edge by Market
                    </span>
                    <div className="flex-1 min-h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                                data={[...marketBreakdown].sort((a, b) => b.edge - a.edge)}
                                layout="vertical"
                                margin={{ left: 0, right: 30, top: 5, bottom: 0 }}
                            >
                                <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                                <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false} tickFormatter={v => `${v}%`} axisLine={{ stroke: 'var(--border)' }} />
                                <YAxis type="category" dataKey="market" width={70} tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => marketLabel(String(v))} />
                                <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                    if (!active || !payload?.length) return null;
                                    const d = payload[0]?.payload;
                                    return (
                                        <div style={TT}>
                                            <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>{marketLabel(d.market)}</p>
                                            <p><span style={{ color: 'var(--text-secondary)' }}>Edge: </span><span style={{ color: d.edge >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>{d.edge >= 0 ? '+' : ''}{d.edge}%</span></p>
                                            <p><span style={{ color: 'var(--text-secondary)' }}>Legs: </span><span style={{ color: 'var(--text-primary)' }}>{d.legs}</span></p>
                                        </div>
                                    );
                                }} />
                                <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" />
                                <Bar dataKey="edge" radius={[0, 3, 3, 0]}>
                                    {[...marketBreakdown].sort((a, b) => b.edge - a.edge).map((entry, i) => (
                                        <Cell key={i} fill={entry.edge >= 0 ? 'var(--win)' : 'var(--loss)'} fillOpacity={entry.legs < MIN_SAMPLE_SIZE ? 0.25 : 0.8} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* 2. League Intelligence */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2">
                    <IntelligenceContainer
                        title="League Breakdown"
                        tip="Per-league hit-rate and value analysis. Greyed rows have < 10 legs."
                        data={leagueBreakdown}
                        columns={leagueColumns}
                        dimensionKey="league"
                        dimensionLabel="League"
                        defaultSortKey="edge"
                        legsKey="legs"
                    />
                </div>
                <div className="card p-4 flex flex-col h-full">
                    <span className="font-mono text-[11px] tracking-widest uppercase mb-4 text-[var(--text-secondary)]">
                        Edge by League
                    </span>
                    <div className="flex-1 min-h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                                data={[...leagueBreakdown].sort((a, b) => b.edge - a.edge)}
                                layout="vertical"
                                margin={{ left: 0, right: 30, top: 5, bottom: 0 }}
                            >
                                <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                                <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false} tickFormatter={v => `${v}%`} axisLine={{ stroke: 'var(--border)' }} />
                                <YAxis type="category" dataKey="league" width={80} tick={{ fill: 'var(--text-secondary)', fontSize: 9 }} tickLine={false} axisLine={false} />
                                <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                    if (!active || !payload?.length) return null;
                                    const d = payload[0]?.payload;
                                    return (
                                        <div style={TT}>
                                            <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>{d.league}</p>
                                            <p><span style={{ color: 'var(--text-secondary)' }}>Edge: </span><span style={{ color: d.edge >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>{d.edge >= 0 ? '+' : ''}{d.edge}%</span></p>
                                            <p><span style={{ color: 'var(--text-secondary)' }}>Legs: </span><span style={{ color: 'var(--text-primary)' }}>{d.legs}</span></p>
                                        </div>
                                    );
                                }} />
                                <ReferenceLine x={0} stroke="rgba(255,255,255,0.3)" />
                                <Bar dataKey="edge" radius={[0, 3, 3, 0]}>
                                    {[...leagueBreakdown].sort((a, b) => b.edge - a.edge).map((entry, i) => (
                                        <Cell key={i} fill={entry.edge >= 0 ? 'var(--win)' : 'var(--loss)'} fillOpacity={entry.legs < MIN_SAMPLE_SIZE ? 0.25 : 0.8} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* 3. Source Intelligence (Table, Chart, Highlights) */}
            {sourceBreakdown.length > 0 && (
                <div className="flex flex-col gap-4">
                    {/* Source Highlights */}
                    {sourceSignals && (
                        <div className="card p-4">
                            <span className="font-mono text-[11px] tracking-widest uppercase mb-4 block text-[var(--text-secondary)]">
                                Source Signals & Model Reliability
                            </span>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                <div className="rounded-lg p-3 flex flex-col gap-1" style={{ background: 'var(--win-bg)' }}>
                                    <span className="text-[9px] font-mono tracking-widest uppercase font-bold" style={{ color: 'var(--win)' }}>↑ Best Accuracy</span>
                                    <span className="font-display font-bold text-lg leading-none" style={{ color: 'var(--text-bright)' }}>{sourceSignals.bestAccuracy.source}</span>
                                    <span className="text-[11px] font-mono font-bold" style={{ color: 'var(--win)' }}>+{sourceSignals.bestAccuracy.accuracy.toFixed(1)}%</span>
                                    <span className="text-[9px] font-mono text-gray-500">{sourceSignals.bestAccuracy.correct_predictions}/{sourceSignals.bestAccuracy.total_predictions} correct</span>
                                </div>
                                <div className="rounded-lg p-3 flex flex-col gap-1" style={{ background: 'var(--loss-bg)' }}>
                                    <span className="text-[9px] font-mono tracking-widest uppercase font-bold" style={{ color: 'var(--loss)' }}>↓ Worst Accuracy</span>
                                    <span className="font-display font-bold text-lg leading-none" style={{ color: 'var(--text-bright)' }}>{sourceSignals.worstAccuracy.source}</span>
                                    <span className="text-[11px] font-mono font-bold" style={{ color: 'var(--loss)' }}>{sourceSignals.worstAccuracy.accuracy.toFixed(1)}%</span>
                                    <span className="text-[9px] font-mono text-gray-500">{sourceSignals.worstAccuracy.correct_predictions}/{sourceSignals.worstAccuracy.total_predictions} correct</span>
                                </div>
                                <div className="rounded-lg p-3 flex flex-col gap-1" style={{ background: 'var(--win-bg)' }}>
                                    <span className="text-[9px] font-mono tracking-widest uppercase font-bold" style={{ color: 'var(--win)' }}>↑ Best Score MAE</span>
                                    <span className="font-display font-bold text-lg leading-none" style={{ color: 'var(--text-bright)' }}>{sourceSignals.bestMAE.source}</span>
                                    <span className="text-[11px] font-mono font-bold" style={{ color: 'var(--win)' }}>{sourceSignals.bestMAE.score_mae.toFixed(2)} MAE</span>
                                    <span className="text-[9px] font-mono text-gray-500">{sourceSignals.bestMAE.total_predictions} predictions</span>
                                </div>
                                <div className="rounded-lg p-3 flex flex-col gap-1" style={{ background: 'var(--loss-bg)' }}>
                                    <span className="text-[9px] font-mono tracking-widest uppercase font-bold" style={{ color: 'var(--loss)' }}>↓ Worst Score MAE</span>
                                    <span className="font-display font-bold text-lg leading-none" style={{ color: 'var(--text-bright)' }}>{sourceSignals.worstMAE.source}</span>
                                    <span className="text-[11px] font-mono font-bold" style={{ color: 'var(--loss)' }}>{sourceSignals.worstMAE.score_mae.toFixed(2)} MAE</span>
                                    <span className="text-[9px] font-mono text-gray-500">{sourceSignals.worstMAE.total_predictions} predictions</span>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <div className="lg:col-span-2">
                            <IntelligenceContainer
                                title="Source Breakdown"
                                tip="Per-source prediction stats exposing accuracy, score error (MAE), and edge."
                                data={sourceBreakdown}
                                columns={sourceColumns}
                                dimensionKey="source"
                                dimensionLabel="Source"
                                defaultSortKey="accuracy"
                                legsKey="total_predictions"
                            />
                        </div>
                        <div className="card p-4 flex flex-col h-full">
                            <span className="font-mono text-[11px] tracking-widest uppercase mb-4 text-[var(--text-secondary)]">
                                Accuracy by Source
                            </span>
                            <div className="flex-1 min-h-[300px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart
                                        data={[...sourceBreakdown].sort((a, b) => b.accuracy - a.accuracy)}
                                        layout="vertical"
                                        margin={{ left: 0, right: 30, top: 5, bottom: 0 }}
                                    >
                                        <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                                        <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false} tickFormatter={v => `${v}%`} axisLine={{ stroke: 'var(--border)' }} />
                                        <YAxis type="category" dataKey="source" width={110} tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} tickLine={false} axisLine={false} />
                                        <Tooltip contentStyle={TT} content={({ active, payload }) => {
                                            if (!active || !payload?.length) return null;
                                            const d = payload[0]?.payload;
                                            return (
                                                <div style={TT}>
                                                    <p style={{ color: 'var(--text-bright)', fontWeight: 'bold', marginBottom: 4 }}>{d.source}</p>
                                                    <p><span style={{ color: 'var(--text-secondary)' }}>Accuracy: </span><span style={{ color: d.accuracy >= 55 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>{d.accuracy.toFixed(1)}%</span></p>
                                                    <p><span style={{ color: 'var(--text-secondary)' }}>MAE: </span><span style={{ color: 'var(--text-primary)' }}>{d.score_mae.toFixed(2)}</span></p>
                                                    <p><span style={{ color: 'var(--text-secondary)' }}>Predictions: </span><span style={{ color: 'var(--text-primary)' }}>{d.total_predictions}</span></p>
                                                </div>
                                            );
                                        }} />
                                        <ReferenceLine x={50} stroke="rgba(255,255,255,0.3)" />
                                        <Bar dataKey="accuracy" radius={[0, 3, 3, 0]}>
                                            {[...sourceBreakdown].sort((a, b) => b.accuracy - a.accuracy).map((entry, i) => (
                                                <Cell key={i} fill={entry.accuracy >= 60 ? 'var(--win)' : entry.accuracy >= 50 ? 'var(--pending)' : 'var(--loss)'} fillOpacity={entry.total_predictions < MIN_SAMPLE_SIZE ? 0.25 : 0.8} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* 4. Intersectional Correlation Matrices */}
            {correlationMatrix && correlationMatrix.leagues.length > 0 && correlationMatrix.markets.length > 0 && (
                <CorrelationContainer
                    title="League x Market Correlation"
                    tip="Cross-tabulation of performance across league and market intersections. Heatmap colors: Green = High, Red = Low."
                    rowLabel="League"
                    colLabel="Market"
                    rows={correlationMatrix.leagues}
                    cols={correlationMatrix.markets}
                    formatColumnLabel={marketLabel}
                    matrix={correlationMatrix.matrix}
                    views={leagueMarketViews}
                />
            )}

            {sourceMarketCorrelation && sourceMarketCorrelation.sources.length > 0 && sourceMarketCorrelation.markets.length > 0 && (
                <CorrelationContainer
                    title="Source x Market Type Correlation"
                    tip="Cross-tabulation of prediction accuracy across sources and market types."
                    rowLabel="Source"
                    colLabel="Market Type"
                    rows={sourceMarketCorrelation.sources}
                    cols={sourceMarketCorrelation.markets}
                    matrix={sourceMarketCorrelation.matrix}
                    views={sourceMarketViews}
                />
            )}
        </div>
    );

    return (
        <AnalyticsSection
            title="Retrospection"
            icon="◎"
            quickview={quickviewContent}
            detail={detailContent}
            defaultExpanded={defaultExpanded}
        />
    );
}
