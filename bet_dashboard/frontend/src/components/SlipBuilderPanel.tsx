import { useMemo, useState } from 'react';
import type { CandidateLeg } from '../types';
import { BaseCard } from './ui/BaseCard';
import { BaseBadge } from './ui/BaseBadge';

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
        <BaseCard
            className="h-full flex flex-col"
            contentClassName="flex-1 flex flex-col min-h-0"
            header={
                <div>
                    <h2 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                        Slip Builder
                    </h2>
                    <p className="text-sm font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                        {legs.length} leg{legs.length !== 1 ? 's' : ''} selected
                    </p>
                </div>
            }
            footer={legs.length > 0 ? (
                <div className="px-4 py-3 border-t flex-shrink-0" style={{ borderColor: 'var(--border)' }}>
                    {/* Summary stats */}
                    <div className="space-y-1.5 mb-3">
                        <div className="flex justify-between items-center">
                            <span className="text-base font-mono" style={{ color: 'var(--text-secondary)' }}>Total Odds</span>
                            <span className="text-base font-mono font-bold" style={{ color: 'var(--text-bright)' }}>
                                {totalOdds.toFixed(2)}
                            </span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-base font-mono" style={{ color: 'var(--text-secondary)' }}>Units</span>
                            <input
                                type="number"
                                min={1}
                                value={units}
                                onChange={e => setUnits(Math.max(1, parseInt(e.target.value || '1', 10)))}
                                className="w-20 px-3 py-2 rounded text-base font-mono text-center"
                                style={{
                                    background: 'var(--bg-input)',
                                    border: '1px solid var(--border-strong)',
                                    color: 'var(--text-primary)',
                                }}
                            />
                        </div>
                        <div className="flex justify-between items-center pt-1.5 border-t" style={{ borderColor: 'var(--border)' }}>
                            <span className="text-sm font-mono" style={{ color: 'var(--text-secondary)' }}>Potential Win</span>
                            <span className="text-sm font-mono font-bold" style={{ color: 'var(--accent)' }}>
                                {potentialWin.toFixed(2)}
                            </span>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={handleSubmit}
                        className="w-full px-4 py-3 rounded text-base font-mono uppercase tracking-wider transition-opacity hover:opacity-90"
                        style={{
                            background: 'var(--accent)',
                            color: 'var(--text-bright)',
                        }}
                    >
                        Add Slip
                    </button>
                </div>
            ) : null}
        >
            {/* Selections - scrollable */}
            <div className="flex-1 overflow-y-auto px-1 -mx-1 space-y-2 min-h-0">
                {legs.length === 0 ? (
                    <div className="h-full flex items-center justify-center p-8">
                        <div className="text-center">
                            <p className="text-base" style={{ color: 'var(--text-secondary)' }}>
                                No legs selected.
                            </p>
                            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                                Click a market cell in the table to add a leg.
                            </p>
                        </div>
                    </div>
                ) : (
                    legs.map((leg, idx) => (
                        <BaseCard
                            key={idx}
                            className="mb-2"
                        >
                            <div className="flex items-start justify-between gap-2 mb-2">
                                <div className="flex-1 min-w-0">
                                    <p className="font-sans font-bold text-[15px]" style={{ color: 'var(--text-bright)' }}>
                                        {leg.match_name}
                                    </p>
                                    <p className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                        {leg.datetime ? new Date(leg.datetime).toLocaleString('en-GB', {
                                            weekday: 'short',
                                            day: '2-digit',
                                            month: 'short',
                                            hour: '2-digit',
                                            minute: '2-digit'
                                        }) : 'TBD'}
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => onRemoveLeg(idx)}
                                    className="btn-icon shrink-0"
                                    style={{ color: 'var(--text-secondary)' }}
                                    aria-label={`Remove ${leg.match_name} - ${leg.market}`}
                                >
                                    <span style={{ fontSize: 12 }}>✕</span>
                                </button>
                            </div>

                            <div className="flex items-center justify-between mb-2">
                                <BaseBadge status="info">
                                    {leg.market} @{leg.odds != null ? leg.odds.toFixed(2) : '—'}
                                </BaseBadge>
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                                    Consensus: {leg.consensus.toFixed(0)}% · Sources: {leg.sources}
                                </span>
                            </div>
                        </BaseCard>
                    ))
                )}
            </div>
        </BaseCard>
    );
}
