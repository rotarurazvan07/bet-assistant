import type { CandidateLeg, BetSlip, LiveData } from '../types';
import { StatusBadge } from './ui';

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
                                    <p className="font-sans font-medium text-[13px]" style={{ color: 'var(--text-bright)' }}>
                                        {leg.match_name}
                                    </p>
                                    <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>{dt}</p>
                                </div>
                                <button className="btn-icon shrink-0" onClick={() => leg.result_url && onExclude(leg.result_url)}>
                                    <span style={{ fontSize: 12 }}>✕</span>
                                </button>
                            </div>

                            <div className="flex items-center justify-between mb-2">
                                <span className="font-display font-bold text-base" style={{ color: 'var(--text-primary)' }}>
                                    {leg.market}
                                </span>
                                <span className="font-mono font-bold text-sm px-2 py-0.5 rounded"
                                    style={{ background: 'var(--accent)', color: '#fff' }}>
                                    @{leg.odds.toFixed(2)}
                                </span>
                            </div>

                            {/* Consensus bar */}
                            <div className="h-1 rounded-full mb-1.5 overflow-hidden"
                                style={{ background: 'var(--bg-card)' }}>
                                <div className="h-full rounded-full transition-all duration-300"
                                    style={{ width: consWidth, background: consColor }} />
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="font-mono text-[10px]" style={{ color: consColor }}>
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

const LEG_ICON: Record<string, string> = {
    Won: '✓', Lost: '✗', Live: '●', Pending: '◷',
};
const LEG_COLOR: Record<string, string> = {
    Won: 'var(--win)', Lost: 'var(--loss)',
    Live: 'var(--live)', Pending: 'var(--text-muted)',
};
const HEADER_BG: Record<string, string> = {
    Won: 'rgba(16,185,129,.08)',
    Lost: 'rgba(239,68,68,.08)',
    Live: 'rgba(244,63,94,.10)',
    Pending: 'var(--bg-raised)',
};

interface SlipCardProps {
    slip: BetSlip;
    liveData?: LiveData;
    onDelete?: (id: number) => void;
}

export function SlipCard({ slip, liveData = {}, onDelete }: SlipCardProps) {
    const allPending = slip.legs.every(l => l.status === 'Pending');
    const hdrBg = HEADER_BG[slip.slip_status] ?? HEADER_BG.Pending;

    return (
        <div className="card mb-3 overflow-hidden fade-in">
            {/* Header */}
            <div className="flex items-center gap-4 px-4 py-2.5 flex-wrap"
                style={{ background: hdrBg, borderBottom: '1px solid var(--border)' }}>
                <span className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                    {slip.date_generated}
                </span>
                <span className="font-mono text-[11px] uppercase tracking-wide"
                    style={{ color: 'var(--text-muted)' }}>
                    {slip.profile}
                </span>
                <span className="font-mono text-[11px]" style={{ color: 'var(--accent)' }}>
                    {slip.units}u
                </span>
                <span className="font-mono font-bold text-sm" style={{ color: 'var(--text-bright)' }}>
                    @{slip.total_odds.toFixed(2)}
                </span>
                <div className="ml-auto flex items-center gap-2">
                    <StatusBadge status={slip.slip_status} />
                    {allPending && onDelete && (
                        <button className="btn-icon" onClick={() => onDelete(slip.slip_id)} title="Delete slip">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                <line x1="10" y1="11" x2="10" y2="17"></line>
                                <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
                        </button>
                    )}
                </div>
            </div>

            {/* Legs */}
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
                {slip.legs.map((leg, i) => {
                    const live = liveData[leg.match_name];
                    const iconColor = LEG_COLOR[leg.status] ?? LEG_COLOR.Pending;
                    const dt = leg.datetime
                        ? new Date(leg.datetime).toLocaleString('en-GB', {
                            weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                        })
                        : '';
                    return (
                        <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                            <span className="text-sm w-4 shrink-0 text-center font-mono"
                                style={{ color: iconColor }}>
                                {LEG_ICON[leg.status] ?? '◷'}
                            </span>
                            <div className="flex-1 min-w-0">
                                {leg.result_url
                                    ? <a href={leg.result_url} target="_blank" rel="noreferrer"
                                        className="font-sans text-[13px] hover:underline"
                                        style={{ color: 'var(--text-accent)' }}>{leg.match_name}</a>
                                    : <span className="font-sans text-[13px]" style={{ color: 'var(--text-primary)' }}>
                                        {leg.match_name}
                                    </span>
                                }
                                <div className="flex items-center gap-2 mt-0.5">
                                    <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{dt}</span>
                                    {live && leg.status === 'Live' && (
                                        <>
                                            <span className="font-mono text-[10px] font-bold px-1 rounded"
                                                style={{ background: 'var(--live-bg)', color: 'var(--live)' }}>
                                                {live.score}
                                            </span>
                                            <span className="font-mono text-[10px]" style={{ color: 'var(--live)' }}>
                                                {live.minute}
                                            </span>
                                        </>
                                    )}
                                </div>
                            </div>
                            <span className="font-sans text-[12px] shrink-0" style={{ color: 'var(--text-secondary)' }}>
                                {leg.market}
                            </span>
                            <span className="font-mono font-bold text-[12px] shrink-0" style={{ color: 'var(--text-bright)' }}>
                                @{leg.odds.toFixed(2)}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
