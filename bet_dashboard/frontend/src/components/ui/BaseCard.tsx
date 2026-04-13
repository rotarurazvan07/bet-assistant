import type { ReactNode } from 'react';

export interface BaseCardProps {
    header?: ReactNode;
    footer?: ReactNode;
    status?: 'default' | 'success' | 'warning' | 'error' | 'info';
    className?: string;
    contentClassName?: string;
    children: ReactNode;
    onClick?: () => void;
}

export function BaseCard({
    header,
    footer,
    status,
    className = '',
    contentClassName = '',
    children,
    onClick
}: BaseCardProps) {
    // Determine card styling based on variant and status
    const getStatusStyles = () => {
        switch (status) {
            case 'success':
                return { border: '1px solid var(--win)', background: 'var(--win-bg)' };
            case 'warning':
                return { border: '1px solid var(--pending)', background: 'var(--pend-bg)' };
            case 'error':
                return { border: '1px solid var(--loss)', background: 'var(--loss-bg)' };
            case 'info':
                return { border: '1px solid var(--accent)', background: 'var(--accent-glow)' };
            default:
                return { border: '1px solid var(--border)', background: 'var(--bg-card)' };
        }
    };

    const statusStyles = getStatusStyles();

    // Card base styles
    const cardStyles = {
        borderRadius: 'var(--radius-md)',
        padding: '16px',
        ...statusStyles,
    };

    return (
        <div
            className={`card ${className}`}
            style={cardStyles}
            onClick={onClick}
        >
            {header && (
                <div className="card-header shrink-0" style={{ marginBottom: '12px' }}>
                    {header}
                </div>
            )}
            <div className={`card-content ${contentClassName}`}>
                {children}
            </div>
            {footer && (
                <div className="card-footer shrink-0" style={{ marginTop: '12px' }}>
                    {footer}
                </div>
            )}
        </div>
    );
}