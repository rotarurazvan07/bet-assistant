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
                <div className="w-full px-2 h-13 flex items-center justify-between gap-8">

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
