import { useMemo } from 'react';
import {
    ResponsiveContainer, ComposedChart, AreaChart, Area, Line, Bar,
    XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Cell,
} from 'recharts';
import type { HistoryRecord, DrawdownPoint } from '../../../types';

const TT: React.CSSProperties = {
    background: 'var(--bg-card)',
    border: '1px solid var(--border-strong)',
    borderRadius: 8,
    fontSize: 11,
    fontFamily: 'JetBrains Mono, monospace',
    color: 'var(--text-secondary)',
    padding: '10px 14px',
};

function WeekendTick({ x = 0, y = 0, payload, fontSize = 10 }: {
    x?: number; y?: number; payload?: { value: string }; fontSize?: number;
}) {
    const date = new Date(payload?.value ?? '');
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    return (
        <text
            x={x}
            y={y + 12}
            textAnchor="middle"
            style={{
                fontWeight: isWeekend ? 'bold' : 'normal',
                fill: isWeekend ? 'var(--accent)' : 'var(--text-secondary)',
                fontSize,
            }}
        >
            {payload?.value}
        </text>
    );
}

interface EquityDrawdownChartProps {
    history: HistoryRecord[];
    drawdown: DrawdownPoint[];
    height?: number;
}

export default function EquityDrawdownChart({
    history,
    drawdown,
    height = 220,
}: EquityDrawdownChartProps) {
    // Dual-axis 0-aligned domains for Cumulative P&L chart
    const { cumulativeDomain, dailyDomain } = useMemo(() => {
        if (!history.length) return { cumulativeDomain: [-1, 1] as [number, number], dailyDomain: [-1, 1] as [number, number] };
        const cVals = history.map(d => d.cumulative_profit);
        const dVals = history.map(d => d.net_profit);
        let cMin = Math.min(...cVals, 0), cMax = Math.max(...cVals, 0);
        let dMin = Math.min(...dVals, 0), dMax = Math.max(...dVals, 0);
        if (cMax - cMin < 0.1) { cMin = -0.1; cMax = 0.1; }
        if (dMax - dMin < 0.1) { dMin = -0.1; dMax = 0.1; }
        const cRatio = Math.abs(cMin) / (Math.abs(cMin) + cMax);
        const dRatio = Math.abs(dMin) / (Math.abs(dMin) + dMax);
        const targetRatio = Math.max(cRatio, dRatio);
        if (cRatio < targetRatio) cMin = -(cMax * targetRatio / (1 - targetRatio));
        else cMax = Math.abs(cMin) * (1 - targetRatio) / targetRatio;
        if (dRatio < targetRatio) dMin = -(dMax * targetRatio / (1 - targetRatio));
        else dMax = Math.abs(dMin) * (1 - targetRatio) / targetRatio;
        return { cumulativeDomain: [cMin, cMax] as [number, number], dailyDomain: [dMin, dMax] as [number, number] };
    }, [history]);

    const drawdownDomain = useMemo((): [number, number] => {
        if (!drawdown.length) return [-1, 0];
        const minDD = Math.min(...drawdown.map(d => d.drawdown));
        return [minDD, 0];
    }, [drawdown]);

    const formattedHistory = useMemo(() => {
        return history.map(d => ({
            ...d,
            profitPos: Math.max(0, d.cumulative_profit),
            profitNeg: Math.min(0, d.cumulative_profit),
        }));
    }, [history]);

    const maxDD = drawdown.length ? Math.min(...drawdown.map(d => d.drawdown)) : 0;
    const curDD = drawdown.length ? drawdown[drawdown.length - 1].drawdown : 0;
    const lastHistory = history.length ? history[history.length - 1] : null;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Cumulative P&L with Daily Bars */}
            <div className="card p-4">
                <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                        Cumulative Net Profit
                    </span>
                    {lastHistory && (
                        <span className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                            Latest: <span style={{ color: lastHistory.cumulative_profit >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                {lastHistory.cumulative_profit >= 0 ? '+' : ''}{lastHistory.cumulative_profit.toFixed(2)}U
                            </span>
                        </span>
                    )}
                </div>

                {history.length === 0 ? (
                    <div className="flex items-center justify-center font-mono text-xs" style={{ height, color: 'var(--text-secondary)' }}>
                        No history available
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={height}>
                        <ComposedChart data={formattedHistory} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                            <defs>
                                <linearGradient id="pnlPosGrad_shared" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="var(--win)" stopOpacity={0.25} />
                                    <stop offset="100%" stopColor="var(--win)" stopOpacity={0.0} />
                                </linearGradient>
                                <linearGradient id="pnlNegGrad_shared" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="var(--loss)" stopOpacity={0.0} />
                                    <stop offset="100%" stopColor="var(--loss)" stopOpacity={0.25} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                            <XAxis
                                dataKey="date"
                                tick={<WeekendTick fontSize={10} />}
                                tickLine={false}
                                axisLine={{ stroke: 'var(--border)' }}
                            />
                            <YAxis
                                yAxisId="cumulative"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={v => `${Number(v).toFixed(1)}U`}
                                width={48}
                                orientation="left"
                                domain={cumulativeDomain}
                            />
                            <YAxis
                                yAxisId="daily"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={v => `${Number(v).toFixed(1)}U`}
                                width={48}
                                orientation="right"
                                domain={dailyDomain}
                            />
                            <Tooltip
                                contentStyle={TT}
                                content={({ active, payload, label }) => {
                                    if (!active || !payload?.length) return null;
                                    const daily = payload.find(p => p.dataKey === 'net_profit');
                                    const cumulative = payload.find(p => p.dataKey === 'cumulative_profit');
                                    const dailyNum = daily?.value as number | undefined;
                                    const cumulativeNum = cumulative?.value as number | undefined;

                                    return (
                                        <div style={TT}>
                                            <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{label}</p>
                                            {dailyNum != null && (
                                                <p>
                                                    <span style={{ color: 'var(--text-secondary)' }}>Daily: </span>
                                                    <span style={{ color: dailyNum >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                        {dailyNum >= 0 ? '+' : ''}{dailyNum.toFixed(2)}U
                                                    </span>
                                                </p>
                                            )}
                                            {cumulativeNum != null && (
                                                <p>
                                                    <span style={{ color: 'var(--text-secondary)' }}>Cumulative: </span>
                                                    <span style={{ color: cumulativeNum >= 0 ? 'var(--win)' : 'var(--loss)', fontWeight: 'bold' }}>
                                                        {cumulativeNum >= 0 ? '+' : ''}{cumulativeNum.toFixed(2)}U
                                                    </span>
                                                </p>
                                            )}
                                        </div>
                                    );
                                }}
                            />
                            <ReferenceLine y={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Bar yAxisId="daily" dataKey="net_profit" barSize={6} radius={[2, 2, 0, 0]} opacity={0.6}>
                                {history.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.net_profit >= 0 ? 'var(--win)' : 'var(--loss)'} />
                                ))}
                            </Bar>
                            <Area yAxisId="cumulative" dataKey="profitPos" fill="url(#pnlPosGrad_shared)" stroke="none" type="monotone" baseValue={0} />
                            <Area yAxisId="cumulative" dataKey="profitNeg" fill="url(#pnlNegGrad_shared)" stroke="none" type="monotone" baseValue={0} />
                            <Line yAxisId="cumulative" dataKey="cumulative_profit" stroke="var(--chart-1)" strokeWidth={2.5} dot={false} type="monotone" />
                        </ComposedChart>
                    </ResponsiveContainer>
                )}
            </div>

            {/* Bankroll Drawdown */}
            <div className="card p-4">
                <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                        Bankroll Drawdown
                    </span>
                    {drawdown.length > 0 && (
                        <div className="flex gap-3 text-[11px] font-mono">
                            <span style={{ color: 'var(--text-secondary)' }}>
                                Max: <span style={{ color: 'var(--loss)', fontWeight: 'bold' }}>{maxDD.toFixed(2)}U</span>
                            </span>
                            <span style={{ color: 'var(--text-secondary)' }}>
                                Current: <span style={{ color: curDD < 0 ? 'var(--loss)' : 'var(--win)', fontWeight: 'bold' }}>{curDD.toFixed(2)}U</span>
                            </span>
                        </div>
                    )}
                </div>

                {drawdown.length < 2 ? (
                    <div className="flex items-center justify-center font-mono text-xs" style={{ height, color: 'var(--text-secondary)' }}>
                        Not enough history for drawdown analysis.
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={height}>
                        <AreaChart data={drawdown} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                            <defs>
                                <linearGradient id="ddGrad_shared" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--loss)" stopOpacity={0.08} />
                                    <stop offset="95%" stopColor="var(--loss)" stopOpacity={0.35} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} strokeOpacity={0.4} />
                            <XAxis
                                dataKey="date"
                                tick={<WeekendTick fontSize={10} />}
                                tickLine={false}
                                axisLine={{ stroke: 'var(--border)' }}
                            />
                            <YAxis
                                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={v => `${v}U`}
                                width={48}
                                domain={drawdownDomain}
                            />
                            <Tooltip
                                contentStyle={TT}
                                content={({ active, payload, label }) => {
                                    if (!active || !payload?.length) return null;
                                    const d = payload[0]?.payload;
                                    return (
                                        <div style={TT}>
                                            <p style={{ color: 'var(--text-bright)', marginBottom: 4, fontWeight: 'bold' }}>{label}</p>
                                            <p>
                                                <span style={{ color: 'var(--text-secondary)' }}>Drawdown: </span>
                                                <span style={{ color: 'var(--loss)', fontWeight: 'bold' }}>{d.drawdown.toFixed(2)}U</span>
                                            </p>
                                            <p>
                                                <span style={{ color: 'var(--text-secondary)' }}>Peak: </span>
                                                <span style={{ color: 'var(--win)' }}>{d.peak.toFixed(2)}U</span>
                                            </p>
                                        </div>
                                    );
                                }}
                            />
                            <ReferenceLine y={0} stroke="var(--border-strong)" strokeDasharray="4 2" />
                            <Area dataKey="drawdown" stroke="var(--loss)" strokeWidth={2} fill="url(#ddGrad_shared)" dot={false} type="monotone" />
                        </AreaChart>
                    </ResponsiveContainer>
                )}
            </div>
        </div>
    );
}
