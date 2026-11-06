import { useEffect, useState } from 'react';

export interface DateRange {
    dateFrom: string;
    dateTo: string;
}

function readDateRange(storageKey: string): DateRange {
    try {
        const saved = localStorage.getItem(storageKey);
        if (!saved) return { dateFrom: '', dateTo: '' };
        const parsed = JSON.parse(saved) as Partial<DateRange>;
        return {
            dateFrom: typeof parsed.dateFrom === 'string' ? parsed.dateFrom : '',
            dateTo: typeof parsed.dateTo === 'string' ? parsed.dateTo : '',
        };
    } catch {
        localStorage.removeItem(storageKey);
        return { dateFrom: '', dateTo: '' };
    }
}

export function usePageDateRange(page: 'discover' | 'track' | 'builder' | 'analytics') {
    const storageKey = `bet-assistant-${page}-date-range`;
    const [dateRange, setDateRange] = useState(() => readDateRange(storageKey));

    useEffect(() => {
        localStorage.setItem(storageKey, JSON.stringify(dateRange));
    }, [dateRange, storageKey]);

    return {
        ...dateRange,
        setDateFrom: (dateFrom: string) => setDateRange(current => ({ ...current, dateFrom })),
        setDateTo: (dateTo: string) => setDateRange(current => ({ ...current, dateTo })),
    };
}
