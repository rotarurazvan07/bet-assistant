/**
 * Utility functions for color-related operations
 */

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