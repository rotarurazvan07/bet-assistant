import { useMemo, useState } from 'react';
import { TooltipIcon } from '../ui';
import { INTERSECTION_MIN_SAMPLE_SIZE } from '../../utils/analyticsRetrospection';

export interface CorrelationCell {
    total?: number;
    edge?: number;
    win_rate?: number;
    accuracy?: number;
    [key: string]: unknown;
}

export interface ViewOption {
    key: string;
    label: string;
    getValue: (cell: CorrelationCell) => number;
    formatValue: (val: number, cell: CorrelationCell) => string;
    getColor: (val: number, cell: CorrelationCell) => { color: string; bg: string };
}

interface CorrelationContainerProps {
    title: string;
    tip?: string;
    rowLabel: string;
    colLabel: string;
    rows: string[];
    cols: string[];
    formatColumnLabel?: (column: string) => string;
    matrix: Record<string, Record<string, CorrelationCell>>;
    views?: ViewOption[];
    minSampleSize?: number;
    emptyText?: string;
}

export default function CorrelationContainer({
    title,
    tip,
    rowLabel,
    colLabel,
    rows,
    cols,
    formatColumnLabel,
    matrix,
    views,
    minSampleSize = INTERSECTION_MIN_SAMPLE_SIZE,
    emptyText = 'No correlation data available.',
}: CorrelationContainerProps) {
    const defaultView = views && views.length > 0 ? views[0].key : '';
    const [activeViewKey, setActiveViewKey] = useState<string>(defaultView);
    const [sortCol, setSortCol] = useState<string | null>(null);
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

    const handleSort = (col: string) => {
        if (col === sortCol) {
            setSortDir(d => (d === 'desc' ? 'asc' : 'desc'));
        } else {
            setSortCol(col);
            setSortDir('desc');
        }
    };

    const activeView = views?.find(v => v.key === activeViewKey) ?? views?.[0];

    // Sort rows by the value in the clicked column. Rows whose cell has a
    // sufficient sample always rank ahead of low-sample (grayed-out) rows;
    // each group is sorted by the percentage value, low-sample rows last.
    // Columns always keep their original order.
    const sortedRows = useMemo(() => {
        if (!sortCol || !activeView) return rows;
        const cellInfo = (r: string) => {
            const cell = matrix[r]?.[sortCol];
            if (!cell || (cell.total !== undefined && cell.total === 0)) return null;
            return { value: activeView.getValue(cell), lowSample: (cell.total ?? 0) < minSampleSize };
        };
        const cmp = (a: string, b: string) => {
            const va = cellInfo(a);
            const vb = cellInfo(b);
            if (!va && !vb) return a.localeCompare(b);
            if (!va) return 1;
            if (!vb) return -1;
            if (va.lowSample !== vb.lowSample) return va.lowSample ? 1 : -1;
            return sortDir === 'desc' ? vb.value - va.value : va.value - vb.value;
        };
        return [...rows].sort(cmp);
    }, [rows, matrix, sortCol, sortDir, activeView, minSampleSize]);

    if (!rows.length || !cols.length) {
        return (
            <div className="card p-4">
                <div className="flex items-center gap-2 mb-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                        {title}
                    </span>
                    {tip && <TooltipIcon text={tip} align="right" />}
                </div>
                <p className="font-mono text-xs text-center py-8" style={{ color: 'var(--text-secondary)' }}>
                    {emptyText}
                </p>
            </div>
        );
    }

    return (
        <div className="card p-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
                <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                        {title}
                    </span>
                    {tip && <TooltipIcon text={tip} align="right" />}
                </div>

                {views && views.length > 1 && (
                    <div className="flex bg-black/20 p-1 rounded-lg border border-white/5">
                        {views.map(v => (
                            <button
                                key={v.key}
                                type="button"
                                className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase transition-all ${activeViewKey === v.key ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                                onClick={() => setActiveViewKey(v.key)}
                            >
                                {v.label}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <div className="overflow-x-auto rounded-xl border border-white/5">
                <table className="w-full border-collapse">
                    <thead>
                        <tr className="bg-white/5 border-b border-white/10">
                            <th className="p-3 text-left bg-black/20 sticky left-0 z-10 min-w-[130px]">
                                <span className="text-[9px] font-mono uppercase text-gray-500">
                                    {rowLabel} \ {colLabel}
                                </span>
                            </th>
                            {cols.map(c => {
                                const isSorted = sortCol === c;
                                return (
                                    <th
                                        key={c}
                                        className="p-3 text-center min-w-[80px] cursor-pointer select-none hover:bg-white/5 transition-colors"
                                        onClick={() => handleSort(c)}
                                        title={`Sort by ${formatColumnLabel?.(c) ?? c}`}
                                    >
                                        <span
                                            className="text-[9px] font-mono uppercase inline-flex items-center gap-1"
                                            style={{ color: isSorted ? 'var(--accent)' : 'var(--text-secondary)' }}
                                        >
                                            {formatColumnLabel?.(c) ?? c}
                                            {isSorted && (
                                                <span style={{ color: 'var(--accent)', fontSize: 9 }}>
                                                    {sortDir === 'desc' ? '↓' : '↑'}
                                                </span>
                                            )}
                                        </span>
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {sortedRows.map(r => (
                            <tr key={r} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                                <td className="p-3 bg-black/20 sticky left-0 z-10 border-r border-white/5">
                                    <span className="text-[11px] font-bold text-gray-300">
                                        {r}
                                    </span>
                                </td>
                                {cols.map(c => {
                                    const cell = matrix[r]?.[c];
                                    if (!cell || (cell.total !== undefined && cell.total === 0)) {
                                        return <td key={c} className="p-3 text-center text-gray-700 text-[10px]">—</td>;
                                    }

                                    const total = cell.total ?? 0;
                                    const cellLowSample = total < minSampleSize;

                                    let label = '—';
                                    let style = { color: 'var(--text-secondary)', bg: 'transparent' };

                                    if (activeView) {
                                        const val = activeView.getValue(cell);
                                        label = activeView.formatValue(val, cell);
                                        style = activeView.getColor(val, cell);
                                    }

                                    return (
                                        <td
                                            key={c}
                                            className="p-2 text-center"
                                            style={{
                                                backgroundColor: style.bg,
                                                opacity: cellLowSample ? 0.35 : 1,
                                                filter: cellLowSample ? 'grayscale(80%)' : 'none',
                                            }}
                                            title={cellLowSample ? `Low sample (n=${total})` : undefined}
                                        >
                                            <div className="flex flex-col items-center">
                                                <span className="text-[11px] font-mono font-bold" style={{ color: style.color }}>
                                                    {label}
                                                </span>
                                                <span className="text-[8px] font-mono text-gray-500 mt-0.5">
                                                    n={total}
                                                </span>
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
