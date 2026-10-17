import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMediaQuery } from '@mui/material';
import Unstable_TrapFocus from '@mui/material/Unstable_TrapFocus';
import type { CandidateLeg } from '../types';
import SlipBuilderPanel from './SlipBuilderPanel';
import { subscribeTourOpen } from './tourStorage';

interface Props {
    legs: CandidateLeg[];
    onRemoveLeg: (index: number) => void;
    onSubmit: (units: number) => void;
    isMinimized: boolean;
    onToggleMinimize: () => void;
    pulseToken?: number; // AC-04: incrementing nonce, not legs.length
}

// AC-08 (#39): last mobile sheet snap — '50' | '90'. Missing/invalid -> '50'.
const SNAP_KEY = 'slip-sheet-snap';

export default function FloatingSlipBuilder({ legs, onRemoveLeg, onSubmit, isMinimized, onToggleMinimize, pulseToken = 0 }: Props) {
    // AC-01: same mobile query as the #37 Filters drawer.
    const isMobile = useMediaQuery('(max-width:767.95px)');
    // AC-04: restart animation via alternating class; clear on animationend (no effect).
    const [seenPulse, setSeenPulse] = useState(0);
    const [pulseClass, setPulseClass] = useState('');
    if (pulseToken !== seenPulse) {
        setSeenPulse(pulseToken);
        setPulseClass(pulseToken ? (pulseToken % 2 ? ' slip-chrome-pulse-a' : ' slip-chrome-pulse-b') : '');
    }

    // Workstream B (#47): stand the focus trap down while the onboarding tour
    // dialog is open — two TrapFocus wrappers fighting is worse than none.
    const [tourActive, setTourActive] = useState(false);
    useEffect(() => subscribeTourOpen(setTourActive), []);

    // Workstream B (#47): remember the trigger that expanded the panel and
    // return focus to it when the panel minimizes or unmounts.
    const triggerRef = useRef<HTMLElement | null>(null);
    useEffect(() => {
        if (isMinimized) return;
        // L2: only a real control counts — activeElement is frequently <body>
        // at expand time, and "restoring" focus there is a silent no-op.
        const active = document.activeElement;
        if (active instanceof HTMLElement && active !== document.body) {
            triggerRef.current = active;
        }
        return () => {
            const trigger = triggerRef.current;
            if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
            triggerRef.current = null;
        };
    }, [isMinimized]);
    const onPulseEnd = () => setPulseClass('');
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
                className={`floating-slip-minimized${pulseClass}`}
                onAnimationEnd={onPulseEnd}
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
            className={`floating-slip-panel${pulseClass}`}
            onAnimationEnd={onPulseEnd}
            data-slip-panel
            role="dialog"
            aria-modal={false}
            aria-labelledby="slip-builder-title"
            tabIndex={-1}
            data-slip-snap={isMobile ? snap : undefined}
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
        // Workstream B (#47): also stand down while the onboarding tour dialog
        // is open so the two TrapFocus wrappers never fight for Tab order.
        <Unstable_TrapFocus open disableAutoFocus disableRestoreFocus disableEnforceFocus={tourActive}>
            {panel}
        </Unstable_TrapFocus>,
        document.body
    );
}
