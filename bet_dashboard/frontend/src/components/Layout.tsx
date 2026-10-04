import { useState, useEffect, Fragment } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { pullDb } from '../api/data';

// AC-01/AC-02 (issue #36): workflow-grouped nav — Core → Insights → System;
// routes unchanged, labels renamed to action verbs.
const NAV_GROUPS = [
    {
        id: 'core',
        caption: 'Core',
        links: [
            { to: '/', label: 'Discover' },
            { to: '/builder', label: 'Build' },
            { to: '/slips', label: 'Track' },
        ],
    },
    {
        id: 'insights',
        caption: 'Insights',
        links: [{ to: '/analytics', label: 'Analytics' }],
    },
    {
        id: 'system',
        caption: 'System',
        links: [
            { to: '/services', label: 'Services' },
            { to: '/odds-alert', label: 'Odds Alert' },
        ],
    },
];

export interface GlobalFilters {
    dateFrom: string;
    dateTo: string;
}

interface Props {
    children: (filters: GlobalFilters) => React.ReactNode;
    lastPull: string;
    onRefresh: () => void;
    onMatchesUpdated: () => void;
}

const STORAGE_KEY = 'bet-assistant-time-horizon';

function getInitialDate(key: string): string {
    if (typeof window === 'undefined') return '';
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            const parsed = JSON.parse(stored);
            return parsed[key] || '';
        }
    } catch {
        // Ignore parse errors
    }
    return '';
}

function saveDates(dateFrom: string, dateTo: string) {
    if (typeof window === 'undefined') return;
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ dateFrom, dateTo }));
    } catch {
        // Ignore storage errors
    }
}

export default function Layout({ children, lastPull, onRefresh, onMatchesUpdated }: Props) {
    const location = useLocation();
    const [dateFrom, setDateFrom] = useState(() => getInitialDate('dateFrom'));
    const [dateTo, setDateTo] = useState(() => getInitialDate('dateTo'));
    const [pulling, setPulling] = useState(false);

    useEffect(() => {
        saveDates(dateFrom, dateTo);
    }, [dateFrom, dateTo]);

    const showFilters = location.pathname === '/' ||
        location.pathname === '/builder' ||
        location.pathname === '/slips' ||
        location.pathname === '/analytics';

    async function handlePull() {
        setPulling(true);
        try {
            const result = await pullDb().catch(() => null);
            if (result?.status === 'ok') {
                onMatchesUpdated();
            }
        } catch {
            // Ignore pull errors
        } finally {
            setPulling(false);
        }
    }

    async function handleRefresh() {
        try {
            onRefresh();
        } catch {
            // Ignore refresh errors
        }
    }

    return (
        <div className="min-h-screen flex flex-col" style={{ background: 'var(--bg-base)' }}>

            {/* ── Top bar ──────────────────────────────────────────────────────── */}
            <header style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}
                className="sticky top-0 z-50">
                <div className="w-full px-2 h-13 flex items-center justify-between gap-8">

                    {/* Brand */}
                    <div className="flex items-center gap-2.5 shrink-0 select-none">
                        <span className="text-lg" style={{ color: 'var(--accent)' }}>◈</span>
                        <span className="font-display font-bold text-[15px] tracking-tight"
                            style={{ color: 'var(--text-bright)' }}>
                            Bet<span style={{ color: 'var(--accent)' }}>Assistant</span>
                        </span>
                    </div>

                    {/* Nav — workflow groups (issue #36): Core → Insights → System.
                        Anchors stay flat in DOM order inside each group so keyboard
                        Tab order equals visual order (AC-04). */}
                    <nav className="flex items-center gap-5 flex-1" aria-label="Primary">
                        {NAV_GROUPS.map((group, groupIndex) => (
                            <Fragment key={group.id}>
                                {groupIndex > 0 && (
                                    <span className="nav-separator" aria-hidden="true" />
                                )}
                                <div className="flex flex-col justify-center" role="group" aria-label={group.caption}>
                                    {/* AC-03: micro-caption above group (SM-approved) */}
                                    <span
                                        className="nav-caption"
                                        aria-hidden="true"
                                    >
                                        {group.caption}
                                    </span>
                                    <div className="flex items-center gap-3">
                                        {group.links.map(({ to, label }) => (
                                            <NavLink
                                                key={to} to={to} end={to === '/'}
                                                className={({ isActive }) =>
                                                    `nav-link relative py-2.5 ${isActive ? 'active' : ''}`
                                                }
                                            >
                                                {label}
                                            </NavLink>
                                        ))}
                                    </div>
                                </div>
                            </Fragment>
                        ))}
                    </nav>

                    {/* Right controls */}
                    <div className="flex items-center gap-3 shrink-0">
                        {lastPull && (
                            <span className="text-[11px] font-mono hidden md:block"
                                style={{ color: 'var(--text-secondary)' }}>
                                {lastPull}
                            </span>
                        )}
                        <button className="btn-ghost" onClick={handleRefresh}>
                            Refresh
                        </button>
                        <button className="btn-primary" onClick={handlePull} disabled={pulling}>
                            {pulling ? 'Pulling…' : '↓ Pull Update'}
                        </button>
                    </div>
                </div>
            </header>

            {/* ── Global filters ────────────────────────────────────────────────── */}
            {showFilters && (
                <div style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
                    <div className="w-full px-2 py-3 flex flex-col items-center gap-2">

                        {/* Label centered on top */}
                        <span className="text-[10px] font-mono tracking-widest uppercase"
                            style={{ color: 'var(--text-secondary)' }}>Time Horizon</span>

                        {/* Date pickers row */}
                        <div className="flex items-center gap-3">
                            <input className="field w-44" type="date"
                                value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
                            <span style={{ color: 'var(--text-secondary)' }} className="text-xs font-mono">→</span>
                            <input className="field w-44" type="date"
                                value={dateTo} onChange={e => setDateTo(e.target.value)} />
                        </div>

                    </div>
                </div>
            )}

            {/* ── Page content — Fills available width ──────────────────────────── */}
            <main className="flex-1 w-full px-4 lg:px-8 2xl:px-12 py-6 max-w-[2400px] mx-auto transition-all duration-300">
                {children({ dateFrom, dateTo })}
            </main>
        </div>
    );
}
