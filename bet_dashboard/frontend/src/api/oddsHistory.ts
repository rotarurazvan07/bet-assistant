import client from './client';
import type { OddsMovementSummary, MarketMovementDetail } from '../types';

/**
 * Get just the movement summary for a specific match
 */
export async function getMatchMovement(matchId: number): Promise<OddsMovementSummary> {
    const response = await client.get<OddsMovementSummary>(`/odds-history/${matchId}/movement`);
    return response.data;
}

/**
 * Get movement summary for all future matches
 */
export async function getAllMovements(): Promise<Record<string, OddsMovementSummary>> {
    const response = await client.get<Record<string, OddsMovementSummary>>('/odds-history/movements/all');
    return response.data;
}

export type SignificantMovements = Record<string, Record<string, MarketMovementDetail>>;

export async function getSignificantMovements(): Promise<SignificantMovements> {
    const { data } = await client.get<SignificantMovements>('/odds-history/movements/significant');
    return data;
}
