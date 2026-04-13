/**
 * Utility functions for calculations
 */

/**
 * Calculate risk score based on odds and consensus
 * @param totalOdds - Total odds of the slip
 * @param avgConsensus - Average consensus percentage
 * @returns Risk score between 0-100
 */
export function calculateRiskScore(totalOdds: number, avgConsensus: number): number {
    const oddsRisk = Math.min(100, (Math.log10(Math.max(1, totalOdds)) / 2.3) * 100);
    const consensusBonus = ((avgConsensus - 50) / 50) * 15;
    const riskScore = Math.min(100, Math.max(0, oddsRisk - consensusBonus));
    return riskScore;
}

/**
 * Calculate win probability from odds
 * @param totalOdds - Total odds
 * @returns Win probability score
 */
export function calculateWinProbability(totalOdds: number): number {
    const winProb = (1 / totalOdds) * 100;
    return Math.min(100, Math.sqrt(winProb) * 12);
}

/**
 * Calculate diversity score based on unique markets
 * @param uniqueMarkets - Number of unique markets
 * @param totalMarkets - Total possible markets
 * @param legsLength - Number of legs
 * @returns Diversity score
 */
export function calculateDiversityScore(
    uniqueMarkets: number,
    totalMarkets: number,
    legsLength: number
): number {
    return (uniqueMarkets / Math.min(totalMarkets, legsLength)) * 100;
}

/**
 * Get risk label based on risk score
 * @param score - Risk score
 * @returns Risk label
 */
export function getRiskLabel(score: number): string {
    if (score < 20) return 'Very Safe';
    if (score < 40) return 'Safe';
    if (score < 60) return 'Moderate';
    if (score < 80) return 'Risky';
    return 'Very Risky';
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