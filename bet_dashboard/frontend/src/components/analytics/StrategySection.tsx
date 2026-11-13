import AnalyticsSection from './AnalyticsSection';
import QuickviewContainer, { type QuickviewTile } from './QuickviewContainer';
import RollingLineChart from './charts/RollingLineChart';
import type { StrategyMetrics } from '../../utils/analyticsStrategy';

interface StrategySectionProps {
    metrics: StrategyMetrics;
    defaultExpanded?: boolean;
}

export default function StrategySection({
    metrics,
    defaultExpanded = false,
}: StrategySectionProps) {
    const edgeColor = metrics.edge > 0 ? 'var(--win)' : metrics.edge < 0 ? 'var(--loss)' : 'var(--text-bright)';

    const trendColor = metrics.edge_trend === 'growing' ? 'var(--win)'
        : metrics.edge_trend === 'declining' ? 'var(--loss)'
        : 'var(--text-secondary)';
    const trendIcon = metrics.edge_trend === 'growing' ? '↑'
        : metrics.edge_trend === 'declining' ? '↓' : '→';
    const trendLabel = metrics.edge_trend
        ? metrics.edge_trend.charAt(0).toUpperCase() + metrics.edge_trend.slice(1)
        : 'Neutral';

    const tiles: QuickviewTile[] = [
        // 1. Overall Edge (Headline)
        {
            label: 'Overall Edge',
            value: `${metrics.edge > 0 ? '+' : ''}${metrics.edge.toFixed(1)}%`,
            sub: `Actual: ${metrics.win_rate.toFixed(1)}% | Implied: ${metrics.implied_win_rate.toFixed(1)}%`,
            color: edgeColor,
            tip: 'Actual win rate minus market-implied win rate. Positive indicates a beating margin.',
            highlight: true,
            lowSampleWarning: metrics.is_low_sample ? `Low sample (n=${metrics.sample_size})` : null,
        },
        // 2. Edge Trend
        {
            label: 'Edge Trend',
            value: `${trendIcon} ${trendLabel}`,
            sub: `Recent: ${metrics.recent_edge_value > 0 ? '+' : ''}${metrics.recent_edge_value.toFixed(1)}%`,
            color: trendColor,
            tip: 'Trend of your edge over recent windows (14-day). Growing = improving, declining = eroding.',
        },
        // 3. Edge Reliability & Luck vs Skill
        {
            label: 'Edge Reliability',
            value: metrics.variance_z !== null ? `z = ${metrics.variance_z > 0 ? '+' : ''}${metrics.variance_z.toFixed(2)}` : 'n/a',
            sub: metrics.variance_verdict,
            color: metrics.variance_z !== null && metrics.variance_z >= 1.96 ? 'var(--win)' : 'var(--text-bright)',
            tip: 'Binomial test comparing actual wins vs expected wins from market-implied odds.',
        },
        // 4. Staking Discipline (Target Stake)
        {
            label: 'Target Stake',
            value: `${metrics.kelly_suggested_units.toFixed(2)}U`,
            sub: metrics.kelly_ratio !== null ? `${metrics.kelly_ratio}× avg stake${metrics.is_aggressive ? ' (aggressive)' : ''}` : `avg: ${metrics.avg_units.toFixed(2)}U`,
            color: metrics.is_aggressive ? 'var(--pending)' : 'var(--text-bright)',
            tip: 'Suggested stake size based on Kelly Criterion vs actual average stake.',
        },
        // 5. Odds Profile & Consistency
        {
            label: 'Odds Profile',
            value: `@${metrics.avg_odds.toFixed(2)}`,
            sub: metrics.units_std !== null ? `±${metrics.units_std.toFixed(2)}U stake std` : undefined,
            color: 'var(--text-bright)',
            tip: 'Average market odds taken and standard deviation of stake sizing.',
        },
        // 6. Aggregate Prediction Quality
        {
            label: 'Input Accuracy',
            value: metrics.aggregate_sources?.accuracy != null ? `${metrics.aggregate_sources.accuracy.toFixed(1)}%` : 'n/a',
            sub: metrics.aggregate_sources?.score_mae != null ? `${metrics.aggregate_sources.score_mae.toFixed(2)} score MAE` : undefined,
            color: metrics.aggregate_sources?.accuracy != null && metrics.aggregate_sources.accuracy >= 55 ? 'var(--win)' : 'var(--text-bright)',
            tip: 'Aggregate hit-rate and score error across all crawler prediction models combined.',
        },
    ];

    const quickviewFooter = (
        <div className="flex items-center justify-between w-full flex-wrap gap-2">
            <span>Portfolio basis: <strong className="text-[var(--text-bright)]">{metrics.sample_size}</strong> bets evaluated</span>
            <span>Expected wins: <strong className="text-[var(--text-bright)]">{metrics.expected_wins.toFixed(1)}</strong> | Actual wins: <strong style={{ color: metrics.actual_wins >= metrics.expected_wins ? 'var(--win)' : 'var(--loss)' }}>{metrics.actual_wins}</strong></span>
        </div>
    );

    const detailContent = (
        <div className="flex flex-col gap-6">
            {/* Market Efficiency Visual Comparison */}
            <div className="card p-4">
                <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase text-[var(--text-secondary)]">
                        Market Efficiency Bar
                    </span>
                    <span className="font-mono text-xs font-bold" style={{ color: edgeColor }}>
                        Edge: {metrics.edge > 0 ? '+' : ''}{metrics.edge.toFixed(1)}%
                    </span>
                </div>
                <div className="flex flex-col gap-3">
                    <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono w-20 text-[var(--win)] font-bold">Actual Win</span>
                        <div className="flex-1 h-3 rounded-full overflow-hidden" style={{ background: 'var(--bg-raised)' }}>
                            <div
                                className="h-3 rounded-full transition-all duration-300"
                                style={{ width: `${Math.min(100, Math.max(0, metrics.win_rate))}%`, background: 'var(--win)', opacity: 0.8 }}
                            />
                        </div>
                        <span className="text-xs font-mono w-14 text-right font-bold text-[var(--win)]">
                            {metrics.win_rate.toFixed(1)}%
                        </span>
                    </div>
                    <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono w-20 text-[var(--text-secondary)] font-bold">Implied Win</span>
                        <div className="flex-1 h-3 rounded-full overflow-hidden" style={{ background: 'var(--bg-raised)' }}>
                            <div
                                className="h-3 rounded-full transition-all duration-300"
                                style={{ width: `${Math.min(100, Math.max(0, metrics.implied_win_rate))}%`, background: 'var(--text-secondary)', opacity: 0.5 }}
                            />
                        </div>
                        <span className="text-xs font-mono w-14 text-right font-bold text-[var(--text-secondary)]">
                            {metrics.implied_win_rate.toFixed(1)}%
                        </span>
                    </div>
                </div>
            </div>

            {/* Rolling Edge Chart */}
            <div className="card p-4">
                <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase text-[var(--text-secondary)]">
                        Rolling Edge (14-day window)
                    </span>
                    <span className="font-mono text-[10px] text-[var(--text-secondary)]">
                        Beating margin vs market expectation
                    </span>
                </div>
                <RollingLineChart
                    data={metrics.rolling_edge_series.map(s => ({
                        date: s.date,
                        value: s.rolling_edge,
                        sampleSize: s.sample_size,
                    }))}
                    valueKey="value"
                    valueLabel="Edge"
                    unit="%"
                    height={220}
                />
            </div>
        </div>
    );

    return (
        <AnalyticsSection
            title="Strategy"
            icon="◈"
            quickview={
                <QuickviewContainer
                    tiles={tiles}
                    columnsClassName="grid-cols-2 md:grid-cols-3 lg:grid-cols-6"
                    footer={quickviewFooter}
                />
            }
            detail={detailContent}
            defaultExpanded={defaultExpanded}
        />
    );
}
