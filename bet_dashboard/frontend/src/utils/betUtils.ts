/**
 * Utility functions for bet-related operations
 */

const _tzFormatCache = new Map<string, Intl.DateTimeFormat>();

/**
 * Build (and cache) an Intl formatter that renders an instant's wall-clock parts in a timezone.
 */
function _wallClockFormatter(timezone: string): Intl.DateTimeFormat {
    let formatter = _tzFormatCache.get(timezone);
    if (!formatter) {
        formatter = new Intl.DateTimeFormat('en-US', {
            timeZone: timezone,
            hourCycle: 'h23',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
        _tzFormatCache.set(timezone, formatter);
    }
    return formatter;
}

/**
 * Read the wall-clock time a timezone shows for an instant, expressed as UTC milliseconds.
 */
function _wallClockAsUtc(timezone: string, instantMs: number): number {
    const parts = _wallClockFormatter(timezone).formatToParts(new Date(instantMs));
    const part = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
    return Date.UTC(part('year'), part('month') - 1, part('day'), part('hour'), part('minute'), part('second'));
}

/**
 * Convert a naive wall-clock string (as stored by the backend) into an epoch instant
 * for the given IANA timezone.
 *
 * Backend match datetimes carry no offset: they are the wall clock of the configured
 * match-data timezone. This applies that timezone's offset to get the true instant,
 * independent of the browser's own timezone, and refines once so DST boundaries resolve.
 *
 * @param iso - Naive datetime, e.g. '2026-01-15T20:30:00'
 * @param timezone - IANA timezone identifier the naive value is expressed in
 * @returns Milliseconds since epoch, or NaN when the input is missing/unparseable
 */
export function naiveToInstant(iso?: string | null, timezone = 'UTC'): number {
    if (!iso) return NaN;

    const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/.exec(iso);
    if (!match) return NaN;

    const wallAsUtc = Date.UTC(
        Number(match[1]),
        Number(match[2]) - 1,
        Number(match[3]),
        Number(match[4] ?? 0),
        Number(match[5] ?? 0),
        Number(match[6] ?? 0),
    );

    let instant = wallAsUtc;
    for (let i = 0; i < 2; i += 1) {
        instant = wallAsUtc - (_wallClockAsUtc(timezone, instant) - instant);
    }
    return instant;
}

/**
 * Format a naive backend datetime for display in a specific timezone.
 *
 * Backend match datetimes are naive wall-clock strings expressed in the
 * configured match-data timezone, so rendering must pin that timezone instead
 * of inheriting the browser's. Passing no timezone (or null) falls back to the
 * browser-local rendering used before the timezone contract existed.
 *
 * @param dateStr - Naive ISO datetime from the backend
 * @param timezone - IANA timezone identifier, or null while it is still loading
 * @param locale - BCP-47 locale (defaults to en-GB)
 * @param options - Extra Intl.DateTimeFormatOptions merged over the defaults
 * @returns Formatted date string, or '' when there is no date
 */
export function formatMatchTime(
    dateStr?: string | null,
    timezone?: string | null,
    locale = 'en-GB',
    options: Intl.DateTimeFormatOptions = {}
): string {
    if (!dateStr) return '';

    // Detect if the string carries its own offset (Z or ±HH:MM).
    // Such strings are true instants; parse them directly and render in the
    // configured timezone (or browser-local if no timezone configured).
    const hasOffset = /Z$|[+-]\d{2}:?\d{2}$/.test(dateStr.trim());

    // Without a configured timezone (still loading, or request failed) fall back
    // to the browser-local rendering the app used before the timezone contract.
    const formatOptions: Intl.DateTimeFormatOptions = {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        ...options,
        ...(timezone ? { timeZone: timezone } : {}),
    };

    const date = hasOffset
        ? new Date(dateStr)
        : timezone
            ? new Date(naiveToInstant(dateStr, timezone))
            : new Date(dateStr as string);
    return date.toLocaleString(locale, formatOptions);
}

/**
 * Format date for display in bet components
 * @param dateStr - Date string to format
 * @param options - Formatting options
 * @returns Formatted date string
 */
export function formatBetDate(
    dateStr?: string | null,
    options: { includeWeekday?: boolean; includeYear?: boolean; timezone?: string | null } = {}
): string {
    const { includeWeekday = false, includeYear = false, timezone = null } = options;

    const formatOptions: Intl.DateTimeFormatOptions = {
        ...(includeWeekday && { weekday: 'short' }),
        ...(includeYear && { year: 'numeric' })
    };

    return formatMatchTime(dateStr, timezone, 'en-GB', formatOptions);
}

/**
 * Parse team names from match name string
 * @param matchName - Match name in format "Team A - Team B"
 * @returns Object containing teamA and teamB
 */
export function parseTeamNames(matchName: string): { teamA: string; teamB: string } {
    const teams = matchName.split(' - ');
    const teamA = teams[0] || matchName;
    const teamB = teams[1] || '';

    return { teamA, teamB };
}

/**
 * Get color based on consensus percentage
 * @param consensus - Consensus percentage
 * @returns Color hex code
 */
export function getConsensusColor(consensus: number): string {
    return consensus >= 80 ? '#10B981'  // green-500
        : consensus >= 60 ? '#F59E0B'    // amber-500
            : '#EF4444';                    // red-500
}

/**
 * Get color based on status
 * @param status - Status string
 * @returns Color hex code
 */
export function getStatusColor(status: string): string {
    switch (status) {
        case 'Won': return '#10B981';    // green-500
        case 'Lost': return '#EF4444';    // red-500
        case 'Live': return '#3B82F6';   // blue-500
        case 'Pending': return '#F59E0B'; // amber-500
        default: return '#9CA3AF';       // gray-400
    }
}

/**
 * Calculate net profit for a bet slip
 * @param slipStatus - Status of the slip
 * @param totalOdds - Total odds of the slip
 * @param units - Number of units bet
 * @returns Net profit or loss
 */
export function calculateNetProfit(
    slipStatus: string,
    totalOdds: number,
    units: number
): number | null {
    const totalStake = units;
    const potentialReturn = totalOdds * units;

    switch (slipStatus) {
        case 'Won':
            return potentialReturn - totalStake;
        case 'Lost':
            return -totalStake;
        default:
            return null;
    }
}

/**
 * Get status icon based on status
 * @param status - Status string
 * @returns Status icon character
 */
export function getStatusIcon(status: string): string {
    switch (status) {
        case 'Won': return '✓';
        case 'Lost': return '✗';
        case 'Live': return '●';
        default: return '◷';
    }
}

/**
 * Get status for BaseBadge component
 * @param status - Status string
 * @returns Badge status type
 */
export function getStatusBadge(status: string): 'success' | 'error' | 'warning' | 'default' {
    switch (status) {
        case 'Won': return 'success';
        case 'Lost': return 'error';
        case 'Live': return 'warning';
        default: return 'default';
    }
}