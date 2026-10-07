import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMediaQuery } from '@mui/material';
import Unstable_TrapFocus from '@mui/material/Unstable_TrapFocus';
import type { CandidateLeg } from '../types';
import SlipBuilderPanel from './SlipBuilderPanel';

interface Props {
    legs: CandidateLeg[];
    onRemoveLeg: (index: number) => void;
    onSubmit: (units: number) => void;
    isMinimized: boolean;
    onToggleMinimize: () => void;
}

// AC-08 (#39): last mobile sheet snap — '50' | '90'. Missing/invalid -> '50'.
const SNAP_KEY = 'slip-sheet-snap';

export default function FloatingSlipBuilder({ legs, onRemoveLeg, onSubmit, isMinimized, onToggleMinimize }: Props) {
    // AC-01: same mobile query as the #37 Filters drawer.
    const isMobile = useMediaQuery('(max-width:767.95px)');
    const [snap, setSnap] = useState<'50' | '90'>(() => {
        try { return localStorage.getItem(SNAP_KEY) === '90' ? '90' : '50'; } catch { return '50'; }
    });
    useEffect(() => {
        if (!isMobile) return; // AC-08: this key is mobile-only
        try { localStorage.setItem(SNAP_KEY, snap); } catch { /* storage unavailable */ }
    }, [snap, isMobile]);

    const totalOdds = useMemo(() => {
        const valid = legs.filter(l => l.odds != null && l.odds > 0).map(l => l.odds!);
        if (valid.length === 0) return 0;
        return valid.reduce((a, b) => a * b, 1);
    }, [legs]);

    // SQ-3: swipe-down on the handle minimizes. No snap-physics library.
    const swipeStartY = useRef<number | null>(null);
    const onHandleTouchStart = (event: React.TouchEvent) => {
        swipeStartY.current = event.touches[0]?.clientY ?? null;
    };
    const onHandleTouchEnd = (event: React.TouchEvent) => {
        const start = swipeStartY.current;
        swipeStartY.current = null;
        if (start == null) return;
        const end = event.changedTouches[0]?.clientY;
        if (end != null && end - start > 40) onToggleMinimize();
    };

    // AC-13: minimized pill is a real keyboard button (Enter/Space expand natively).
    if (isMinimized) {
        return createPortal(
            <button
                type="button"
                className="floating-slip-minimized"
                onClick={onToggleMinimize}
                aria-label={`Open slip builder, ${legs.length} leg${legs.length !== 1 ? 's' : ''}`}
            >
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)' }}>
                        {legs.length} leg{legs.length !== 1 ? 's' : ''}
                    </span>
                    {totalOdds > 0 && (
                        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-accent)' }}>
                            • {totalOdds.toFixed(2)}
                        </span>
                    )}
                    <span style={{ fontSize: 14, color: 'var(--text-muted-strong)', marginLeft: 4 }}>▲</span>
                </span>
            </button>,
            document.body
        );
    }

    const panel = (
        <div
            className="floating-slip-panel"
            data-slip-panel
            role="dialog"
            aria-modal={false}
            aria-labelledby="slip-builder-title"
            tabIndex={-1}
            style={isMobile ? { height: snap === '90' ? '90dvh' : '50dvh' } : undefined}
        >
            {isMobile && (
                <button
                    type="button"
                    className="slip-sheet-handle"
                    aria-label="Resize slip sheet"
                    onClick={() => setSnap(s => (s === '50' ? '90' : '50'))}
                    onTouchStart={onHandleTouchStart}
                    onTouchEnd={onHandleTouchEnd}
                />
            )}
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
                <SlipBuilderPanel
                    legs={legs}
                    onRemoveLeg={onRemoveLeg}
                    onSubmit={onSubmit}
                    onToggleMinimize={onToggleMinimize}
                    isMobileSheet={isMobile}
                />
            </div>
        </div>
    );

    // AC-01/AC-03: mobile is a non-modal fixed sheet (MUI Modal/SwipeableDrawer
    // aria-hides Discover and blocks #37 Filters). Desktop stays the portal panel.
    if (isMobile) {
        return createPortal(panel, document.body);
    }

    return createPortal(
        // AC-06: MUI focus trap. autoFocus/restore stay off so focus is never
        // stolen from the page (keeps the #36 nav keyboard walk intact).
        <Unstable_TrapFocus open disableAutoFocus disableRestoreFocus>
            {panel}
        </Unstable_TrapFocus>,
        document.body
    );
}
