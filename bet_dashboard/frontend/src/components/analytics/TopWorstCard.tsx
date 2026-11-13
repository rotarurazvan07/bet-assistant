import { TooltipIcon } from '../ui';
import type { RankableItem } from '../../utils/analyticsRetrospection';

interface TopWorstCardProps {
    title: string;
    top: RankableItem[];
    worst: RankableItem[];
    formatName?: (name: string) => string;
    tip?: string;
    emptyMessage?: string;
}

export default function TopWorstCard({
    title,
    top,
    worst,
    formatName = name => name,
    tip = 'Top 3 and Worst 3 performers ranked by edge among items with sufficient legs.',
    emptyMessage = 'not enough data (min legs)',
}: TopWorstCardProps) {
    const hasData = top.length > 0;

    return (
        <div className="card p-4 flex flex-col gap-3">
            <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono tracking-widest uppercase font-bold" style={{ color: 'var(--text-secondary)' }}>
                    {title}
                </span>
                {tip && <TooltipIcon text={tip} align="right" />}
            </div>

            {!hasData ? (
                <div className="py-6 text-center text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {emptyMessage}
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {/* Top 3 */}
                    <div className="rounded-lg p-3 flex flex-col gap-2" style={{ background: 'var(--win-bg)' }}>
                        <div className="flex items-center justify-between">
                            <span className="text-[9px] font-mono tracking-widest uppercase font-bold" style={{ color: 'var(--win)' }}>
                                ↑ Top 3 Edge
                            </span>
                        </div>
                        <div className="flex flex-col gap-1.5">
                            {top.map((item, idx) => {
                                const displayName = formatName(item.name);
                                return (
                                    <div key={item.name || idx} className="flex items-center justify-between gap-2 text-xs font-mono">
                                        <span className="font-bold truncate" style={{ color: 'var(--text-bright)' }}>
                                            {idx + 1}. {displayName}
                                        </span>
                                        <div className="flex items-center gap-1.5 shrink-0">
                                            <span className="font-bold" style={{ color: 'var(--win)' }}>
                                                {item.edge > 0 ? '+' : ''}{item.edge.toFixed(1)}%
                                            </span>
                                            <span className="text-[9px] text-gray-500">
                                                (n={item.legs})
                                            </span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Worst 3 */}
                    <div className="rounded-lg p-3 flex flex-col gap-2" style={{ background: 'var(--loss-bg)' }}>
                        <div className="flex items-center justify-between">
                            <span className="text-[9px] font-mono tracking-widest uppercase font-bold" style={{ color: 'var(--loss)' }}>
                                ↓ Worst 3 Edge
                            </span>
                        </div>
                        {worst.length === 0 ? (
                            <span className="text-[10px] font-mono italic" style={{ color: 'var(--text-secondary)' }}>
                                No eligible worst items
                            </span>
                        ) : (
                            <div className="flex flex-col gap-1.5">
                                {worst.map((item, idx) => {
                                    const displayName = formatName(item.name);
                                    const edgeColor = item.edge > 0 ? 'var(--pending)' : 'var(--loss)';
                                    return (
                                        <div key={item.name || idx} className="flex items-center justify-between gap-2 text-xs font-mono">
                                            <span className="font-bold truncate" style={{ color: 'var(--text-bright)' }}>
                                                {displayName}
                                            </span>
                                            <div className="flex items-center gap-1.5 shrink-0">
                                                <span className="font-bold" style={{ color: edgeColor }}>
                                                    {item.edge > 0 ? '+' : ''}{item.edge.toFixed(1)}%
                                                </span>
                                                <span className="text-[9px] text-gray-500">
                                                    (n={item.legs})
                                                </span>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
