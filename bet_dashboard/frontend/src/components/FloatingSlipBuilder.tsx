import { useMemo } from 'react';
import { createPortal } from 'react-dom';
import type { CandidateLeg } from '../types';
import SlipBuilderPanel from './SlipBuilderPanel';

interface Props {
    legs: CandidateLeg[];
    onRemoveLeg: (index: number) => void;
    onSubmit: (units: number) => void;
    isMinimized: boolean;
    onToggleMinimize: () => void;
}

export default function FloatingSlipBuilder({ legs, onRemoveLeg, onSubmit, isMinimized, onToggleMinimize }: Props) {
    const totalOdds = useMemo(() => {
        const valid = legs.filter(l => l.odds != null && l.odds > 0).map(l => l.odds!);
        if (valid.length === 0) return 0;
        return valid.reduce((a, b) => a * b, 1);
    }, [legs]);

    if (isMinimized) {
        return createPortal(
            <div className="floating-slip-minimized" onClick={onToggleMinimize}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)' }}>
                        {legs.length} leg{legs.length !== 1 ? 's' : ''}
                    </span>
                    {totalOdds > 0 && (
                        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                            • {totalOdds.toFixed(2)}
                        </span>
                    )}
                    <span style={{ fontSize: 14, color: 'var(--text-muted)', marginLeft: 4 }}>▲</span>
                </span>
            </div>,
            document.body
        );
    }

    return createPortal(
        <div className="floating-slip-panel card">
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                <SlipBuilderPanel legs={legs} onRemoveLeg={onRemoveLeg} onSubmit={onSubmit} onToggleMinimize={onToggleMinimize} />
            </div>
        </div>,
        document.body
    );
}
