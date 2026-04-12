import { useMemo } from 'react';
import {
    RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
    Radar, ResponsiveContainer
} from 'recharts';
import { TooltipIcon } from './ui';
import type { CandidateLeg } from '../types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
    legs: CandidateLeg[];
    totalOdds: number;
}

// ── Metric Card ───────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub, icon }: {
    label: string; value: string; sub?: string; icon: string;
}) {
    return (
        <div className="flex-1 rounded-xl p-4 relative overflow-hidden group transition-all duration-300"
            style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.05)',
                boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            }}>
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                style={{ background: 'radial-gradient(circle at center, rgba(61,123,255,.1) 0%, transparent 80%)' }} />
            <div className="relative">
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{icon}</span>
                    <span className="text-[10px] font-mono tracking-[0.2em] uppercase font-bold"
                        style={{ color: 'var(--text-muted)' }}>{label}</span>
                </div>
                <p className="font-display font-black text-2xl leading-none"
                    style={{ color: 'var(--text-bright)', letterSpacing: '-0.02em' }}>{value}</p>
                {sub && (
                    <p className="text-[10px] font-mono mt-1.5 opacity-60 font-medium"
                        style={{ color: 'var(--text-secondary)' }}>{sub}</p>
                )}
            </div>
        </div>
    );
}

// ── Gauge Chart ───────────────────────────────────────────────────────────────

function GaugeChart({ riskScore }: { riskScore: number }) {
    const clampedRisk = Math.min(100, Math.max(0, riskScore));

    const getColor = (score: number) => {
        if (score < 30) return '#10B981';
        if (score < 55) return '#F59E0B';
        return '#F43F5E';
    };

    const getRiskLabel = (score: number) => {
        if (score < 20) return 'Very Safe';
        if (score < 40) return 'Safe';
        if (score < 60) return 'Moderate';
        if (score < 80) return 'Risky';
        return 'Very Risky';
    };

    const color = getColor(clampedRisk);

    return (
        <div className="w-full h-full flex flex-col items-center justify-center relative overflow-hidden">
            <svg viewBox="0 0 200 110" className="w-full h-full drop-shadow-2xl">
                <defs>
                    <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(255,255,255,0.02)" />
                        <stop offset="100%" stopColor="rgba(255,255,255,0.08)" />
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
                        style={{ color: 'var(--text-muted)' }}>
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
            fill="#8896B3"
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

        const oddsRisk = Math.min(100, (Math.log10(Math.max(1, totalOdds)) / 2.3) * 100);
        const consensusBonus = ((avgConsensus - 50) / 50) * 15;
        const riskScore = Math.min(100, Math.max(0, oddsRisk - consensusBonus));

        const winProb = (1 / totalOdds) * 100;

        const radarWinProb = Math.min(100, Math.sqrt(winProb) * 12);
        const radarConsensus = Math.max(0, (avgConsensus - 50) * 2);
        const radarDiversity = (uniqueMarkets / Math.min(totalMarkets, legs.length)) * 100;
        const radarSources = Math.min(100, (avgSources / 4) * 100);
        const radarQuality = Math.min(100, avgScore * 100);

        return {
            totalOdds, totalLegs: legs.length, avgConsensus: Math.round(avgConsensus),
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
                background: 'linear-gradient(180deg, rgba(13,19,33,1) 0%, rgba(24,36,58,.8) 100%)',
                border: '1px solid rgba(255,255,255,.12)',
                backdropFilter: 'blur(30px)',
            }}>
            <div className="absolute top-0 left-1/4 w-1/2 h-1 bg-accent/20 blur-xl" />

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
                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 bg-[radial-gradient(circle_at_50%_70%,rgba(61,123,255,0.08)_0%,transparent_80%)]" />

                        <div className="flex-1 w-full flex items-center justify-center">
                            <GaugeChart riskScore={metrics.riskScore} />
                        </div>

                        <span className="text-[11px] font-mono tracking-[0.5em] uppercase opacity-40 mt-6 font-black relative z-10"
                            style={{ color: 'var(--text-muted)' }}>Risk Assessment Gauge</span>
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
                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 bg-[radial-gradient(circle_at_50%_50%,rgba(61,123,255,0.03)_0%,transparent_70%)]" />

                        <div className="flex-1 w-full flex items-center justify-center overflow-hidden">
                            <ResponsiveContainer width="100%" height="100%">
                                <RadarChart data={radarData} outerRadius="70%" cx="50%" cy="50%">
                                    <PolarGrid stroke="rgba(255,255,255,.12)" strokeDasharray="4 4" />
                                    <PolarAngleAxis dataKey="axis" tick={renderPolarAngleLabel} tickLine={false} />
                                    <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                                    <Radar
                                        dataKey="value" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.3}
                                        strokeWidth={4}
                                        dot={{ r: 6, fill: 'var(--accent)', stroke: '#0D1321', strokeWidth: 2.5 }}
                                    />
                                </RadarChart>
                            </ResponsiveContainer>
                        </div>
                        <p className="text-[11px] font-mono tracking-[0.5em] uppercase text-center mt-4 opacity-40 font-black"
                            style={{ color: 'var(--text-muted)' }}>Portfolio matrix profile</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
