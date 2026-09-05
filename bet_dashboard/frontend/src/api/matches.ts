import client from './client';
import type { MatchesPage } from '../types';

export async function fetchMatches(params: {
    page: number; page_size: number;
    search?: string; date_from?: string; date_to?: string;
    sort_by?: string; sort_dir?: string; min_sources?: number;
    min_consensus?: number | null;
    min_odds?: number | null;
    only_significant_movement?: boolean;
    excluded_sources?: string[];
}): Promise<MatchesPage> {
    const queryParams: Record<string, unknown> = { ...params };
    if (params.excluded_sources && params.excluded_sources.length > 0) {
        queryParams.excluded_sources = params.excluded_sources.join(',');
    }
    const res = await client.get<MatchesPage>('/matches', { params: queryParams });
    return res.data;
}
