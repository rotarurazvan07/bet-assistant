import { useMemo } from 'react';
import {
    ResponsiveContainer, ComposedChart, CartesianGrid, XAxis, YAxis,
    Tooltip, ReferenceLine, Area, Line,
} from 'recharts';

const TT_STYLE: React.CSSProperties = {
    background: 'var(--bg-card)',
    border: '1px solid var(--border-strong)',
    borderRadius: 8,
    fontSize: 11,
    fontFamily: 'JetBrains Mono, monospace',
    color: 'var(--text-secondary)',
    padding: '10px 14px',
};

interface RollingPoint {
    date: string;
    value: number;
    sampleSize?: number;
    [key: string]: unknown;
}

interface RollingLineChartProps {
    data: RollingPoint[];
    valueKey?: string;
    valueLabel?: string;
    unit?: string;
    height?: number;
    zeroLine?: boolean;
}

export default function RollingLineChart({
    data,
    valueKey = 'value',
    valueLabel = 'Value',
    unit = '%',
    height = 240,
    zeroLine = true,
}: RollingLineChartProps) {
    const formattedData = useMemo(() => {
        return data.map(d => {
            const val = Number(d[valueKey] ?? 0);
            return {
                ...d,
                valPos: Math.max(0, val),
                valNeg: Math.min(0, val),
            };
        });
    }, [data, valueKey]);

    const yDomain = useMemo((): [number, number] => {
        if (!data.length) return [-1, 1];
        const vals = data.map(d => Number(d[valueKey] ?? 0));
        const min = Math.min(...vals, 0);
        const max = Math.max(...vals, 0);
        return [min, max];
    }, [data, valueKey]);

    if (data.length < 2) {
        return (
            <div className="flex items-center justify-center font-mono text-xs" style={{ height, color: 'var(--text-secondary)' }}>
                Need more historical data (minimum 2 points).
            </div>
        );
    }

    const gradIdPos = `rollingPosGrad_${valueKey}`;
    const gradIdNeg = `rollingNegGrad_${valueKey}`;

    return (
        <ResponsiveContainer width="100%" height={height}>
            <ComposedChart data={formattedData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                <defs>
                    <linearGradient id={gradIdPos} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--win)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="var(--win)" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id={gradIdNeg} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--loss)" stopOpacity={0.02} />
                        <stop offset="95%" stopColor="var(--loss)" stopOpacity={0.3} />
                    </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                <XAxis
                    dataKey="date"
                    tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                    tickLine={false}
                    axisLine={{ stroke: 'var(--border)' }}
                />
                <YAxis
                    tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={v => `${v}${unit}`}
                    width={48}
                    domain={yDomain}
                />
                <Tooltip
                    contentStyle={TT_STYLE}
                    content={({ active, payload, label }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0]?.payload;
                        const val = d ? Number(d[valueKey] ?? 0) : 0;
                        return (
                            <div style={TT_STYLE}>
                                <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{label}</p>
                                <p>
                                    <span style={{ color: 'var(--text-secondary)' }}>{valueLabel}: </span>
                                    <span style={{ color: val >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                        {val >= 0 ? '+' : ''}{val.toFixed(1)}{unit}
                                    </span>
                                </p>
                                {d?.sampleSize !== undefined && (
                                    <p>
                                        <span style={{ color: 'var(--text-secondary)' }}>Sample: </span>
                                        <span style={{ color: 'var(--text-primary)' }}>n={d.sampleSize}</span>
                                    </p>
                                )}
                            </div>
                        );
                    }}
                />
                {zeroLine && (
                    <ReferenceLine y={0} stroke="rgba(255,255,255,0.4)" strokeDasharray="4 2" strokeWidth={1.5} />
                )}
                <Area dataKey="valPos" fill={`url(#${gradIdPos})`} stroke="none" type="monotone" />
                <Area dataKey="valNeg" fill={`url(#${gradIdNeg})`} stroke="none" type="monotone" />
                <Line
                    dataKey={valueKey}
                    stroke="var(--chart-1)"
                    strokeWidth={2.5}
                    dot={false}
                    type="monotone"
                />
            </ComposedChart>
        </ResponsiveContainer>
    );
}
