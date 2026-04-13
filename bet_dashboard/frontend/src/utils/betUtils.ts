/**
 * Utility functions for bet-related operations
 */

/**
 * Format date for display in bet components
 * @param dateStr - Date string to format
 * @param options - Formatting options
 * @returns Formatted date string
 */
export function formatBetDate(
    dateStr?: string | null,
    options: { includeWeekday?: boolean; includeYear?: boolean } = {}
): string {
    if (!dateStr) return '';

    const date = new Date(dateStr);
    const { includeWeekday = false, includeYear = false } = options;

    const formatOptions: Intl.DateTimeFormatOptions = {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        ...(includeWeekday && { weekday: 'short' }),
        ...(includeYear && { year: 'numeric' })
    };

    return date.toLocaleString('en-GB', formatOptions);
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