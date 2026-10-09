import type { ReactNode } from 'react';

export type EmptyCta = { label: string; onClick: () => void };

type Props = {
    icon: ReactNode;
    title: string;
    steps: string[];
    primary: EmptyCta;
    secondary?: EmptyCta;
};

/** Satisfies: AC-01, AC-08, AC-11 */
export default function EmptyState({ icon, title, steps, primary, secondary }: Props) {
    return (
        <div
            data-empty-state
            role="region"
            aria-label={title}
            className="card text-center py-16 fade-in px-6"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
        >
            {/* AC-08 / AC-11: illustration is decorative */}
            <div className="flex justify-center mb-4" aria-hidden="true">
                {icon}
            </div>
            <h3 className="font-display font-bold text-lg mb-4" style={{ color: 'var(--text-bright)' }}>
                {title}
            </h3>
            {/* AC-11: numbered steps; color the text node, not only the root */}
            <ol className="mx-auto mb-6 max-w-sm text-left list-decimal list-inside space-y-1">
                {steps.map((step) => (
                    <li key={step} className="font-sans text-sm" style={{ color: 'var(--text-secondary)' }}>
                        {step}
                    </li>
                ))}
            </ol>
            <div className="flex justify-center gap-3 flex-wrap">
                <button type="button" className="btn-primary" onClick={primary.onClick}>
                    {primary.label}
                </button>
                {secondary && (
                    <button type="button" className="btn-ghost" onClick={secondary.onClick}>
                        {secondary.label}
                    </button>
                )}
            </div>
        </div>
    );
}

function SvgShell({ children }: { children: ReactNode }) {
    return (
        <svg width="72" height="72" viewBox="0 0 72 72" fill="none" aria-hidden="true" style={{ color: 'var(--accent)' }}>
            {children}
        </svg>
    );
}

export function DiscoverEmptyIcon() {
    return (
        <SvgShell>
            <circle cx="30" cy="30" r="14" stroke="currentColor" strokeWidth="3" />
            <path d="M41 41 L56 56" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
            <path d="M24 30h12M30 24v12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </SvgShell>
    );
}

export function BuildEmptyIcon() {
    return (
        <SvgShell>
            <rect x="16" y="18" width="40" height="12" rx="3" stroke="currentColor" strokeWidth="3" />
            <rect x="16" y="34" width="40" height="12" rx="3" stroke="currentColor" strokeWidth="3" />
            <rect x="16" y="50" width="28" height="8" rx="2" stroke="currentColor" strokeWidth="3" />
        </SvgShell>
    );
}

export function TrackEmptyIcon() {
    return (
        <SvgShell>
            <rect x="18" y="14" width="36" height="46" rx="4" stroke="currentColor" strokeWidth="3" />
            <path d="M26 28h20M26 38h20M26 48h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </SvgShell>
    );
}

export function AnalyticsEmptyIcon() {
    return (
        <SvgShell>
            <path d="M16 52h40" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
            <path d="M24 52V36M36 52V24M48 52V42" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
        </SvgShell>
    );
}

export function ServicesEmptyIcon() {
    return (
        <SvgShell>
            <circle cx="36" cy="36" r="10" stroke="currentColor" strokeWidth="3" />
            <path d="M36 16v8M36 48v8M16 36h8M48 36h8M21 21l6 6M45 45l6 6M51 21l-6 6M27 45l-6 6" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </SvgShell>
    );
}
