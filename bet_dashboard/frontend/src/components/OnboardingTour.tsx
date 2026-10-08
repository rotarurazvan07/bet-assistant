import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, Backdrop, Button, MobileStepper, Paper, Snackbar, useMediaQuery } from '@mui/material';
import Unstable_TrapFocus from '@mui/material/Unstable_TrapFocus';
import { TOUR_DONE_KEY } from './tourStorage';

const STEPS = [
    {
        route: '/',
        title: 'Find value bets',
        body: 'Use filters, click a cell, and add legs in the floating slip panel.',
        targets: ['[data-tour="discover-filters"]', '[role="button"][aria-label^="Select"]', '[data-slip-panel]', '.floating-slip-minimized'],
    },
    {
        route: '/builder',
        title: 'Create your strategy',
        body: 'Pick a preset, watch Live Preview, then save your profile.',
        targets: ['[data-profile-chip]', 'input[placeholder="profile name"]', '[data-tour="build-preview"]', '[data-tour="build-save"]'],
    },
    {
        route: '/slips',
        title: 'Monitor performance',
        body: 'Validate results, generate slips, and sort the list.',
        targets: ['[data-tour="track-validate"]', '[data-tour="track-generate"]', '[data-tour="track-list"]'],
    },
] as const;

function readDone(): boolean {
    try {
        return localStorage.getItem(TOUR_DONE_KEY) === '1';
    } catch {
        return false;
    }
}

function persistDone(): void {
    try {
        localStorage.setItem(TOUR_DONE_KEY, '1');
    } catch {
        // Ignore quota / private-mode failures (#39 pattern).
    }
}

function firstTarget(selectors: readonly string[]): HTMLElement | null {
    for (const sel of selectors) {
        const el = document.querySelector<HTMLElement>(sel);
        if (el) return el;
    }
    return null;
}

const ALERT_SX = {
    color: 'var(--text-muted-strong)',
    // AC-06: contrast on the message node (#38 CR-FAIL).
    '& .MuiAlert-message': { color: 'var(--text-secondary)' },
    backgroundColor: 'color-mix(in srgb, var(--bg-card) 82%, var(--win) 18%)',
    borderColor: 'var(--win-border)',
    '& .MuiAlert-icon': { color: 'var(--win)' },
} as const;

/** Satisfies: AC-06 */
export function FirstSlipToast({ open, onClose }: { open: boolean; onClose: () => void }) {
    const isMobile = useMediaQuery('(max-width:767.95px)');
    return (
        <Snackbar
            open={open}
            autoHideDuration={4000}
            onClose={onClose}
            anchorOrigin={{ vertical: isMobile ? 'top' : 'bottom', horizontal: 'center' }}
        >
            <Alert role="alert" severity="success" variant="outlined" onClose={onClose} sx={ALERT_SX}>
                🎉 First slip submitted! Check Track to monitor.
            </Alert>
        </Snackbar>
    );
}

/** Satisfies: AC-01, AC-02, AC-03, AC-04, AC-07 */
export default function OnboardingTour() {
    const navigate = useNavigate();
    const location = useLocation();
    const [open, setOpen] = useState(() => !readDone());
    const [step, setStep] = useState(0);

    const finish = useCallback(() => {
        persistDone();
        setOpen(false);
    }, []);

    useEffect(() => {
        if (!open) return;
        const route = STEPS[step].route;
        if (location.pathname !== route) navigate(route);
    }, [open, step, location.pathname, navigate]);

    useEffect(() => {
        if (!open) return;
        const paint = () => {
            document.querySelectorAll('.tour-spotlight').forEach((el) => el.classList.remove('tour-spotlight'));
            firstTarget(STEPS[step].targets)?.classList.add('tour-spotlight');
        };
        paint();
        const id = requestAnimationFrame(paint);
        window.addEventListener('resize', paint);
        return () => {
            cancelAnimationFrame(id);
            window.removeEventListener('resize', paint);
            document.querySelectorAll('.tour-spotlight').forEach((el) => el.classList.remove('tour-spotlight'));
        };
    }, [open, step, location.pathname]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key !== 'Escape') return;
            // AC-07: swallow Esc so #39 slip minimize does not fire.
            e.stopPropagation();
            e.preventDefault();
            finish();
        };
        window.addEventListener('keydown', onKey, true);
        return () => window.removeEventListener('keydown', onKey, true);
    }, [open, finish]);

    if (!open) return null;

    const last = step === STEPS.length - 1;
    const title = STEPS[step].title;

    return (
        <>
            <Backdrop open sx={{ zIndex: 1300, backgroundColor: 'rgba(0,0,0,0.45)' }} />
            <Unstable_TrapFocus open>
                <Paper
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="tour-title"
                    tabIndex={-1}
                    sx={{
                        position: 'fixed',
                        zIndex: 1400,
                        bottom: 24,
                        left: '50%',
                        transform: 'translateX(-50%)',
                        width: 'min(420px, calc(100vw - 24px))',
                        p: 2,
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                    }}
                >
                    <h2 id="tour-title" className="font-display font-bold text-lg" style={{ color: 'var(--text-bright)', margin: 0 }}>
                        {title}
                    </h2>
                    <p style={{ color: 'var(--text-secondary)', margin: '8px 0 12px', fontSize: 14 }}>
                        {STEPS[step].body}
                    </p>
                    {/* AC-07: dots are decorative; announce step via live text. */}
                    <span style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }} aria-live="polite">{`Step ${step + 1} of 3`}</span>
                    <MobileStepper
                        variant="dots"
                        steps={3}
                        activeStep={step}
                        position="static"
                        nextButton={<span />}
                        backButton={<span />}
                        aria-hidden="true"
                        sx={{ background: 'transparent', justifyContent: 'center' }}
                    />
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
                        <Button type="button" onClick={finish} sx={{ color: 'var(--text-secondary)' }}>Skip</Button>
                        <Button type="button" disabled={step === 0} onClick={() => setStep((s) => s - 1)} sx={{ color: 'var(--text-secondary)' }}>Back</Button>
                        <Button type="button" onClick={() => (last ? finish() : setStep((s) => s + 1))} sx={{ color: 'var(--text-bright)' }}>
                            {last ? 'Done' : 'Next'}
                        </Button>
                    </div>
                </Paper>
            </Unstable_TrapFocus>
        </>
    );
}
