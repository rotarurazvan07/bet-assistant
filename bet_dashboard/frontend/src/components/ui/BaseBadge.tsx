import type { ReactNode } from 'react';

export interface BaseBadgeProps {
    status?: 'success' | 'warning' | 'error' | 'info' | 'default';
    children: ReactNode;
    className?: string;
    icon?: ReactNode;
}

export function BaseBadge({
    status = 'default',
    children,
    className = '',
    icon
}: BaseBadgeProps) {
    // Determine badge styling based on status
    const getStatusStyles = () => {
        switch (status) {
            case 'success':
                return {
                    background: 'var(--win-bg)',
                    color: 'var(--win)',
                    border: '1px solid var(--win)'
                };
            case 'warning':
                return {
                    background: 'var(--pend-bg)',
                    color: 'var(--pending)',
                    border: '1px solid var(--pending)'
                };
            case 'error':
                return {
                    background: 'var(--loss-bg)',
                    color: 'var(--loss)',
                    border: '1px solid var(--loss)'
                };
            case 'info':
                return {
                    background: 'var(--accent-glow)',
                    color: 'var(--accent)',
                    border: '1px solid var(--accent)'
                };
            default:
                return {
                    background: 'rgba(255,255,255,0.05)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border)'
                };
        }
    };

    const statusStyles = getStatusStyles();

    const badgeStyles = {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 'var(--radius-sm)',
        padding: '2px 8px',
        fontSize: '12px',
        fontWeight: '600',
        ...statusStyles,
    };

    return (
        <span
            className={`badge ${className}`}
            style={badgeStyles}
        >
            {icon && (
                <span style={{ marginRight: '4px' }}>
                    {icon}
                </span>
            )}
            {children}
        </span>
    );
}