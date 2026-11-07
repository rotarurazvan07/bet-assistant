import type { CandidateLeg, BetSlip, LiveData, BetLeg} from '../types';
import { useEffect, useMemo, useState } from 'react';
import { BaseBadge } from './ui/BaseBadge';
import { formatBetDate } from '../utils/betUtils';
import { parseTeamNames } from '../utils/teamUtils';
import { getStatusColor, getStatusBadge } from '../utils/colorUtils';
import { calculateNetProfit } from '../utils/calculationUtils';
import { marketLabel } from '../config/marketConfig';
import { getPotentialStatusColor } from '../utils/colorUtils';
import { useConfigTimezone, naiveToInstant } from '../hooks/useConfigTimezone';

// ── BetPreview ────────────────────────────────────────────────────────────────

interface PreviewProps {
    legs: CandidateLeg[];
    totalOdds: number;
    pendingUrls: string[];
    onExclude: (url: string) => void;
    minStrength?: number;
}

function TierBadge({ tier }: { tier: number; }) {
    return (
        <div className="flex items-center gap-1">
            <BaseBadge
                status={tier === 1 ? 'success' : 'warning'}
            >
                {tier === 1 ? 'Balanced' : '⚠ Drift'}
            </BaseBadge>
        </div>
    );
}

function OddsMovementBadge({ direction, strength, minStrength }: { direction?: string | null; strength?: number; minStrength?: number }) {
    if (!direction || direction === 'stable') return null;
    const effectiveMinStrength = minStrength ?? 0.05;
    if (effectiveMinStrength > 0 && (strength == null || strength < effectiveMinStrength)) return null;
    const isConfirm = direction === 'down';
    const pct = strength != null ? (strength * 100).toFixed(1) : null;
    const label = isConfirm ? '↓' : '↑';
    const title = isConfirm
        ? `Odds dropped${pct ? ` ${pct}%` : ''} — bookmaker confirms`
        : `Odds rose${pct ? ` ${pct}%` : ''} — bookmaker doubts`;
    return (
        <span
            title={title}
            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-bold shrink-0"
            style={{
                background: isConfirm ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                color: isConfirm ? 'rgb(16,185,129)' : 'rgb(239,68,68)',
                border: `1px solid ${isConfirm ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            }}
        >
            {label}
        </span>
    );
}

function QualityIndicator({ score }: { score: number }) {
    const qualityColor = (() => {
        const clampedScore = Math.max(0, Math.min(1, score));
        const red = { r: 239, g: 68, b: 68 };
        const green = { r: 16, g: 185, b: 129 };
        const r = Math.round(red.r + (green.r - red.r) * clampedScore);
        const g = Math.round(red.g + (green.g - red.g) * clampedScore);
        const b = Math.round(red.b + (green.b - red.b) * clampedScore);
        return `rgb(${r}, ${g}, ${b})`;
    })();

    return (
        <div className="flex items-center gap-2">
            <div className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>
                Quality
            </div>
            <div
                className="w-4 h-4 rounded-full"
                style={{
                    background: qualityColor,
                    boxShadow: `0 0 6px ${qualityColor}80`
                }}
            />
            <span
                className="text-sm font-bold font-mono"
                style={{ color: qualityColor }}
            >
                {(score * 100).toFixed(0)}%
            </span>
        </div>
    );
}

export function BetPreview({ legs, pendingUrls, onExclude, minStrength }: PreviewProps) {
    // empty preview is rendered by SmartBuilder via EmptyState. Keep a silent fallback.
    if (!legs.length) {
        return null;
    }

    const outOfBand = legs.filter(l => l.tier === 2).length;

    return (
        <div className="fade-in">
            {/* Leg count + out-of-band badge */}
            {outOfBand > 0 && (
                <div className="flex items-center gap-3 mb-4">
                    <BaseBadge status="warning">
                        {outOfBand} out-of-band
                    </BaseBadge>
                </div>
            )}

            {/* Match Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {legs.map((leg, i) => {
                    const isDupe = pendingUrls.includes(leg.result_url ?? '');

                    // Parse team names from "Team A - Team B" format
                    const { teamA, teamB } = parseTeamNames(leg.match_name);

                    const dt = formatBetDate(leg.datetime, {
                        includeWeekday: false,
                        includeYear: false
                    });

                    return (
                        <div key={i}
                            className="group rounded-xl overflow-hidden fade-in transition-all duration-300 cursor-default"
                            style={{
                                background: 'var(--bg-card)',
                                border: `1px solid ${isDupe ? 'var(--pending)' : 'var(--border)'}`,
                                boxShadow: 'var(--shadow-sm)',
                                transform: 'translateY(0)',
                            }}
                            onMouseEnter={e => {
                                e.currentTarget.style.transform = 'translateY(-4px)';
                                e.currentTarget.style.boxShadow = 'var(--accent-glow), var(--shadow-md)';
                                e.currentTarget.style.borderColor = 'var(--accent)';
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.transform = 'translateY(0)';
                                e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
                                e.currentTarget.style.borderColor = isDupe ? 'var(--pending)' : 'var(--border)';
                            }}
                        >
                            {/* Dupe warning strip */}
                            {isDupe && (
                                <div className="text-[9px] font-mono px-3 py-1.5 text-center"
                                    style={{ background: 'var(--pending-bg)', color: 'var(--pending)' }}>
                                    ⚠ In pending slip
                                </div>
                            )}

                            {/* Card Content */}
                            <div className="p-4" style={{ border: '1px solid var(--border-accent)', }}>
                                {/* Top: Teams + Date + Exclude */}
                                <div className="flex items-start justify-between gap-1.5 mb-3">
                                    <div className="min-w-0 flex-1">
                                        <p className="font-sans font-bold text-[13px] leading-tight truncate"
                                            style={{ color: 'var(--text-bright)' }}>
                                            {teamA}
                                        </p>
                                        {teamB && (
                                            <>
                                                <span className="text-[9px] font-mono block my-0.5"
                                                    style={{ color: 'var(--text-secondary)' }}>vs</span>
                                                <p className="font-sans font-bold text-[13px] leading-tight truncate"
                                                    style={{ color: 'var(--text-bright)' }}>
                                                    {teamB}
                                                </p>
                                            </>
                                        )}
                                        {dt && (
                                            <p className="text-[10px] font-mono mt-1.5"
                                                style={{ color: 'white' }}>{dt}</p>
                                        )}
                                        {leg.league && (
                                            <p className="text-[9px] font-mono mt-0.5 opacity-60 uppercase tracking-wider"
                                                style={{ color: 'var(--text-secondary)' }}>{leg.league}</p>
                                        )}
                                    </div>
                                    <button
                                        className="btn-icon shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                                        onClick={() => leg.result_url && onExclude(leg.result_url)}
                                        style={{ width: 24, height: 24, marginTop: -2 }}
                                    >
                                        <span style={{ fontSize: 11, color: 'var(--loss)' }}>✕</span>
                                    </button>
                                </div>

                                {/* Middle: Market + Odds Badge - Left aligned */}
                                <div className="mb-4">
                                    <span className="font-display font-bold text-sm px-4 py-1.5 rounded-full
                                                     transition-all duration-200 inline-block"
                                        style={{
                                            background: 'var(--bg-card)',
                                            border: `2px solid var(--accent)`,
                                            color: 'var(--accent)',
                                            boxShadow: '0 0 12px var(--accent-glow)',
                                        }}>
                                        {marketLabel(leg.market)} <span style={{ opacity: 0.7, margin: '0 3px' }}></span>@{leg.odds.toFixed(2)}
                                    </span>
                                </div>

                                {/* Bottom: Quality Indicator + Tier */}
                                <div className="flex items-center justify-between">
                                    <QualityIndicator score={leg.score} />
                                <div className="flex items-center gap-1.5">
                                    <OddsMovementBadge direction={leg.odds_movement_direction} strength={leg.odds_movement_strength} minStrength={minStrength} />
                                    <TierBadge tier={leg.tier} />
                                </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ── BetLegRow (Unified Leg Component) ──────────────────────────────────────────

interface BetLegRowProps {
    // Legs render from settled-slip rows: BetLeg carries every field the
    // row reads (datetime, status, market, odds, league, result_url).
    leg: BetLeg;
    liveData?: LiveData;
}

export function BetLegRow({ leg, liveData = {} }: BetLegRowProps) {
    const dt = formatBetDate(leg.datetime, {
        includeWeekday: true,
        includeYear: false
    });
    const legStatusColor = getStatusColor(leg.status);
    const live = liveData[leg.match_name];

    let marketOddsColor: string;
    if (leg.status === 'Live') {
        const potentialColor = getPotentialStatusColor(leg, live?.score);
        marketOddsColor = potentialColor || legStatusColor;
    } else {
        marketOddsColor = legStatusColor;
    }

    return (
        <div
            className="p-3 sm:p-4 rounded-lg flex items-start gap-3 sm:gap-4 transition-all"
            style={{
                background: 'var(--bg-raised)',
                border: `1px solid ${legStatusColor}40`,
                borderLeft: `4px solid ${legStatusColor}`,
            }}
        >
            {/* Left Status Icon */}
            {/* <div
                className="flex items-center justify-center w-7 h-7 sm:w-8 sm:h-8 rounded-full shrink-0"
                style={{
                    background: legStatusColor + '15',
                    color: legStatusColor,
                    border: `1.5px solid ${legStatusColor}`
                }}
            >
                <span className="text-sm sm:text-base font-bold">{legStatusIcon}</span>
            </div> */}

            {/* Leg Details */}
            <div className="flex-1 min-w-0">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                    <div className="flex-1 min-w-0">
                        {leg.result_url ? (
                            <a
                                href={leg.result_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-sans font-bold text-sm sm:text-base leading-tight hover:underline block"
                                style={{ color: 'var(--text-bright)' }}
                                onClick={e => e.stopPropagation()}
                            >
                                {leg.match_name}
                            </a>
                        ) : (
                            <p className="font-sans font-bold text-sm sm:text-base leading-tight" style={{ color: 'var(--text-bright)' }}>
                                {leg.match_name}
                            </p>
                        )}
                        <p className="text-[11px] sm:text-xs font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>{dt}</p>
                        {leg.league && (
                            <p className="text-[9px] sm:text-[10px] font-mono mt-0.5 opacity-60 uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                                {leg.league}
                            </p>
                        )}
                    </div>
                    <div className="flex items-center gap-2 sm:gap-3 shrink-0 flex-wrap">
                        <span
                            className="font-display font-bold text-[11px] sm:text-sm px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-full"
                            style={{
                                background: 'var(--bg-card)',
                                border: `2px solid ${marketOddsColor}`,
                                color: 'white'
                            }}
                        >
                            {marketLabel(leg.market)} @{leg.odds.toFixed(2)}
                        </span>
                        {live && leg.status === 'Live' && (
                            <div className="flex flex-col items-center gap-0.5">
                                <span
                                    className="font-mono text-xs sm:text-sm font-bold px-2 py-0.5 sm:py-1 rounded animate-pulse"
                                    style={{ background: 'var(--live-bg)', color: 'var(--live)' }}
                                >
                                    {live.score}
                                </span>
                                <span className="font-mono text-[9px] sm:text-[11px] font-bold" style={{ color: 'var(--live)' }}>
                                    {live.minute}
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

// ── SlipCard ──────────────────────────────────────────────────────────────────

interface SlipCardProps {
    slip: BetSlip;
    liveData?: LiveData;
    onDelete?: (id: number) => void;
    onCardClick?: () => void;
}

function sortSlipLegs(legs: BetLeg[]): BetLeg[] {
    return [...legs].sort((a, b) => {
        const aIsLive = a.status === 'Live';
        const bIsLive = b.status === 'Live';
        if (aIsLive && !bIsLive) return -1;
        if (!aIsLive && bIsLive) return 1;
        const aTime = a.datetime ? new Date(a.datetime).getTime() : 0;
        const bTime = b.datetime ? new Date(b.datetime).getTime() : 0;
        return aTime - bTime;
    });
}

function getSlipWinChance(legs: BetLeg[]): number | null {
    if (legs.some(leg => leg.status === 'Lost')) return null;

    const unsettledLegs = legs.filter(leg => leg.status === 'Pending' || leg.status === 'Live');
    if (unsettledLegs.length === 0 || unsettledLegs.some(leg => !Number.isFinite(leg.odds) || leg.odds < 1)) {
        return null;
    }

    const probability = unsettledLegs.reduce((chance, leg) => chance / leg.odds, 1);
    return Math.min(probability * 100, 100);
}

function WinChanceGauge({ chance, compact = false }: { chance: number; compact?: boolean }) {
    return (
        <div
            className={compact ? 'min-w-[72px] flex-1' : 'w-full'}
            title="Estimated chance from the original odds on unsettled legs"
        >
            {!compact && (
                <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="text-xs font-mono uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>
                        Estimated chance
                    </span>
                </div>
            )}
            <div
                className={`relative overflow-hidden rounded-full ${compact ? 'h-5' : 'h-7'}`}
                style={{ background: 'var(--bg-raised)' }}
                role="progressbar"
                aria-label="Estimated chance"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={chance}
                aria-valuetext={`${chance.toFixed(1)}% estimated chance`}
            >
                <div
                    className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-300"
                    style={{
                        width: `${chance}%`,
                        background: 'linear-gradient(90deg, var(--loss), var(--pending), var(--win))',
                    }}
                />
                <span
                    className={`absolute inset-0 flex items-center justify-center font-mono font-bold text-white ${compact ? 'text-[10px]' : 'text-xs'}`}
                    style={{ textShadow: '0 1px 3px rgba(0, 0, 0, .95)' }}
                >
                    {chance.toFixed(1)}%
                </span>
            </div>
        </div>
    );
}

export function SlipCard({ slip, liveData = {}, onDelete, onCardClick }: SlipCardProps) {
    const { timezone } = useConfigTimezone();
    const zone = timezone || 'UTC';
    // Tick the wall clock once a minute so the upcoming-match countdown refreshes
    // without calling an impure time source during render.
    const [nowMs, setNowMs] = useState(() => Date.now());
    useEffect(() => {
        const id = setInterval(() => setNowMs(Date.now()), 60_000);
        return () => clearInterval(id);
    }, []);
    const hdrBg = slip.slip_status === 'Live' ? 'var(--live-bg)' : (slip.slip_status === 'Won' ? 'var(--win-bg)' : slip.slip_status === 'Lost' ? 'var(--loss-bg)' : 'var(--pending-bg)');
    const statusBorderColor = getStatusColor(slip.slip_status);

    const sortedLegs = useMemo(() => sortSlipLegs(slip.legs), [slip.legs]);

    // Truncated display logic based on live matches count:
    // - If live >= 2: show only live matches
    // - If live = 1: show 1 live + 1 non-live
    // - If live = 0: show 2 non-live
    const displayedLegs = useMemo(() => {
        const liveLegs = sortedLegs.filter(leg => leg.status === 'Live');
        const nonLiveLegs = sortedLegs.filter(leg => leg.status !== 'Live');

        if (liveLegs.length >= 2) {
            return liveLegs;
        } else if (liveLegs.length === 1) {
            const oneNonLive = nonLiveLegs.slice(0, 1);
            return [...liveLegs, ...oneNonLive];
        } else {
            return nonLiveLegs.slice(0, 2);
        }
    }, [sortedLegs]);

    const hiddenCount = slip.legs.length - displayedLegs.length;
    const legStatusCounts = {
        won: slip.legs.filter(leg => leg.status === 'Won').length,
        lost: slip.legs.filter(leg => leg.status === 'Lost').length,
        live: slip.legs.filter(leg => leg.status === 'Live').length,
        pending: slip.legs.filter(leg => leg.status === 'Pending').length,
    };
    const winChance = getSlipWinChance(slip.legs);

    return (
        <div
            className={`flex flex-col rounded-lg overflow-hidden fade-in bg-[var(--bg-card)] border-l-4 cursor-pointer hover:brightness-110 transition-all slip-${slip.slip_status.toLowerCase()}`}
            style={{ borderLeftColor: statusBorderColor, borderLeftWidth: '4px' }}
            onClick={onCardClick}
        >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 flex-wrap justify-between"
                style={{ background: hdrBg, borderBottom: `1px solid ${statusBorderColor}33` }}>
                <div className="flex items-center gap-2 flex-wrap">
                    <BaseBadge status="default">
                        {slip.date_generated.split('T')[0]}
                    </BaseBadge>
                    <BaseBadge status="default">
                        {slip.profile}
                    </BaseBadge>
                </div>
                <div className="flex items-center gap-2">
                    <BaseBadge status={getStatusBadge(slip.slip_status)}>
                        {slip.slip_status}
                    </BaseBadge>
                    {slip.slip_status === 'Pending' && onDelete && (
                        <button className="btn-icon" onClick={(e) => { e.stopPropagation(); onDelete(slip.slip_id); }} title="Delete slip">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                <line x1="10" y1="11" x2="10" y2="17"></line>
                                <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
                        </button>
                    )}
                </div>
            </div>

            <div
                className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2 border-b text-xs font-mono"
                style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
                role="group"
                aria-label="Leg status summary"
            >
                <span style={{ color: 'var(--win)' }}>{legStatusCounts.won} won</span>
                <span style={{ color: 'var(--loss)' }}>{legStatusCounts.lost} lost</span>
                {legStatusCounts.live > 0 && (
                    <span style={{ color: 'var(--live)' }}>{legStatusCounts.live} live</span>
                )}
                {legStatusCounts.pending > 0 && (
                    <span style={{ color: 'var(--pending)' }}>{legStatusCounts.pending} pending</span>
                )}
                {winChance !== null && <WinChanceGauge chance={winChance} compact />}
            </div>

            {/* Legs - using the recycled BetLegRow component for each displayed leg */}
            <div className="flex-1 p-3 space-y-2">
                {displayedLegs.map((leg, idx) => (
                    <BetLegRow
                        key={idx}
                        leg={leg}
                        liveData={liveData}
                    />
                ))}
                {hiddenCount > 0 && onCardClick && (
                    <button
                        className="w-full mt-2 py-2 text-sm font-mono rounded transition-colors"
                        style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--accent)' }}
                        onClick={(e) => {
                            e.stopPropagation();
                            onCardClick();
                        }}
                    >
                        Show Details ({hiddenCount} more)
                    </button>
                )}
            </div>

            {/* Footer */}
            <div className="p-3 mt-auto flex justify-between items-center rounded-b-lg"
                style={{ background: 'var(--bg-raised)' }}>
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-3 text-sm">
                        <span className="font-mono" style={{ color: 'white' }}>
                            {slip.units}u
                        </span>
                        <span className="font-mono" style={{ color: 'white' }}>
                            @ {slip.total_odds.toFixed(2)}
                        </span>
                    </div>
                </div>
                {/* For pending slips, show time to next match; for won/lost, show profit */}
                <div className="font-mono font-bold text-sm">
                    {slip.slip_status === 'Pending' ? (
                        (() => {
                            // Find the earliest leg datetime that is in the future
                            const upcomingLegs = slip.legs
                                .filter(leg => leg.datetime && naiveToInstant(leg.datetime, zone) > nowMs)
                                .map(leg => naiveToInstant(leg.datetime!, zone));

                            if (upcomingLegs.length === 0) {
                                return <span style={{ color: 'var(--text-muted)' }}>no upcoming</span>;
                            }

                            const nextMatch = Math.min(...upcomingLegs);
                            const msUntil = nextMatch - nowMs;

                            if (msUntil <= 0) {
                                return <span style={{ color: 'var(--text-primary)' }}>live</span>;
                            }

                            const hours = Math.floor(msUntil / (1000 * 60 * 60));
                            if (hours >= 1) {
                                return <span style={{ color: 'var(--text-primary)' }}>Next match in {hours}h</span>;
                            }

                            const mins = Math.round(msUntil / (1000 * 60));
                            return <span style={{ color: 'var(--text-primary)' }}>Next match in {mins}m</span>;
                        })()
                    ) : (() => {
                        const netProfit = calculateNetProfit(slip.slip_status, slip.total_odds, slip.units);
                        if (netProfit !== null) {
                            const isPositive = netProfit > 0;
                            const color = isPositive ? 'var(--win)' : 'var(--loss)';
                            return <span style={{ color }}>{isPositive ? '+' : ''}{netProfit.toFixed(2)}</span>;
                        }
                        return null;
                    })()}
                </div>
            </div>
        </div>
    );
}

// ── SlipDetailModal ────────────────────────────────────────────────────────────

interface SlipDetailModalProps {
    slip: BetSlip | null;
    liveData?: LiveData;
    onClose: () => void;
}

export function SlipDetailModal({ slip, liveData = {}, onClose }: SlipDetailModalProps) {
    // Hooks must run unconditionally — effect sits ABOVE the null guard
    // (eslint react-hooks/rules-of-hooks: the old `if (!slip) return null`
    // above made this useEffect conditional).
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleEscape);
        return () => window.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    if (!slip) return null;

    const legStatusCounts = {
        won: slip.legs.filter(leg => leg.status === 'Won').length,
        lost: slip.legs.filter(leg => leg.status === 'Lost').length,
        live: slip.legs.filter(leg => leg.status === 'Live').length,
        pending: slip.legs.filter(leg => leg.status === 'Pending').length,
    };
    const legStatusSummary = [
        { label: 'Won', count: legStatusCounts.won, color: 'var(--win)' },
        { label: 'Lost', count: legStatusCounts.lost, color: 'var(--loss)' },
        ...(legStatusCounts.live > 0
            ? [{ label: 'Live', count: legStatusCounts.live, color: 'var(--live)' }]
            : []),
        ...(legStatusCounts.pending > 0
            ? [{ label: 'Pending', count: legStatusCounts.pending, color: 'var(--pending)' }]
            : []),
    ];
    const winChance = getSlipWinChance(slip.legs);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/70 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal Content */}
            <div className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col rounded-xl shadow-2xl"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>

                {/* Header */}
                <div className="px-6 py-4 border-b flex flex-wrap justify-between items-start gap-4"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg-card)' }}>
                    <div>
                        <h2 className="text-xl font-bold" style={{ color: 'var(--text-bright)' }}>
                            {slip.date_generated.split('T')[0]}
                        </h2>
                        <p className="text-sm font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>
                            {slip.profile.toUpperCase()}
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-4">
                        <div>
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Status</p>
                            <BaseBadge status={getStatusBadge(slip.slip_status)}>
                                {slip.slip_status}
                            </BaseBadge>
                        </div>
                        <div>
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Stake</p>
                            <p className="text-xl font-bold" style={{ color: 'white' }}>
                                {slip.units}u
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Legs</p>
                            <p className="text-xl font-bold" style={{ color: 'white' }}>
                                {slip.legs.length}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Odds</p>
                            <p className="text-2xl font-bold" style={{ color: 'white' }}>
                                {slip.total_odds.toFixed(2)}
                            </p>
                        </div>
                        {/* Show potential win or net profit in header */}
                        {(() => {
                            const netProfit = calculateNetProfit(slip.slip_status, slip.total_odds, slip.units);
                            if (slip.slip_status === 'Pending' || slip.slip_status === 'Live') {
                                // Potential Win = (total_odds * units) - units
                                const potentialWin = slip.total_odds * slip.units - slip.units;
                                return (
                                    <div className="text-right">
                                        <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Potential Win</p>
                                        <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                                            {potentialWin.toFixed(2)}u
                                        </p>
                                    </div>
                                );
                            } else if (netProfit !== null) {
                                const isPositive = netProfit > 0;
                                const color = isPositive ? 'var(--win)' : 'var(--loss)';
                                return (
                                    <div className="text-right">
                                        <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>
                                            {isPositive ? 'Profit' : 'Loss'}
                                        </p>
                                        <p className="text-2xl font-bold" style={{ color }}>
                                            {isPositive ? '+' : ''}{netProfit.toFixed(2)}u
                                        </p>
                                    </div>
                                );
                            }
                            return null;
                        })()}
                    </div>
                </div>

                <div
                    className="grid gap-3 border-b px-6 py-4"
                    style={{
                        borderColor: 'var(--border)',
                        background: 'var(--bg-raised)',
                        gridTemplateColumns: `repeat(${legStatusSummary.length}, minmax(0, 1fr))`,
                    }}
                    role="group"
                    aria-label="Leg status summary"
                >
                    {legStatusSummary.map(({ label, count, color }) => (
                        <div
                            key={label}
                            className="rounded-lg border px-3 py-3 text-center"
                            style={{ borderColor: `${color}55`, background: `${color}12` }}
                        >
                            <p className="font-mono text-2xl font-bold" style={{ color }}>{count}</p>
                            <p className="text-xs font-mono uppercase tracking-wide" style={{ color }}>{label}</p>
                        </div>
                    ))}
                </div>

                {winChance !== null && (
                    <div className="border-b px-6 py-4" style={{ borderColor: 'var(--border)' }}>
                        <WinChanceGauge chance={winChance} />
                    </div>
                )}

                {/* Legs List - using the exact same BetLegRow component! */}
                <div className="flex-1 overflow-y-auto p-6 space-y-3">
                    {sortSlipLegs(slip.legs).map((leg, i) => (
                        <BetLegRow
                            key={i}
                            leg={leg}
                            liveData={liveData}
                        />
                    ))}
                </div>

            </div>
        </div>
    );
}
