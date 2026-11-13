import { useState, useId } from 'react';
import { SectionHeader } from '../ui';

interface AnalyticsSectionProps {
    title: string;
    icon?: string;
    quickview: React.ReactNode;
    detail: React.ReactNode;
    defaultExpanded?: boolean;
}

export default function AnalyticsSection({
    title,
    icon,
    quickview,
    detail,
    defaultExpanded = false,
}: AnalyticsSectionProps) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const detailId = useId();

    return (
        <section className="mb-10" aria-label={title}>
            <div className="flex items-center justify-between mb-3">
                <SectionHeader icon={icon} title={title} />
                <button
                    type="button"
                    onClick={() => setIsExpanded(prev => !prev)}
                    aria-expanded={isExpanded}
                    aria-controls={detailId}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md font-mono text-[11px] tracking-wider uppercase transition-colors"
                    style={{
                        background: 'var(--bg-raised)',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border)',
                    }}
                    onMouseEnter={e => {
                        e.currentTarget.style.color = 'var(--text-bright)';
                        e.currentTarget.style.borderColor = 'var(--border-strong)';
                    }}
                    onMouseLeave={e => {
                        e.currentTarget.style.color = 'var(--text-secondary)';
                        e.currentTarget.style.borderColor = 'var(--border)';
                    }}
                >
                    <span>{isExpanded ? 'View less' : 'View more'}</span>
                    <span
                        className="inline-block transition-transform duration-200"
                        style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
                    >
                        ▾
                    </span>
                </button>
            </div>

            {/* Quickview (always visible) */}
            <div className="mb-4">
                {quickview}
            </div>

            {/* Expandable Detail (CSS slide transition) */}
            <div
                id={detailId}
                className="grid transition-all duration-300 ease-in-out"
                style={{
                    gridTemplateRows: isExpanded ? '1fr' : '0fr',
                }}
            >
                <div className="overflow-hidden">
                    <div className="pt-2">
                        {detail}
                    </div>
                </div>
            </div>
        </section>
    );
}
