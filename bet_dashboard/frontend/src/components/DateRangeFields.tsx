interface Props {
    dateFrom: string;
    dateTo: string;
    onDateFromChange: (value: string) => void;
    onDateToChange: (value: string) => void;
    compact?: boolean;
}

export default function DateRangeFields({
    dateFrom,
    dateTo,
    onDateFromChange,
    onDateToChange,
    compact = false,
}: Props) {
    return (
        <div className={compact ? 'flex flex-wrap items-center gap-3' : 'flex flex-col gap-2'}>
            <label
                className={`text-xs font-mono ${compact ? 'whitespace-nowrap' : ''}`}
                style={{ color: 'var(--text-secondary)' }}
                htmlFor={compact ? 'page-date-from-compact' : 'page-date-from'}
            >
                Date range
            </label>
            <div className="flex items-center gap-2">
                <input
                    id={compact ? 'page-date-from-compact' : 'page-date-from'}
                    aria-label="Date from"
                    className={`field min-w-0 ${compact ? 'w-36' : 'w-full flex-1'}`}
                    type="date"
                    value={dateFrom}
                    onChange={event => onDateFromChange(event.target.value)}
                />
                <span aria-hidden="true" className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>to</span>
                <input
                    aria-label="Date to"
                    className={`field min-w-0 ${compact ? 'w-36' : 'w-full flex-1'}`}
                    type="date"
                    value={dateTo}
                    onChange={event => onDateToChange(event.target.value)}
                />
            </div>
        </div>
    );
}
