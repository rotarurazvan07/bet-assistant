import type { CandidateLeg, BetSlip, LiveData } from '../types';
import { useEffect, useMemo } from 'react';

// ── BetPreview ────────────────────────────────────────────────────────────────

interface PreviewProps {
    legs: CandidateLeg[];
    totalOdds: number;
    pendingUrls: string[];
    onExclude: (url: string) => void;
}

function TierBadge({ tier, score }: { tier: number; score: number }) {
    return (
        <div className="flex items-center gap-1">
            <span className="badge text-[9px]"
                style={tier === 1
                    ? { background: 'var(--win-bg)', color: 'var(--win)' }
                    : { background: 'var(--pend-bg)', color: 'var(--pending)' }}>
                {tier === 1 ? '✓ Balanced' : '⚠ Drift'}
            </span>
            <span className="font-mono text-[9px]" style={{ color: 'var(--text-muted)' }}>
                {score.toFixed(2)}
            </span>
        </div>
    );
}

export function BetPreview({ legs, totalOdds, pendingUrls, onExclude }: PreviewProps) {
    if (!legs.length) {
        return (
            <div className="text-[12px] font-sans text-center py-8" style={{ color: 'var(--text-muted)' }}>
                No matches meet the current criteria.
            </div>
        );
    }

    const outOfBand = legs.filter(l => l.tier === 2).length;

    return (
        <div className="fade-in">
            {/* Summary bar */}
            <div className="flex items-center gap-6 mb-4 px-3 py-2.5 rounded-lg"
                style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
                <div>
                    <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Total Odds </span>
                    <span className="font-display font-bold text-xl" style={{ color: 'var(--accent)' }}>
                        @{totalOdds.toFixed(2)}
                    </span>
                </div>
                <div>
                    <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Legs </span>
                    <span className="font-mono font-bold text-base" style={{ color: 'var(--text-bright)' }}>
                        {legs.length}
                    </span>
                </div>
                {outOfBand > 0 && (
                    <span className="badge" style={{ background: 'var(--pend-bg)', color: 'var(--pending)' }}>
                        {outOfBand} out-of-band
                    </span>
                )}
            </div>

            {/* Leg cards */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                {legs.map((leg, i) => {
                    const isDupe = pendingUrls.includes(leg.result_url ?? '');
                    const consColor = leg.consensus >= 80 ? 'var(--win)'
                        : leg.consensus >= 60 ? 'var(--pending)'
                            : 'var(--loss)';
                    const consWidth = `${leg.consensus}%`;
                    const dt = leg.datetime
                        ? new Date(leg.datetime).toLocaleString('en-GB', {
                            weekday: 'short', day: '2-digit', month: 'short',
                            hour: '2-digit', minute: '2-digit'
                        })
                        : '';

                    return (
                        <div key={i} className="rounded-lg p-3 fade-in"
                            style={{
                                background: 'var(--bg-raised)',
                                border: `1px solid ${isDupe ? 'var(--pending)' : 'var(--border)'}`,
                            }}>
                            {isDupe && (
                                <div className="text-[10px] font-mono mb-2 px-2 py-1 rounded"
                                    style={{ background: 'var(--pend-bg)', color: 'var(--pending)' }}>
                                    ⚠ Already in a pending slip
                                </div>
                            )}
                            <div className="flex items-start justify-between gap-2 mb-2">
                                <div>
                                    <p className="font-sans font-bold text-[15px]" style={{ color: 'var(--text-bright)' }}>
                                        {leg.match_name}
                                    </p>
                                    <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>{dt}</p>
                                </div>
                                <button className="btn-icon shrink-0" onClick={() => leg.result_url && onExclude(leg.result_url)}>
                                    <span style={{ fontSize: 12 }}>✕</span>
                                </button>
                            </div>

                            <div className="flex items-center justify-between mb-2">
                                <span className="font-display font-bold text-base px-3 py-1 rounded-full"
                                    style={{
                                        background: 'var(--bg-card)',
                                        border: '2px solid var(--accent)',
                                        color: 'var(--accent)'
                                    }}>
                                    {leg.market} @{leg.odds.toFixed(2)}
                                </span>
                            </div>

                            {/* Consensus bar */}
                            <div className="h-1 rounded-full mb-1.5 overflow-hidden"
                                style={{ background: 'var(--bg-card)' }}>
                                <div className="h-full rounded-full transition-all duration-300"
                                    style={{ width: consWidth, background: consColor }} />
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                                    Consensus: {leg.consensus}% · Sources: {leg.sources}
                                </span>
                                <TierBadge tier={leg.tier} score={leg.score} />
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

const HEADER_BG: Record<string, string> = {
    Won: 'rgba(16,185,129,.08)',
    Lost: 'rgba(239,68,68,.08)',
    Live: 'rgba(61,123,255,.10)',
    Pending: 'var(--bg-raised)',
};

interface SlipCardProps {
    slip: BetSlip;
    liveData?: LiveData;
    onDelete?: (id: number) => void;
    onCardClick?: () => void;
}

export function SlipCard({ slip, liveData = {}, onDelete, onCardClick }: SlipCardProps & { onCardClick?: () => void }) {
    const hdrBg = slip.slip_status === 'Live' ? 'rgba(61,123,255,.10)' : (HEADER_BG[slip.slip_status] ?? HEADER_BG.Pending);

    // Status border colors
    const statusBorderColor = slip.slip_status === 'Won' ? 'var(--win)'
        : slip.slip_status === 'Lost' ? 'var(--loss)'
            : slip.slip_status === 'Live' ? 'var(--accent)'
                : 'var(--text-muted)';

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
            className="flex flex-col rounded-lg overflow-hidden fade-in bg-[#1e293b] border-l-4 cursor-pointer hover:brightness-110 transition-all"
            style={{ borderLeftColor: statusBorderColor }}
            onClick={onCardClick}
        >
            {/* Header */}
            <div className="flex items-center gap-3 px-4 py-3 flex-wrap justify-between"
                style={{ background: hdrBg, borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2 flex-wrap">
                    <span className="badge text-xs" style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        color: 'var(--text-secondary)'
                    }}>
                        {slip.date_generated.split('T')[0]}
                    </span>
                    <span className="badge text-xs" style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        color: 'var(--text-bright)'
                    }}>
                        {slip.profile}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="badge text-xs" style={{
                        background: slip.slip_status === 'Live' ? 'rgba(61, 123, 255, 0.12)' :
                            slip.slip_status === 'Won' ? 'rgba(16,185,129,.15)' :
                                slip.slip_status === 'Lost' ? 'rgba(239,68,68,.15)' : 'var(--bg-raised)',
                        border: '1px solid',
                        borderColor: slip.slip_status === 'Live' ? 'var(--accent)' :
                            slip.slip_status === 'Won' ? 'var(--win)' :
                                slip.slip_status === 'Lost' ? 'var(--loss)' : 'var(--border)',
                        color: slip.slip_status === 'Live' ? 'var(--accent)' :
                            slip.slip_status === 'Won' ? 'var(--win)' :
                                slip.slip_status === 'Lost' ? 'var(--loss)' : 'var(--text-muted)',
                        fontWeight: '600'
                    }}>
                        {slip.slip_status}
                    </span>
                    {slip.slip_status === 'Pending' && onDelete && (
                        <button className="btn-icon" onClick={() => onDelete(slip.slip_id)} title="Delete slip">
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
                    const dt = leg.datetime
                        ? new Date(leg.datetime).toLocaleString('en-GB', {
                            weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                        })
                        : '';
                    // Pick border color based on leg status
                    const pickBorderColor = leg.status === 'Won' ? 'var(--win)'
                        : leg.status === 'Lost' ? 'var(--loss)'
                            : leg.status === 'Live' ? 'var(--pending)'
                                : 'var(--text-muted)';

                    return (
                        <div key={idx} className="p-2 rounded" style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
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
                                            style={{ background: 'var(--pending)' }} />
                                        <span className="relative block w-3 h-3 rounded-full"
                                            style={{ background: 'var(--pending)' }} />
                                    </span>
                                )}
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="font-display font-bold text-base px-2.5 py-1 rounded-full"
                                    style={{
                                        background: 'var(--bg-card)',
                                        border: `2px solid ${pickBorderColor}`,
                                        color: pickBorderColor
                                    }}>
                                    {leg.market} @{leg.odds.toFixed(2)}
                                </span>
                                {live && leg.status === 'Live' && (
                                    <span className="font-mono text-sm font-bold px-2 py-1 rounded"
                                        style={{ background: 'rgba(245,158,11,.12)', color: 'var(--pending)' }}>
                                        {live.minute}
                                    </span>
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
                style={{ background: 'rgba(0,0,0,0.2)' }}>
                <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-3 text-sm">
                        <span className="font-mono" style={{ color: 'var(--text-bright)' }}>
                            {slip.units}u @ {slip.total_odds.toFixed(2)}
                        </span>
                    </div>
                </div>
                {/* Calculate and show net profit client-side on the right */}
                {(() => {
                    // Stake is per slip, not per leg
                    const totalStake = slip.units;
                    const potentialReturn = slip.total_odds * slip.units;
                    let netProfit: number | null = null;
                    if (slip.slip_status === 'Won') {
                        netProfit = potentialReturn - totalStake;
                    } else if (slip.slip_status === 'Lost') {
                        netProfit = -totalStake;
                    }
                    if (netProfit !== null) {
                        const isPositive = netProfit > 0;
                        const color = isPositive ? 'var(--win)' : 'var(--loss)';
                        return (
                            <span className="font-mono font-bold text-sm" style={{ color }}>
                                {isPositive ? '+' : ''}{netProfit.toFixed(2)}
                            </span>
                        );
                    }
                    return null;
                })()}
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
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Status</p>
                            <span className="badge text-sm" style={{
                                background: slip.slip_status === 'Live' ? 'rgba(61, 123, 255, 0.12)' :
                                    slip.slip_status === 'Won' ? 'rgba(16,185,129,.15)' :
                                        slip.slip_status === 'Lost' ? 'rgba(239,68,68,.15)' : 'var(--bg-raised)',
                                color: slip.slip_status === 'Live' ? 'var(--accent)' :
                                    slip.slip_status === 'Won' ? 'var(--win)' :
                                        slip.slip_status === 'Lost' ? 'var(--loss)' : 'var(--text-muted)'
                            }}>
                                {slip.slip_status}
                            </span>
                        </div>
                        <div>
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Stake</p>
                            <p className="text-xl font-bold" style={{ color: 'var(--text-bright)' }}>
                                {slip.units}u
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Total Odds</p>
                            <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                                @{slip.total_odds.toFixed(2)}
                            </p>
                        </div>
                        {/* Show potential return or net profit in header */}
                        {(() => {
                            const totalStake = slip.units;
                            const potentialReturn = slip.total_odds * slip.units;
                            if (slip.slip_status === 'Pending') {
                                return (
                                    <div className="text-right">
                                        <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Potential Return</p>
                                        <p className="text-2xl font-bold" style={{ color: 'var(--accent)' }}>
                                            {potentialReturn.toFixed(2)}u
                                        </p>
                                    </div>
                                );
                            } else if (slip.slip_status === 'Won') {
                                const netProfit = potentialReturn - totalStake;
                                return (
                                    <div className="text-right">
                                        <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Profit</p>
                                        <p className="text-2xl font-bold" style={{ color: 'var(--win)' }}>
                                            +{netProfit.toFixed(2)}u
                                        </p>
                                    </div>
                                );
                            } else if (slip.slip_status === 'Lost') {
                                const netProfit = -totalStake;
                                return (
                                    <div className="text-right">
                                        <p className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Loss</p>
                                        <p className="text-2xl font-bold" style={{ color: 'var(--loss)' }}>
                                            {netProfit.toFixed(2)}u
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
                        const dt = leg.datetime
                            ? new Date(leg.datetime).toLocaleString('en-GB', {
                                weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                            })
                            : '';
                        const legStatusColor = leg.status === 'Won' ? 'var(--win)'
                            : leg.status === 'Lost' ? 'var(--loss)'
                                : leg.status === 'Live' ? 'var(--pending)'
                                    : 'var(--text-muted)';
                        const legStatusIcon = leg.status === 'Won' ? '✓'
                            : leg.status === 'Lost' ? '✗'
                                : leg.status === 'Live' ? '●'
                                    : '◷';

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
                                                    color: legStatusColor
                                                }}>
                                                {leg.market} @{leg.odds.toFixed(2)}
                                            </span>
                                            {live && leg.status === 'Live' && (
                                                <div className="flex flex-col items-center gap-1">
                                                    <span className="font-mono text-sm font-bold px-3 py-1 rounded"
                                                        style={{ background: 'rgba(245,158,11,.12)', color: 'var(--pending)' }}>
                                                        {live.score}
                                                    </span>
                                                    <span className="font-mono text-lg font-bold" style={{ color: 'var(--pending)' }}>
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
