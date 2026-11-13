import React from 'react';
import { TooltipIcon } from '../ui';

export interface QuickviewTile {
    id?: string;
    label: string;
    value: string | number | null | undefined;
    sub?: string | React.ReactNode;
    color?: string;
    tip?: string;
    badge?: { text: string; color?: string };
    highlight?: boolean;
    lowSampleWarning?: string | null;
}

interface QuickviewContainerProps {
    tiles: QuickviewTile[];
    columnsClassName?: string;
    footer?: React.ReactNode;
    sparkline?: React.ReactNode;
}

export default function QuickviewContainer({
    tiles,
    columnsClassName = 'grid-cols-2 md:grid-cols-3 lg:grid-cols-6',
    footer,
    sparkline,
}: QuickviewContainerProps) {
    return (
        <div className="card p-4 flex flex-col gap-4">
            <div className={`grid gap-3 ${columnsClassName}`}>
                {tiles.map((tile, idx) => {
                    const displayValue = tile.value === null || tile.value === undefined || Number.isNaN(tile.value)
                        ? 'n/a'
                        : tile.value;

                    return (
                        <div
                            key={tile.id ?? `${tile.label}-${idx}`}
                            className="card px-4 py-3 flex flex-col gap-1 justify-between"
                            style={tile.highlight ? { border: '1px solid var(--border-accent)', background: 'var(--bg-hover)' } : {}}
                        >
                            <div>
                                <div className="flex items-center gap-1 mb-1">
                                    <span
                                        className="text-[10px] font-mono tracking-widest uppercase truncate"
                                        style={{ color: 'var(--text-secondary)' }}
                                    >
                                        {tile.label}
                                    </span>
                                    {tile.tip && <TooltipIcon text={tile.tip} align="center" />}
                                </div>
                                <div className="flex items-baseline gap-2 flex-wrap">
                                    <span
                                        className="font-display font-bold text-xl leading-none"
                                        style={{ color: tile.color ?? 'var(--text-bright)' }}
                                    >
                                        {displayValue}
                                    </span>
                                    {tile.badge && (
                                        <span
                                            className="text-[9px] font-mono tracking-wide uppercase px-1.5 py-0.5 rounded"
                                            style={{
                                                color: tile.badge.color ?? 'var(--accent)',
                                                background: `color-mix(in srgb, ${tile.badge.color ?? 'var(--accent)'} 15%, transparent)`,
                                            }}
                                        >
                                            {tile.badge.text}
                                        </span>
                                    )}
                                </div>
                            </div>

                            {/* Subtext and sample size warning */}
                            <div>
                                {tile.sub && (
                                    <div className="text-[10px] font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>
                                        {tile.sub}
                                    </div>
                                )}
                                {tile.lowSampleWarning && (
                                    <div className="text-[9px] font-mono mt-0.5 italic" style={{ color: 'var(--loss)' }}>
                                        ⚠ {tile.lowSampleWarning}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {sparkline && (
                <div className="pt-2 border-t border-[var(--border)]">
                    {sparkline}
                </div>
            )}

            {footer && (
                <div className="pt-2 border-t border-[var(--border)] flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {footer}
                </div>
            )}
        </div>
    );
}
