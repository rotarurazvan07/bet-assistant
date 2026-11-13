interface MiniSparklineProps {
    data: number[];
    width?: number | string;
    height?: number;
    strokeColor?: string;
    strokeWidth?: number;
}

export default function MiniSparkline({
    data,
    width = '100%',
    height = 36,
    strokeColor = 'var(--chart-1)',
    strokeWidth = 2,
}: MiniSparklineProps) {
    if (!data || data.length < 2) {
        return (
            <div className="flex items-center justify-center font-mono text-[10px]" style={{ height, color: 'var(--text-secondary)' }}>
                no history
            </div>
        );
    }

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    // High water mark: track cumulative max
    let hwm = -Infinity;
    const hwmPoints: number[] = [];
    for (const v of data) {
        hwm = Math.max(hwm, v);
        hwmPoints.push(hwm);
    }

    const padTop = 3;
    const padBottom = 3;
    const innerHeight = height - padTop - padBottom;
    const n = data.length;

    // SVG coordinates
    const points = data.map((val, i) => {
        const x = (i / (n - 1)) * 100;
        const y = padTop + innerHeight - ((val - min) / range) * innerHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const hwmPath = hwmPoints.map((val, i) => {
        const x = (i / (n - 1)) * 100;
        const y = padTop + innerHeight - ((val - min) / range) * innerHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    return (
        <div className="flex items-center gap-3">
            <span className="text-[9px] font-mono uppercase tracking-wider shrink-0" style={{ color: 'var(--text-secondary)' }}>
                Equity Curve
            </span>
            <div className="flex-1" style={{ height }}>
                <svg
                    viewBox={`0 0 100 ${height}`}
                    preserveAspectRatio="none"
                    style={{ width, height, overflow: 'visible' }}
                >
                    {/* High water mark guideline */}
                    <polyline
                        points={hwmPath}
                        fill="none"
                        stroke="var(--win)"
                        strokeWidth={1}
                        strokeDasharray="2 2"
                        opacity={0.5}
                    />
                    {/* Main curve */}
                    <polyline
                        points={points}
                        fill="none"
                        stroke={strokeColor}
                        strokeWidth={strokeWidth}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    />
                </svg>
            </div>
            <div className="flex items-center gap-2 text-[9px] font-mono shrink-0">
                <span className="flex items-center gap-1" style={{ color: 'var(--win)' }}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--win)' }} /> HWM: {max.toFixed(1)}U
                </span>
            </div>
        </div>
    );
}
