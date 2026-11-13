import React, { useState, useMemo } from 'react';
import { TooltipIcon } from '../ui';
import { MIN_SAMPLE_SIZE } from '../../utils/analyticsRetrospection';

export interface IntelligenceColumn<T> {
    key: keyof T;
    label: string;
    tip?: string;
    align?: 'left' | 'right' | 'center';
    render?: (row: T, index: number) => React.ReactNode;
    sortAccessor?: (row: T) => number | string;
    sortable?: boolean;
}

interface IntelligenceContainerProps<T extends object> {
    title: string;
    tip?: string;
    data: T[];
    columns: IntelligenceColumn<T>[];
    dimensionKey: keyof T;
    dimensionLabel: string;
    formatDimensionValue?: (value: unknown) => React.ReactNode;
    defaultSortKey?: string;
    defaultSortDir?: 'asc' | 'desc';
    minSampleSize?: number;
    legsKey?: string;
    emptyText?: string;
}

export default function IntelligenceContainer<T extends object>({
    title,
    tip,
    data,
    columns,
    dimensionKey,
    dimensionLabel,
    formatDimensionValue = val => String(val ?? ''),
    defaultSortKey,
    defaultSortDir = 'desc',
    minSampleSize = MIN_SAMPLE_SIZE,
    legsKey = 'legs',
    emptyText = 'No data available yet.',
}: IntelligenceContainerProps<T>) {
    const initialSortKey = defaultSortKey ?? (columns[0]?.key as string) ?? String(dimensionKey);
    const [sortKey, setSortKey] = useState<string>(initialSortKey);
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>(defaultSortDir);

    const handleSort = (k: string) => {
        if (k === sortKey) {
            setSortDir(d => d === 'desc' ? 'asc' : 'desc');
        } else {
            setSortKey(k);
            setSortDir('desc');
        }
    };

    const sortedData = useMemo(() => {
        if (!data || data.length === 0) return [];

        const col = columns.find(c => String(c.key) === sortKey);
        const accessor = col?.sortAccessor ?? (col
            ? (row: T) => Reflect.get(row, String(col.key))
            : (row: T) => Reflect.get(row, String(dimensionKey)));

        // Separate sufficient sample from low sample (sufficient first)
        const sufficient: T[] = [];
        const insufficient: T[] = [];

        for (const row of data) {
            const legs = Number(Reflect.get(row, legsKey) ?? 0);
            if (legs >= minSampleSize) {
                sufficient.push(row);
            } else {
                insufficient.push(row);
            }
        }

        const comparator = (a: T, b: T) => {
            const va = accessor(a);
            const vb = accessor(b);
            if (typeof va === 'number' && typeof vb === 'number') {
                return sortDir === 'desc' ? vb - va : va - vb;
            }
            const sa = String(va ?? '');
            const sb = String(vb ?? '');
            return sortDir === 'desc' ? sb.localeCompare(sa) : sa.localeCompare(sb);
        };

        return [...sufficient.sort(comparator), ...insufficient.sort(comparator)];
    }, [data, sortKey, sortDir, columns, dimensionKey, legsKey, minSampleSize]);

    return (
        <div className="card p-4 h-full flex flex-col">
            <div className="flex items-center gap-2 mb-4">
                <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                    {title}
                </span>
                {tip && <TooltipIcon text={tip} align="right" />}
            </div>

            <div className="flex-1 overflow-x-auto rounded-xl border border-[var(--border)] max-h-[500px]">
                {sortedData.length === 0 ? (
                    <div className="p-8 text-center text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                        {emptyText}
                    </div>
                ) : (
                    <table className="w-full" style={{ borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-raised)' }}>
                                {/* Dimension Column */}
                                <th
                                    className="px-4 py-3 text-left cursor-pointer select-none"
                                    onClick={() => handleSort(String(dimensionKey))}
                                >
                                    <div className="flex items-center gap-1">
                                        <span
                                            className="text-[10px] font-mono tracking-widest uppercase"
                                            style={{ color: sortKey === String(dimensionKey) ? 'var(--accent)' : 'var(--text-secondary)' }}
                                        >
                                            {dimensionLabel}
                                        </span>
                                        {sortKey === String(dimensionKey) && (
                                            <span style={{ color: 'var(--accent)', fontSize: 10 }}>
                                                {sortDir === 'desc' ? '↓' : '↑'}
                                            </span>
                                        )}
                                    </div>
                                </th>

                                {/* Other Columns */}
                                {columns.map(col => {
                                    const colKey = String(col.key);
                                    const isSorted = sortKey === colKey;
                                    const canSort = col.sortable !== false;
                                    return (
                                        <th
                                            key={colKey}
                                            className={`px-4 py-3 select-none ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'} ${canSort ? 'cursor-pointer' : ''}`}
                                            onClick={() => canSort && handleSort(colKey)}
                                        >
                                            <div className={`flex items-center gap-1 ${col.align === 'right' ? 'justify-end' : col.align === 'center' ? 'justify-center' : 'justify-start'}`}>
                                                <span
                                                    className="text-[10px] font-mono tracking-widest uppercase"
                                                    style={{ color: isSorted ? 'var(--accent)' : 'var(--text-secondary)' }}
                                                >
                                                    {col.label}
                                                </span>
                                                {col.tip && <TooltipIcon text={col.tip} align="center" />}
                                                {isSorted && (
                                                    <span style={{ color: 'var(--accent)', fontSize: 10 }}>
                                                        {sortDir === 'desc' ? '↓' : '↑'}
                                                    </span>
                                                )}
                                            </div>
                                        </th>
                                    );
                                })}
                            </tr>
                        </thead>
                        <tbody>
                            {sortedData.map((row, i) => {
                                const legs = Number(Reflect.get(row, legsKey) ?? 0);
                                const lowSample = legs < minSampleSize;

                                return (
                                    <tr
                                        key={String(Reflect.get(row, String(dimensionKey)) ?? i)}
                                        style={{
                                            borderBottom: '1px solid var(--border)',
                                            background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                                            opacity: lowSample ? 0.4 : 1,
                                            filter: lowSample ? 'grayscale(80%)' : 'none',
                                            fontStyle: lowSample ? 'italic' : 'normal',
                                        }}
                                        title={lowSample ? `Low sample size (n=${legs})` : undefined}
                                    >
                                        <td className="px-4 py-3">
                                            <span className="font-mono font-bold text-sm" style={{ color: 'var(--text-bright)' }}>
                                                {formatDimensionValue(Reflect.get(row, String(dimensionKey)))}
                                            </span>
                                        </td>
                                        {columns.map(col => {
                                            const colKey = String(col.key);
                                            const content = col.render ? col.render(row, i) : String(Reflect.get(row, String(col.key)) ?? '');
                                            return (
                                                <td
                                                    key={colKey}
                                                    className={`px-4 py-3 font-mono text-sm ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'}`}
                                                >
                                                    {content}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
