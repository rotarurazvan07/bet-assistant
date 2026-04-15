/**
 * Utility functions for color-related operations
 */

/**
 * Get color based on consensus percentage
 * @param consensus - Consensus percentage
 * @returns CSS variable reference
 */
export function getConsensusColor(consensus: number): string {
    return consensus >= 80 ? 'var(--cons-high-txt)'
        : consensus >= 60 ? 'var(--cons-mid-txt)'
            : 'var(--cons-low-txt)';
}

/**
 * Get color based on status
 * @param status - Status string
 * @returns CSS variable reference
 */
export function getStatusColor(status: string): string {
    switch (status) {
        case 'Won': return 'var(--win)';
        case 'Lost': return 'var(--loss)';
        case 'Live': return 'var(--live)';
        case 'Pending': return 'var(--pending)';
        default: return 'var(--text-muted)';
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
export function getStatusBadge(status: string): 'success' | 'error' | 'warning' | 'default' | 'info' {
    switch (status) {
        case 'Won': return 'success';
        case 'Lost': return 'error';
        case 'Live': return 'info';
        case 'Pending': return 'warning';
        default: return 'default';
    }
}