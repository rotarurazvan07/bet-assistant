import { useMemo, useState } from 'react';
import type { CandidateLeg } from '../types';

interface Props {
    legs: CandidateLeg[];
    onRemoveLeg: (index: number) => void;
    onSubmit: (units: number) => void;
}

export default function SlipBuilderPanel({ legs, onRemoveLeg, onSubmit }: Props) {
    const [units, setUnits] = useState(1);

    // Calculate total odds (multiply all valid odds)
    const totalOdds = useMemo(() => {
        const validOdds = legs.filter(leg => leg.odds != null).map(leg => leg.odds!);
        if (validOdds.length === 0) return 0;
        return validOdds.reduce((product, odds) => product * odds, 1);
    }, [legs]);

    // Calculate potential win
    const potentialWin = useMemo(() => {
        return totalOdds * units;
    }, [totalOdds, units]);

    const handleSubmit = () => {
        onSubmit(units);
    };

    return (
        <div className="card flex flex-col h-full overflow-hidden"
            style={{ minWidth: 280, maxWidth: 320 }}>
            {/* Header */}
            <div className="px-4 py-3 border-b"
                style={{ borderColor: 'var(--border)' }}>
                <h2 className="font-display font-bold text-lg"
                    style={{ color: 'var(--text-bright)' }}>
                    Slip Builder
                </h2>
                <p className="text-[11px] font-mono mt-0.5"
                    style={{ color: 'var(--text-secondary)' }}>
                    {legs.length} leg{legs.length !== 1 ? 's' : ''} selected
                </p>
            </div>

            {/* Legs list */}
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
                {legs.length === 0 ? (
                    <div className="text-center py-8">
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                            No legs selected.
                        </p>
                        <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                            Click a market cell in the table to add a leg.
                        </p>
                    </div>
                ) : (
                    legs.map((leg, idx) => (
                        <div
                            key={idx}
                            className="flex items-center justify-between px-3 py-2 rounded"
                            style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}
                        >
                            <div className="flex-1 min-w-0">
                                <p className="font-sans text-sm font-medium truncate"
                                    style={{ color: 'var(--text-primary)' }}>
                                    {leg.match_name}
                                </p>
                                <p className="text-[11px] font-mono truncate"
                                    style={{ color: 'var(--text-secondary)' }}>
                                    {leg.market} · @{leg.odds != null ? leg.odds.toFixed(2) : '—'} · {leg.consensus.toFixed(0)}%
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => onRemoveLeg(idx)}
                                className="ml-2 p-1.5 rounded hover:opacity-70 transition-opacity"
                                style={{ color: 'var(--loss)' }}
                                aria-label={`Remove ${leg.match_name} - ${leg.market}`}
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M18 6L6 18M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    ))
                )}
            </div>

            {/* Footer - Summary & Actions */}
            {legs.length > 0 && (
                <div className="px-4 py-3 border-t space-y-3"
                    style={{ borderColor: 'var(--border)' }}>
                    {/* Summary stats */}
                    <div className="space-y-1.5">
                        <div className="flex justify-between items-center">
                            <span className="text-sm font-mono" style={{ color: 'var(--text-secondary)' }}>Total Odds</span>
                            <span className="text-sm font-mono font-bold" style={{ color: 'var(--text-bright)' }}>
                                {totalOdds.toFixed(2)}
                            </span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-sm font-mono" style={{ color: 'var(--text-secondary)' }}>Units</span>
                            <input
                                type="number"
                                min={1}
                                value={units}
                                onChange={e => setUnits(Math.max(1, parseInt(e.target.value || '1', 10)))}
                                className="w-20 px-2 py-1.5 rounded text-sm font-mono text-center"
                                style={{
                                    background: 'var(--bg-input)',
                                    border: '1px solid var(--border-strong)',
                                    color: 'var(--text-primary)',
                                }}
                            />
                        </div>
                        <div className="flex justify-between items-center pt-1.5 border-t"
                            style={{ borderColor: 'var(--border)' }}>
                            <span className="text-sm font-mono" style={{ color: 'var(--text-secondary)' }}>Potential Win</span>
                            <span className="text-sm font-mono font-bold" style={{ color: 'var(--accent)' }}>
                                {potentialWin.toFixed(2)}
                            </span>
                        </div>
                    </div>

                    {/* Action button */}
                    <button
                        type="button"
                        onClick={handleSubmit}
                        className="w-full px-3 py-2 rounded text-sm font-mono uppercase tracking-wider transition-opacity hover:opacity-90"
                        style={{
                            background: 'var(--accent)',
                            color: 'var(--text-bright)',
                        }}
                    >
                        Add Slip
                    </button>
                </div>
            )}
        </div>
    );
}
