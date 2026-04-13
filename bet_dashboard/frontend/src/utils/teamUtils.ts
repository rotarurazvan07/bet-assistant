/**
 * Utility functions for team-related operations
 */

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
 * Get team name from match name
 * @param matchName - Match name in format "Team A - Team B"
 * @param team - Which team to return ('home' or 'away')
 * @returns Team name
 */
export function getTeamName(matchName: string, team: 'home' | 'away'): string {
    const teams = matchName.split(' - ');
    if (team === 'home') {
        return teams[0] || matchName;
    } else {
        return teams[1] || '';
    }
}