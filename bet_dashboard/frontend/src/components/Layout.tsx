import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { pullDb } from '../api/data';

const LINKS = [
    { to: '/', label: 'Betting Tips' },
    { to: '/builder', label: 'Smart Builder' },
    { to: '/slips', label: 'Slips' },
    { to: '/analytics', label: 'Analytics' },
    { to: '/services', label: 'Services' },
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

export default function Layout({ children, lastPull, onRefresh, onMatchesUpdated }: Props) {
    const location = useLocation();
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [pulling, setPulling] = useState(false);

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
                <div className="max-w-[1480px] mx-auto px-5 h-13 flex items-center justify-between gap-8">

                    {/* Brand */}
                    <div className="flex items-center gap-2.5 shrink-0 select-none">
                        <span className="text-lg" style={{ color: 'var(--accent)' }}>◈</span>
                        <span className="font-display font-bold text-[15px] tracking-tight"
                            style={{ color: 'var(--text-bright)' }}>
                            Bet<span style={{ color: 'var(--accent)' }}>Assistant</span>
                        </span>
                    </div>

                    {/* Nav */}
                    <nav className="flex items-center gap-6 flex-1">
                        {LINKS.map(({ to, label }) => (
                            <NavLink
                                key={to} to={to} end={to === '/'}
                                className={({ isActive }) =>
                                    `nav-link relative py-3.5 ${isActive ? 'active' : ''}`
                                }
                            >
                                {label}
                            </NavLink>
                        ))}
                    </nav>

                    {/* Right controls */}
                    <div className="flex items-center gap-3 shrink-0">
                        {lastPull && (
                            <span className="text-[11px] font-mono hidden md:block"
                                style={{ color: 'var(--text-muted)' }}>
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
                <div style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}
                    className="sticky top-[52px] z-40">
                    <div className="max-w-[1480px] mx-auto px-5 py-2.5 flex items-center gap-6">

                        {/* Date range - GLOBAL FILTER */}
                        <div className="flex flex-col gap-1">
                            <span className="text-[10px] font-mono tracking-widest uppercase"
                                style={{ color: 'var(--text-muted)' }}>Time Horizon</span>
                            <div className="flex items-center gap-2">
                                <input className="field w-36" type="date"
                                    value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
                                <span style={{ color: 'var(--text-muted)' }} className="text-xs">→</span>
                                <input className="field w-36" type="date"
                                    value={dateTo} onChange={e => setDateTo(e.target.value)} />
                            </div>
                        </div>

                    </div>
                </div>
            )}

            {/* ── Page content ──────────────────────────────────────────────────── */}
            <main className="flex-1 max-w-[1480px] mx-auto w-full px-5 py-6">
                {children({ dateFrom, dateTo })}
            </main>
        </div>
    );
}
