import { useState } from 'react';
import { marketLabel } from '../../config/marketConfig';
import type { AnalyticsInsight } from '../../types';

const PREVIEW_SIZE = 3;

const PRIORITIES: Array<{ key: AnalyticsInsight['priority']; label: string; color: string }> = [
    { key: 'high', label: 'High priority', color: 'var(--accent)' },
    { key: 'medium', label: 'Medium priority', color: 'var(--pending)' },
    { key: 'watch', label: 'Watch', color: 'var(--text-secondary)' },
];

function subject(insight: AnalyticsInsight): string {
    const { target } = insight;
    if (target.section === 'source') return target.source ?? 'Unknown source';
    if (target.section === 'league') return target.league ?? 'Unknown league';
    return marketLabel(target.market ?? '');
}

function action(insight: AnalyticsInsight): string {
    if (insight.priority === 'watch') return `Monitor ${subject(insight)}`;
    if (insight.direction === 'opportunity') return `Prioritize ${subject(insight)}`;
    return insight.target.section === 'source' ? `Avoid ${subject(insight)}` : `Reduce ${subject(insight)}`;
}

export default function InsightsSection({ insights }: { insights: AnalyticsInsight[] }) {
    const [expanded, setExpanded] = useState<Partial<Record<AnalyticsInsight['priority'], boolean>>>({});

    if (!insights.length) return null;

    return (
        <section className="mb-10" aria-label="Actionable insights">
            <div className="flex items-baseline gap-3 mb-4">
                <h2 className="font-display font-bold text-lg" style={{ color: 'var(--text-bright)' }}>Actionable insights</h2>
                <span className="font-mono text-[10px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                    Based on settled results
                </span>
            </div>
            <div className="flex flex-col gap-5">
                {PRIORITIES.map(group => {
                    const groupInsights = insights.filter(insight => insight.priority === group.key);
                    if (!groupInsights.length) return null;
                    const isExpanded = expanded[group.key] ?? false;
                    const visibleInsights = isExpanded ? groupInsights : groupInsights.slice(0, PREVIEW_SIZE);
                    const hiddenCount = groupInsights.length - PREVIEW_SIZE;
                    return (
                        <div key={group.key}>
                            <div className="flex items-center gap-2 mb-2">
                                <span className="h-2 w-2 rounded-full" style={{ background: group.color }} />
                                <h3 className="font-mono text-[11px] tracking-widest uppercase" style={{ color: group.color }}>{group.label}</h3>
                                <span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>({groupInsights.length})</span>
                            </div>
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                                {visibleInsights.map(insight => {
                                    const color = insight.direction === 'opportunity' ? 'var(--win)' : 'var(--loss)';
                                    const background = insight.direction === 'opportunity' ? 'var(--win-bg)' : 'var(--loss-bg)';
                                    return (
                                        <article key={insight.id} className="card p-4 flex flex-col gap-3" style={{ borderLeft: `3px solid ${color}` }}>
                                            <div className="flex items-start justify-between gap-3">
                                                <h4 className="font-semibold text-sm" style={{ color: 'var(--text-bright)' }}>{action(insight)}</h4>
                                                <span className="shrink-0 rounded px-2 py-0.5 font-mono text-[9px] uppercase" style={{ color, background }}>
                                                    {insight.confidence} confidence
                                                </span>
                                            </div>
                                            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                                {insight.edge > 0 ? '+' : ''}{insight.edge.toFixed(1)}% edge: {insight.win_rate.toFixed(1)}% win rate versus {insight.implied_win_rate.toFixed(1)}% implied (n={insight.sample_size}).
                                            </p>
                                        </article>
                                    );
                                })}
                            </div>
                            {hiddenCount > 0 && (
                                <button
                                    type="button"
                                    className="mt-3 font-mono text-[11px] transition-colors"
                                    style={{ color: 'var(--accent)' }}
                                    onClick={() => setExpanded(current => ({ ...current, [group.key]: !isExpanded }))}
                                >
                                    {isExpanded ? 'Show less' : `View ${hiddenCount} more`}
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </section>
    );
}
