import type { CandidateLeg, BetSlip, LiveData } from '../types';
import { useEffect, useMemo } from 'react';
import { BaseBadge } from './ui/BaseBadge';
import { formatBetDate } from '../utils/betUtils';
import { parseTeamNames } from '../utils/teamUtils';
import { getStatusColor, getStatusIcon, getStatusBadge } from '../utils/colorUtils';
import { calculateNetProfit } from '../utils/calculationUtils';
import { getPotentialStatusColor } from '../utils/colorUtils';

// ── BetPreview ────────────────────────────────────────────────────────────────

interface PreviewProps {
    legs: CandidateLeg[];
    totalOdds: number;
    pendingUrls: string[];
    onExclude: (url: string) => void;
}

function TierBadge({ tier }: { tier: number; }) {
    return (
        <div className="flex items-center gap-1">
            <BaseBadge
                status={tier === 1 ? 'success' : 'warning'}
            >
                {tier === 1 ? '✓ Balanced' : '⚠ Drift'}
            </BaseBadge>
        </div>
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

export function BetPreview({ legs, pendingUrls, onExclude }: PreviewProps) {
    if (!legs.length) {
        return (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
                <span className="text-3xl opacity-30">🎯</span>
                <p className="text-[13px] font-sans" style={{ color: 'var(--text-secondary)' }}>
                    No matches meet the current criteria.
                </p>
            </div>
        );
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
                            <div className="p-4" style={{border: '1px solid var(--border-accent)',}}>
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
                                        {leg.market} <span style={{ opacity: 0.7, margin: '0 3px' }}></span>@{leg.odds.toFixed(2)}
                                    </span>
                                </div>

                                {/* Bottom: Quality Indicator + Tier */}
                                <div className="flex items-center justify-between">
                                    <QualityIndicator score={leg.score} />
                                    <TierBadge tier={leg.tier}/>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ── SlipCard ──────────────────────────────────────────────────────────────────

// ── SlipCard (Grid Layout) ──────────────────────────────────────────────────────

interface SlipCardProps {
    slip: BetSlip;
    liveData?: LiveData;
    onDelete?: (id: number) => void;
    onCardClick?: () => void;
}

export function SlipCard({ slip, liveData = {}, onDelete, onCardClick }: SlipCardProps & { onCardClick?: () => void }) {
    const hdrBg = slip.slip_status === 'Live' ? 'var(--live-bg)' : (slip.slip_status === 'Won' ? 'var(--win-bg)' : slip.slip_status === 'Lost' ? 'var(--loss-bg)' : 'var(--pending-bg)');

    // Status border colors
    const statusBorderColor = getStatusColor(slip.slip_status);

    // Sort legs: live legs first, then others by datetime
    const sortedLegs = useMemo(() => {
        const legs = [...slip.legs];
        return legs.sort((a, b) => {
            // Live legs come first
            const aIsLive = a.status === 'Live';
            const bIsLive = b.status === 'Live';
            if (aIsLive && !bIsLive) return -1;
            if (!aIsLive && bIsLive) return 1;
            // Then sort by datetime (ascending)
            const aTime = a.datetime ? new Date(a.datetime).getTime() : 0;
            const bTime = b.datetime ? new Date(b.datetime).getTime() : 0;
            return aTime - bTime;
        });
    }, [slip.legs]);

    // Display logic based on live matches count:
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

            {/* Legs - truncated display */}
            <div className="flex-1 p-3 space-y-2">
                {displayedLegs.map((leg, idx) => {
                    const live = liveData[leg.match_name];
                    const dt = formatBetDate(leg.datetime, {
                        includeWeekday: true,
                        includeYear: false
                    });
                    // Pick border color based on leg status
                    let pickBorderColor = getStatusColor(leg.status);
                    
                    // For live pending slips, apply potential outcome color
                    if ((slip.slip_status === 'Pending' || slip.slip_status === 'Live') && leg.status === 'Live') {
                        const potentialColor = getPotentialStatusColor(leg, live?.score);
                        if (potentialColor) {
                            pickBorderColor = potentialColor;
                        }
                    }

                    return (
                        <div key={idx} className="p-2 rounded" style={{ 
                            background: 'var(--bg-raised)', 
                            border: `1px solid ${pickBorderColor}` 
                        }}>
                            <div className="flex items-start justify-between gap-2 mb-1">
                                <div className="flex-1 min-w-0">
                                    {leg.result_url ? (
                                        <a
                                            href={leg.result_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="font-sans font-bold text-sm leading-tight hover:underline"
                                            style={{ color: 'var(--text-bright)' }}
                                            onClick={e => e.stopPropagation()}
                                        >
                                            {leg.match_name}
                                        </a>
                                    ) : (
                                        <p className="font-sans font-bold text-sm leading-tight" style={{ color: 'var(--text-bright)' }}>
                                            {leg.match_name}
                                        </p>
                                    )}
                                    <p className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>{dt}</p>
                                </div>
                                {leg.status === 'Live' && (
                                    <span className="relative inline-flex items-center justify-center w-4 h-4 shrink-0">
                                        <span className="absolute inset-0 rounded-full animate-ping opacity-60"
                                            style={{ background: 'var(--live)' }} />
                                        <span className="relative block w-3 h-3 rounded-full"
                                            style={{ background: 'var(--live)' }} />
                                    </span>
                                )}
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="font-display font-bold text-base px-2.5 py-1 rounded-full"
                                    style={{
                                        background: 'var(--bg-card)',
                                        border: `2px solid ${pickBorderColor}`,
                                        color: 'white'
                                    }}>
                                    {leg.market} @{leg.odds.toFixed(2)}
                                </span>
                                {live && leg.status === 'Live' && (
                                    <div className="flex flex-col items-center gap-1">
                                        <span className="font-mono text-lg font-bold px-3 py-2 rounded"
                                            style={{ background: 'var(--live-bg)', color: 'var(--live)' }}>
                                            {live.score}
                                        </span>
                                        <span className="font-mono text-base font-bold" style={{ color: 'var(--live)' }}>
                                            {live.minute}
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
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
                            const now = new Date();
                            const upcomingLegs = slip.legs
                                .filter(leg => leg.datetime && new Date(leg.datetime) > now)
                                .map(leg => new Date(leg.datetime!));

                            if (upcomingLegs.length === 0) {
                                return <span style={{ color: 'var(--text-muted)' }}>no upcoming</span>;
                            }

                            const nextMatch = new Date(Math.min(...upcomingLegs.map(d => d.getTime())));
                            const hoursUntil = (nextMatch.getTime() - now.getTime()) / (1000 * 60 * 60);

                            if (hoursUntil < 1) {
                                const mins = Math.round(hoursUntil * 60);
                                return <span style={{ color: 'var(--text-primary)' }}>Next match in {mins}m</span>;
                            }

                            return <span style={{ color: 'var(--text-primary)' }}>Next match in {Math.round(hoursUntil)}h</span>;
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
    if (!slip) return null;

    // Close on Escape key
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleEscape);
        return () => window.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    // No need to pre-calculate; we'll compute in footer

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/70 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal Content */}
            <div className="relative w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col rounded-xl shadow-2xl"
                style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>

                {/* Header */}
                <div className="px-6 py-4 border-b flex justify-between items-center"
                    style={{ borderColor: 'var(--border)', background: 'var(--bg-card)' }}>
                    <div>
                        <h2 className="text-xl font-bold" style={{ color: 'var(--text-bright)' }}>
                            Betting Slip
                        </h2>
                        <p className="text-sm font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>
                            {slip.date_generated.split('T')[0]} • {slip.profile.toUpperCase()}
                        </p>
                    </div>
                    <div className="flex items-center gap-6">
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
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Total Odds</p>
                            <p className="text-2xl font-bold" style={{ color: 'white' }}>
                                @{slip.total_odds.toFixed(2)}
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

                {/* Legs List */}
                <div className="flex-1 overflow-y-auto p-6 space-y-3">
                    {slip.legs.map((leg, i) => {
                        const live = liveData[leg.match_name];
                        const dt = formatBetDate(leg.datetime, {
                            includeWeekday: true,
                            includeYear: false
                        });
                        const legStatusColor = getStatusColor(leg.status);
                        const legStatusIcon = getStatusIcon(leg.status);

                        return (
                            <div key={i} className="p-4 rounded-lg flex items-start gap-4"
                                style={{
                                    background: 'var(--bg-raised)',
                                    border: `1px solid ${legStatusColor}`,
                                    borderLeftWidth: '4px'
                                }}>
                                <div className="flex items-center justify-center w-8 h-8 rounded-full shrink-0"
                                    style={{
                                        background: legStatusColor + '20',
                                        color: legStatusColor,
                                        border: `2px solid ${legStatusColor}`
                                    }}>
                                    <span className="text-lg font-bold">{legStatusIcon}</span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex-1 min-w-0">
                                            {leg.result_url ? (
                                                <a
                                                    href={leg.result_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="font-sans font-bold text-lg leading-tight hover:underline"
                                                    style={{ color: 'var(--text-bright)' }}
                                                >
                                                    {leg.match_name}
                                                </a>
                                            ) : (
                                                <p className="font-sans font-bold text-lg leading-tight" style={{ color: 'var(--text-bright)' }}>
                                                    {leg.match_name}
                                                </p>
                                            )}
                                            <p className="text-sm font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>{dt}</p>
                                        </div>
                                        <div className="flex items-center gap-3 shrink-0">
                                            <span className="font-display font-bold text-xl px-4 py-2 rounded-full"
                                                style={{
                                                    background: 'var(--bg-card)',
                                                    border: `2px solid ${legStatusColor}`,
                                                    color: 'white'
                                                }}>
                                                {leg.market} @{leg.odds.toFixed(2)}
                                            </span>
                                            {live && leg.status === 'Live' && (
                                                <div className="flex flex-col items-center gap-1.5">
                                                    <span className="font-mono text-xl font-bold px-4 py-2 rounded"
                                                        style={{ background: 'var(--live-bg)', color: 'var(--live)' }}>
                                                        {live.score}
                                                    </span>
                                                    <span className="font-mono text-lg font-bold" style={{ color: 'var(--live)' }}>
                                                        {live.minute}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

            </div>
        </div>
    );
}
