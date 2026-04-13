import type { ReactNode } from 'react';

export interface BaseDataRowProps {
    label?: string;
    value?: ReactNode;
    status?: 'success' | 'warning' | 'error' | 'info' | 'default';
    actions?: ReactNode;
    className?: string;
    children?: ReactNode;
    // For table row support
    isTableRow?: boolean;
    cells?: ReactNode[];
    // Additional props for styling and event handlers
    style?: React.CSSProperties;
    onMouseEnter?: React.MouseEventHandler<HTMLTableRowElement>;
    onMouseLeave?: React.MouseEventHandler<HTMLTableRowElement>;
}

export function BaseDataRow({
    label,
    value,
    status = 'default',
    actions,
    className = '',
    children,
    isTableRow = false,
    cells = [],
    style,
    onMouseEnter,
    onMouseLeave
}: BaseDataRowProps) {
    // Determine row styling based on status
    const getStatusStyles = () => {
        switch (status) {
            case 'success':
                return { color: 'var(--win)' };
            case 'warning':
                return { color: 'var(--pending)' };
            case 'error':
                return { color: 'var(--loss)' };
            case 'info':
                return { color: 'var(--accent)' };
            default:
                return { color: 'var(--text-primary)' };
        }
    };

    const statusStyles = getStatusStyles();

    // If this is a table row, render table cells
    if (isTableRow) {
        return (
            <tr
                className={className}
                style={style}
                onMouseEnter={onMouseEnter}
                onMouseLeave={onMouseLeave}
            >
                {cells}
                {children}
            </tr>
        );
    }

    const rowStyles = {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 0',
        borderBottom: '1px solid var(--border)',
    };

    const labelStyles = {
        fontSize: '14px',
        color: 'var(--text-secondary)',
        flex: '1',
    };

    const valueStyles = {
        fontSize: '14px',
        fontWeight: '500',
        ...statusStyles,
    };

    const actionsStyles = {
        marginLeft: '8px',
    };

    return (
        <div className={`data-row ${className}`} style={rowStyles}>
            <span style={labelStyles}>{label}</span>
            <span style={valueStyles}>{value}</span>
            {actions && (
                <div style={actionsStyles}>
                    {actions}
                </div>
            )}
        </div>
    );
}