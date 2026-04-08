import client from './client';
import type { MatchesPage } from '../types';

export async function fetchMatches(params: {
    page: number; page_size: number;
    search?: string; date_from?: string; date_to?: string;
    sort_by?: string; sort_dir?: string; min_sources?: number;
    min_consensus?: number | null;
}): Promise<MatchesPage> {
    const res = await client.get<MatchesPage>('/matches', { params });
    return res.data;
}
