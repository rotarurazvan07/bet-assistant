import { useEffect, useMemo, useState } from 'react';
import { fetchSlipCalendar } from '../api/data';
import type { SlipDailyPnl } from '../types';

interface Props {
    profiles: string[];
    dateFrom: string;
    dateTo: string;
    selectedDate: string | null;
    onSelectDate: (date: string) => void;
}

function dateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function parseDate(value: string): Date | null {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    const [year, month, day] = value.split('-').map(Number);
    const parsed = new Date(year, month - 1, day);
    return Number.isNaN(parsed.getTime()) || dateKey(parsed) !== value ? null : parsed;
}

function formatProfit(value: number): string {
    return `${value > 0 ? '+' : ''}${value.toFixed(1)}U`;
}

function dayColor(day: SlipDailyPnl | undefined): string {
    if (!day) return 'var(--bg-surface)';
    if (day.net_profit === 0) return 'var(--bg-raised)';
    const intensity = Math.min(Math.abs(day.net_profit) / 5, 1);
    const alpha = 0.14 + intensity * 0.62;
    return day.net_profit > 0
        ? `rgba(34, 197, 94, ${alpha})`
        : `rgba(239, 68, 68, ${alpha})`;
}

export default function SlipCalendar({ profiles, dateFrom, dateTo, selectedDate, onSelectDate }: Props) {
    const [month, setMonth] = useState(() => {
        const now = new Date();
        return new Date(now.getFullYear(), now.getMonth(), 1);
    });
    const [response, setResponse] = useState<{
        key: string;
        days: SlipDailyPnl[];
        error: boolean;
    } | null>(null);
    const [retryKey, setRetryKey] = useState(0);

    const monthStart = new Date(month.getFullYear(), month.getMonth(), 1);
    const monthEnd = new Date(month.getFullYear(), month.getMonth() + 1, 0);
    const rangeStart = parseDate(dateFrom);
    const rangeEnd = parseDate(dateTo);
    const effectiveStart = rangeStart && rangeStart > monthStart ? rangeStart : monthStart;
    const effectiveEnd = rangeEnd && rangeEnd < monthEnd ? rangeEnd : monthEnd;
    const startKey = dateKey(effectiveStart);
    const endKey = dateKey(effectiveEnd);
    const hasDateRange = effectiveStart <= effectiveEnd;
    const requestKey = JSON.stringify([startKey, endKey, profiles, retryKey]);
    const currentResponse = response?.key === requestKey ? response : null;
    const loading = hasDateRange && currentResponse === null;
    const error = currentResponse?.error ?? false;

    useEffect(() => {
        if (!hasDateRange) {
            return;
        }

        let cancelled = false;
        fetchSlipCalendar({
            date_from: startKey,
            date_to: endKey,
            profiles: profiles.length > 0 ? profiles : undefined,
        })
            .then(result => {
                if (!cancelled) setResponse({ key: requestKey, days: result.days, error: false });
            })
            .catch(error => {
                console.error('Failed to fetch slip calendar:', error);
                if (!cancelled) setResponse({ key: requestKey, days: [], error: true });
            });

        return () => { cancelled = true; };
    }, [endKey, hasDateRange, profiles, requestKey, startKey]);

    const daysByDate = useMemo(() => new Map(
        (currentResponse?.days ?? []).map(day => [day.date, day]),
    ), [currentResponse]);
    const monthSummary = useMemo(() => (currentResponse?.days ?? []).reduce(
        (summary, day) => ({
            slips: summary.slips + day.slips,
            wins: summary.wins + day.wins,
            losses: summary.losses + day.losses,
            netProfit: summary.netProfit + day.net_profit,
        }),
        { slips: 0, wins: 0, losses: 0, netProfit: 0 },
    ), [currentResponse]);
    const cells = useMemo(() => {
        const firstWeekday = new Date(month.getFullYear(), month.getMonth(), 1).getDay();
        const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
        return [
            ...Array.from({ length: firstWeekday }, () => null),
            ...Array.from({ length: count }, (_, index) => new Date(month.getFullYear(), month.getMonth(), index + 1)),
        ];
    }, [month]);

    const monthLabel = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' }).format(month);
    const todayKey = dateKey(new Date());
    const settledCount = monthSummary.wins + monthSummary.losses;
    const hitRate = settledCount ? `${Math.round((monthSummary.wins / settledCount) * 100)}%` : '—';

    function moveMonth(offset: number) {
        setMonth(current => new Date(current.getFullYear(), current.getMonth() + offset, 1));
    }

    return (
        <section
            className="relative overflow-hidden rounded-2xl border p-4 md:p-6 mb-6"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)' }}
            aria-label="Daily profit calendar"
        >
            <div
                className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full opacity-20 blur-3xl"
                style={{ background: 'var(--accent)' }}
                aria-hidden="true"
            />
            <div className="relative">
                <div className="flex items-center justify-between gap-4 flex-wrap mb-6">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <span className="h-2 w-2 rounded-full" style={{ background: 'var(--accent)' }} />
                            <span
                                className="text-[10px] sm:text-xs font-mono uppercase tracking-[.18em]"
                                style={{ color: 'var(--text-secondary)' }}
                            >
                                Daily performance
                            </span>
                        </div>
                        <h2 className="font-display font-bold text-2xl md:text-3xl" style={{ color: 'var(--text-bright)' }}>
                            {monthLabel}
                        </h2>
                    </div>
                    <div
                        className="flex items-center gap-1 rounded-xl border p-1"
                        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
                        role="group"
                        aria-label="Calendar navigation"
                    >
                        <button
                            className="flex h-9 w-9 items-center justify-center rounded-lg text-lg transition-colors hover:bg-white/5"
                            aria-label="Previous month"
                            onClick={() => moveMonth(-1)}
                            style={{ color: 'var(--text-secondary)' }}
                        >
                            ‹
                        </button>
                        <button
                            className="rounded-lg px-3 py-2 text-xs font-semibold transition-colors hover:bg-white/5"
                            onClick={() => {
                                const now = new Date();
                                setMonth(new Date(now.getFullYear(), now.getMonth(), 1));
                            }}
                            style={{ color: 'var(--text-bright)' }}
                        >
                            Today
                        </button>
                        <button
                            className="flex h-9 w-9 items-center justify-center rounded-lg text-lg transition-colors hover:bg-white/5"
                            aria-label="Next month"
                            onClick={() => moveMonth(1)}
                            style={{ color: 'var(--text-secondary)' }}
                        >
                            ›
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-3 gap-2 sm:gap-3 mb-6">
                    {[
                        {
                            label: 'Net P&L',
                            value: loading ? '…' : currentResponse?.error ? '—' : formatProfit(monthSummary.netProfit),
                            color: monthSummary.netProfit > 0 ? 'var(--live, #22c55e)' : monthSummary.netProfit < 0 ? 'var(--danger, #ef4444)' : 'var(--text-bright)',
                        },
                        {
                            label: 'Slips',
                            value: loading ? '…' : currentResponse?.error ? '—' : String(monthSummary.slips),
                            color: 'var(--text-bright)',
                        },
                        {
                            label: 'Win rate',
                            value: loading ? '…' : currentResponse?.error ? '—' : hitRate,
                            color: 'var(--text-bright)',
                        },
                    ].map(metric => (
                        <div
                            key={metric.label}
                            className="rounded-xl border px-3 py-3 sm:px-4"
                            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
                        >
                            <div className="text-[9px] sm:text-[10px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--text-secondary)' }}>
                                {metric.label}
                            </div>
                            <div className="font-display font-bold text-base sm:text-xl tabular-nums" style={{ color: metric.color }}>
                                {metric.value}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {error && hasDateRange && (
                <div role="alert" className="mb-4 rounded-lg border px-3 py-2 text-sm" style={{ color: 'var(--danger, #ef4444)', borderColor: 'var(--border)' }}>
                    Could not load calendar data.{' '}
                    <button className="btn-ghost" onClick={() => setRetryKey(value => value + 1)}>Retry</button>
                </div>
            )}

            <div className="grid grid-cols-7 gap-1.5 sm:gap-2" aria-busy={loading}>
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((weekday, index) => (
                    <div
                        key={weekday}
                        className="text-center text-[9px] sm:text-[10px] font-mono uppercase tracking-wider pb-1.5"
                        style={{ color: index === 0 || index === 6 ? 'var(--text-bright)' : 'var(--text-secondary)' }}
                    >
                        <span className="hidden sm:inline">{weekday}</span>
                        <span className="sm:hidden">{weekday[0]}</span>
                    </div>
                ))}
                {cells.map((date, index) => {
                    if (!date) return <div key={`empty-${index}`} aria-hidden="true" />;
                    const key = dateKey(date);
                    const day = daysByDate.get(key);
                    const weekend = date.getDay() === 0 || date.getDay() === 6;
                    const tooltip = day
                        ? `${day.slips} ${day.slips === 1 ? 'slip' : 'slips'}, ${formatProfit(day.net_profit)}, ${day.wins}W/${day.losses}L`
                        : 'No slips';
                    const inRange = hasDateRange && key >= startKey && key <= endKey;
                    return (
                        <button
                            key={key}
                            type="button"
                            disabled={!inRange}
                            onClick={() => onSelectDate(key)}
                            title={tooltip}
                            aria-label={`${key}: ${tooltip}`}
                            aria-pressed={selectedDate === key}
                            className="group flex min-h-[68px] flex-col justify-between rounded-lg border p-1.5 text-left transition-all hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 sm:min-h-24 sm:rounded-xl sm:p-2.5 disabled:cursor-default disabled:opacity-30 disabled:hover:translate-y-0 disabled:hover:shadow-none"
                            style={{
                                background: dayColor(day),
                                borderColor: selectedDate === key
                                    ? 'var(--accent)'
                                    : weekend ? 'var(--border-strong, var(--border))' : 'var(--border)',
                                outline: key === todayKey ? '1px solid var(--accent)' : undefined,
                                outlineOffset: key === todayKey ? '1px' : undefined,
                                color: 'var(--text-bright)',
                            }}
                        >
                            <span className="flex w-full items-center justify-between gap-1">
                                <span
                                    className="inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-[10px] sm:h-7 sm:min-w-7 sm:text-xs font-mono"
                                    style={{
                                        color: key === todayKey ? 'var(--bg-base)' : 'var(--text-bright)',
                                        background: key === todayKey ? 'var(--accent)' : 'transparent',
                                    }}
                                >
                                    {date.getDate()}
                                </span>
                                {day && (
                                    <span className="hidden sm:inline text-[9px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                                        {day.slips} {day.slips === 1 ? 'slip' : 'slips'}
                                    </span>
                                )}
                            </span>
                            {day ? (
                                <span className="w-full truncate text-[9px] sm:text-xs font-semibold tabular-nums">
                                    {formatProfit(day.net_profit)}
                                </span>
                            ) : (
                                <span className="w-full text-[9px] sm:text-[10px]" style={{ color: 'var(--text-secondary)', opacity: 0.65 }}>
                                    <span className="hidden sm:inline">No slips</span>
                                    <span className="sm:hidden">—</span>
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            <div className="flex items-center justify-between gap-3 flex-wrap mt-5 border-t pt-4" style={{ borderColor: 'var(--border)' }}>
                <div className="flex items-center gap-2 text-[10px] sm:text-xs" style={{ color: 'var(--text-secondary)' }}>
                    <span>-5U</span>
                    <span className="h-2.5 w-16 sm:w-24 rounded-full" style={{ background: 'linear-gradient(90deg, rgba(239,68,68,.76), var(--bg-raised), rgba(34,197,94,.76))' }} />
                    <span>+5U</span>
                </div>
                <span className="text-[9px] sm:text-[10px] text-right" style={{ color: 'var(--text-secondary)' }}>
                    {loading ? 'Updating calendar…' : 'Realized P&L · Pending and live slips excluded'}
                </span>
            </div>
        </section>
    );
}
