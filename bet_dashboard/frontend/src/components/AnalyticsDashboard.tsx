import { useMemo } from 'react';
import {
    RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
    Radar, ResponsiveContainer
} from 'recharts';
import { TooltipIcon } from './ui';
import { BaseCard } from './ui/BaseCard';
import type { CandidateLeg } from '../types';
import {
    calculateRiskScore,
    calculateWinProbability,
    calculateDiversityScore,
    getRiskLabel
} from '../utils/calculationUtils';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
    legs: CandidateLeg[];
    totalOdds: number;
}

// ── Metric Card ───────────────────────────────────────────────────────────────

interface MetricCardProps {
    icon: string;
    label: string;
    value: string;
    sub?: string;
}

function MetricCard({ icon, label, value, sub }: MetricCardProps) {
    return (
        <BaseCard className="flex-1 rounded-xl p-4 relative overflow-hidden group transition-all duration-300">
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                style={{ background: 'radial-gradient(circle at center, var(--accent-glow) 0%, transparent 80%)' }} />
            <div className="relative">
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{icon}</span>
                    <span className="text-[10px] font-mono tracking-[0.2em] uppercase font-bold"
                        style={{ color: 'var(--text-secondary)' }}>{label}</span>
                </div>
                <p className="font-display font-black text-2xl leading-none"
                    style={{ color: 'var(--text-bright)', letterSpacing: '-0.02em' }}>{value}</p>
                {sub && (
                    <p className="text-[10px] font-mono mt-1.5 opacity-60 font-medium"
                        style={{ color: 'var(--text-secondary)' }}>{sub}</p>
                )}
            </div>
        </BaseCard>
    );
}

// ── Gauge Chart ───────────────────────────────────────────────────────────────

function GaugeChart({ riskScore }: { riskScore: number }) {
    const clampedRisk = Math.min(100, Math.max(0, riskScore));

    const getColor = (score: number) => {
        if (score < 30) return 'var(--win)';
        if (score < 55) return 'var(--pending)';
        return 'var(--loss)';
    };

    // getRiskLabel is now imported from calculationUtils

    const color = getColor(clampedRisk);

    return (
        <div className="w-full h-full flex flex-col items-center justify-center relative overflow-hidden">
            <svg viewBox="0 0 200 110" className="w-full h-full drop-shadow-2xl">
                <defs>
                    <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="var(--gauge-track-start)" />
                        <stop offset="100%" stopColor="var(--gauge-track-end)" />
                    </linearGradient>
                </defs>
                {/* Background Track */}
                <path
                    d="M 20 100 A 80 80 0 0 1 180 100"
                    fill="none"
                    stroke="url(#gaugeGradient)"
                    strokeWidth="18"
                    strokeLinecap="round"
                />
                {/* Active Risk Track */}
                <path
                    d="M 20 100 A 80 80 0 0 1 180 100"
                    fill="none"
                    stroke={color}
                    strokeWidth="18"
                    strokeLinecap="round"
                    strokeDasharray="251.3" // PI * 80
                    strokeDashoffset={251.3 - (clampedRisk / 100) * 251.3}
                    style={{ transition: 'stroke-dashoffset 1.5s ease-out, stroke 0.5s ease' }}
                />
            </svg>

            {/* Numeric Overlay - Positioned exactly at the pivot point */}
            <div className="absolute inset-x-0 bottom-[12%] flex flex-col items-center justify-center pointer-events-none">
                <div className="text-center">
                    <p className="font-display font-black text-6xl xl:text-7xl leading-none tracking-tighter"
                        style={{ color, textShadow: `0 0 40px ${color}55` }}>
                        {Math.round(clampedRisk)}
                    </p>
                    <p className="font-mono text-[10px] xl:text-[11px] uppercase font-black tracking-[0.4em] mt-2"
                        style={{ color: 'var(--text-secondary)' }}>
                        {getRiskLabel(clampedRisk)}
                    </p>
                </div>
            </div>
        </div>
    );
}

// ── Custom Radar Label ────────────────────────────────────────────────────────

