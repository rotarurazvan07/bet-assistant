import { useState, Fragment } from 'react';
import { NavLink } from 'react-router-dom';
import { pullDb } from '../api/data';
import OnboardingTour from './OnboardingTour';

// Navigation groups retain visual separators; routes and labels stay unchanged.
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

interface Props {
    children: React.ReactNode;
    lastPull: string;
    onMatchesUpdated: () => void;
}

export default function Layout({ children, lastPull, onMatchesUpdated }: Props) {
    const [pulling, setPulling] = useState(false);
    const commitSha = import.meta.env.VITE_COMMIT_SHA || 'unknown';

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

                    {/* Anchors stay flat in DOM order so keyboard Tab order follows the navigation. */}
                    <nav className="flex items-center gap-5 flex-1" aria-label="Primary">
                        {NAV_GROUPS.map((group, groupIndex) => (
                            <Fragment key={group.id}>
                                {groupIndex > 0 && (
                                    <span className="nav-separator" aria-hidden="true" />
                                )}
                                <div className="flex items-center gap-6" role="group" aria-label={group.caption}>
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
                        <button className="btn-primary" onClick={handlePull} disabled={pulling}>
                            {pulling ? 'Pulling matches…' : '↓ Pull Matches'}
                        </button>
                        <span
                            className="border-l pl-3 text-[10px] font-mono whitespace-nowrap"
                            style={{ borderColor: 'var(--border)', color: 'var(--text-secondary)' }}
                            title={`Commit ${commitSha}`}
                            aria-label={`Build ${commitSha.slice(0, 7)}`}
                        >
                            Build {commitSha.slice(0, 7)}
                        </span>
                    </div>
                </div>
            </header>

            {/* ── Page content — Fills available width ──────────────────────────── */}
            <main className="flex-1 w-full px-4 lg:px-8 2xl:px-12 py-6 max-w-[2400px] mx-auto transition-all duration-300">
                {children}
            </main>
            {/* Mount the first-visit tour at the router level. */}
            <OnboardingTour />
        </div>
    );
}