function renderPolarAngleLabel(props: any) {
    const { payload, x, y, cx, cy } = props;

    // Determine position relative to center
    const isTop = y < cy - 30;
    const isBottom = y > cy + 30;
    const isLeft = x < cx - 30;
    const isRight = x > cx + 30;

    // Smart offsets based on quadrant
    let dx = 0;
    let dy = 0;
    let textAnchor: 'middle' | 'start' | 'end' = 'middle';

    if (isTop) {
        dy = -25;
        dx = 0;
        textAnchor = 'middle';
    } else if (isBottom) {
        dy = 20;
        dx = 0;
        textAnchor = 'middle';
    } else if (isRight) {
        dx = 18;
        textAnchor = 'start';
    } else if (isLeft) {
        dx = -18;
        textAnchor = 'end';
    }

    return (
        <text
            x={x + dx} y={y + dy}
            textAnchor={textAnchor}
            fill="var(--text-secondary)"
            fontSize={12}
            fontWeight="700"
            fontFamily="'Inter', sans-serif"
            dominantBaseline="central"
        >
            {payload.value}
        </text>
    );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function AnalyticsDashboard({ legs, totalOdds }: Props) {
    const metrics = useMemo(() => {
        if (!legs.length) return null;

        const avgConsensus = legs.reduce((s, l) => s + l.consensus, 0) / legs.length;
        const avgSources = legs.reduce((s, l) => s + l.sources, 0) / legs.length;
        const avgScore = legs.reduce((s, l) => s + l.score, 0) / legs.length;
        const tier1Ratio = legs.filter(l => l.tier === 1).length / legs.length;

        const uniqueMarkets = new Set(legs.map(l => l.market)).size;
        const totalMarkets = 7;

        const riskScore = calculateRiskScore(totalOdds, avgConsensus);

        const radarWinProb = calculateWinProbability(totalOdds);
        const radarConsensus = Math.max(0, (avgConsensus - 50) * 2);
        const radarDiversity = calculateDiversityScore(uniqueMarkets, totalMarkets, legs.length);
        const radarSources = Math.min(100, (avgSources / 4) * 100);
        const radarQuality = Math.min(100, avgScore * 100);

        return {
            totalOdds, totalLegs: legs.length, avgConsensus: Math.round(avgConsensus),
            avgSources: avgSources,
            riskScore,
            winProb: radarWinProb,
            marketSpread: radarDiversity,
            avgScore: radarQuality,
            sourceDepth: radarSources,
            balanceRatio: tier1Ratio * 100,
            radarConsensus,
        };
    }, [legs, totalOdds]);

    const radarData = useMemo(() => {
        if (!metrics) return [];
        return [
            { axis: 'Win Prob', value: metrics.winProb },
            { axis: 'Consensus', value: metrics.radarConsensus },
            { axis: 'Diversity', value: metrics.marketSpread },
            { axis: 'Sources', value: metrics.sourceDepth },
            { axis: 'Quality', value: metrics.avgScore },
        ];
    }, [metrics]);

    if (!legs.length || !metrics) return null;

    return (
        <div className="w-full rounded-2xl p-6 mb-6 fade-in shadow-2xl relative"
            style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                backdropFilter: 'blur(30px)',
            }}>
            <div className="absolute top-0 left-1/4 w-1/2 h-1" style={{ background: 'var(--accent-glow)', filter: 'blur(8px)' }} />

            <div className="flex flex-col lg:flex-row items-stretch gap-6 w-full">
                {/* Left: Metric Cards - Standardized Container */}
                <div className="flex-[0.8] lg:w-[260px]">
                    <div className="w-full h-full flex flex-col gap-4 p-4 rounded-3xl bg-black/30 border border-white/5 shadow-inner relative group">
                        <MetricCard
                            icon="🎯"
                            label="Cumulative Odds"
                            value={`@${metrics.totalOdds.toFixed(2)}`}
                            sub={`${(1 / metrics.totalOdds * 100).toFixed(2)}% implied probability`}
                        />
                        <MetricCard
                            icon="📊"
                            label="Slip Volume"
                            value={`${metrics.totalLegs} Selects`}
                            sub={`${Math.round(metrics.balanceRatio)}% tier 1 profile`}
                        />
                        <MetricCard
                            icon="📈"
                            label="Avg Consensus"
                            value={`${metrics.avgConsensus}%`}
                            sub={`across ${legs.length} matches`}
                        />
                        <MetricCard
                            icon="📡"
                            label="Avg Sources"
                            value={`${metrics.avgSources.toFixed(1)}`}
                            sub={`per match`}
                        />
                    </div>
                </div>

                {/* Vertical Divider */}
                <div className="hidden lg:block w-px self-stretch bg-gradient-to-b from-transparent via-white/15 to-transparent" />

                {/* Center: Gauge Chart - High Density Panel */}
                <div className="flex-[1.8] min-h-[340px]">
                    <div className="w-full h-full flex flex-col items-center justify-center rounded-3xl bg-black/30 border border-white/5 p-8 shadow-inner relative group overflow-hidden">
                        <div className="absolute top-4 right-4 z-20">
                            <TooltipIcon align="right" text="Risk Index (0-100): Weighted calculation of cumulative odds log-variance and source agreement strength. Proximity to 100 indicates high event volatility." />
                        </div>
                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700" style={{ background: 'radial-gradient(circle at 50% 70%, var(--accent-glow) 0%, transparent 80%)' }} />

                        <div className="flex-1 w-full flex items-center justify-center">
                            <GaugeChart riskScore={metrics.riskScore} />
                        </div>

                        <span className="text-[11px] font-mono tracking-[0.5em] uppercase opacity-40 mt-6 font-black relative z-10"
                            style={{ color: 'var(--text-primary)' }}>Risk Assessment</span>
                    </div>
                </div>

                {/* Vertical Divider */}
                <div className="hidden lg:block w-px self-stretch bg-gradient-to-b from-transparent via-white/15 to-transparent" />

                {/* Right: Radar Chart - Portfolio DNA Column */}
                <div className="flex-1 min-h-[340px]">
                    <div className="w-full h-full flex flex-col items-center justify-center rounded-3xl bg-black/30 border border-white/5 px-2 py-8 shadow-inner relative group">
                        <div className="absolute top-4 right-4 z-20">
                            <TooltipIcon align="right" text="Portfolio DNA: Visual summary of slip characteristics. Balanced shapes indicate optimized risk-reward profiles across data sources and markets." />
                        </div>
                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700" style={{ background: 'radial-gradient(circle at 50% 50%, var(--accent-glow) 0%, transparent 70%)' }} />

                        <div className="flex-1 w-full flex items-center justify-center overflow-hidden">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart data={radarData} outerRadius="70%" cx="50%" cy="50%">
                                    <PolarGrid stroke="var(--border)" strokeDasharray="4 4" />
                                    <PolarAngleAxis dataKey="axis" tick={renderPolarAngleLabel} tickLine={false} />
                                    <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                                    <Radar
                                        dataKey="value" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.3}
                                        strokeWidth={4}
                                        dot={{ r: 6, fill: 'var(--accent)', stroke: 'var(--bg-surface)', strokeWidth: 2.5 }}
                                    />
                                </RadarChart>
                            </ResponsiveContainer>
                        </div>
                        <p className="text-[11px] font-mono tracking-[0.5em] uppercase text-center mt-4 opacity-40 font-black"
                            style={{ color: 'var(--text-primary)' }}>Profile Matrix</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
