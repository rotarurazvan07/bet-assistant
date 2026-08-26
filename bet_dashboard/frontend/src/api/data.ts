import client from './client';
import type {
    BuilderConfig, PreviewResult,
    ProfilesMap, Profile,
    SlipsPage, ManualLegIn,
    AnalyticsData,
    ServicesData,
    MatchesPage,
    OddsHistory,
    DataSource,
} from '../types';

// ── Builder ──────────────────────────────────────────────────────────────────

export async function fetchPreview(cfg: BuilderConfig, dataSource: DataSource = 'live'): Promise<PreviewResult> {
    const res = await client.post<PreviewResult>('/builder/preview', cfg, {
        params: { data_source: dataSource },
    });
    return res.data;
}

export async function fetchLeagues(dataSource: DataSource = 'live'): Promise<string[]> {
    const res = await client.get<string[]>('/builder/leagues', { params: { data_source: dataSource } });
    return res.data;
}

export async function fetchExcluded(): Promise<string[]> {
    const res = await client.get<{ excluded: string[] }>('/builder/excluded');
    return res.data.excluded;
}

export interface ExcludedMatch {
    url: string;
    match_name: string;
    datetime: string | null;
    reason: string;
}

export async function fetchExcludedDetails(dataSource: DataSource = 'live'): Promise<ExcludedMatch[]> {
    const res = await client.get<{ excluded: ExcludedMatch[] }>('/builder/excluded/details', { params: { data_source: dataSource } });
    return res.data.excluded;
}

export async function addExcluded(url: string): Promise<string[]> {
    const res = await client.post<{ excluded: string[] }>('/builder/excluded', { url });
    return res.data.excluded;
}

export async function removeExcluded(url: string): Promise<string[]> {
    const res = await client.post<{ excluded: string[] }>('/builder/excluded/remove', { url });
    return res.data.excluded;
}

export async function clearExcluded(): Promise<void> {
    await client.delete('/builder/excluded');
}

// ── Profiles ─────────────────────────────────────────────────────────────────

export async function fetchProfiles(dataSource: DataSource = 'live'): Promise<ProfilesMap> {
    const res = await client.get<{ profiles: ProfilesMap }>('/profiles', { params: { data_source: dataSource } });
    return res.data.profiles;
}

export async function saveProfile(data: Profile & { name: string }): Promise<void> {
    await client.post('/profiles', data);
}

export async function deleteProfile(name: string): Promise<void> {
    await client.delete(`/profiles/${name}`);
}

// ── Slips ────────────────────────────────────────────────────────────────────

export async function fetchSlips(params: {
    profiles?: string[]; date_from?: string; date_to?: string;
    hide_settled?: boolean; live_only?: boolean;
    data_source?: DataSource;
}): Promise<SlipsPage> {
    const res = await client.get<SlipsPage>('/slips', { params });
    return res.data;
}

export async function addSlip(profile: string, legs: ManualLegIn[], units: number): Promise<number> {
    const res = await client.post<{ slip_id: number }>('/slips', { profile, legs, units });
    return res.data.slip_id;
}

export async function deleteSlip(id: number): Promise<void> {
    await client.delete(`/slips/${id}`);
}

export async function validateSlips(): Promise<{
    checked: number; settled: number; live: number; errors: number;
    live_data: Array<{ match_name: string; score: string; minute: string }>;
}> {
    const res = await client.post('/slips/validate');
    return res.data;
}

export async function generateSlips(): Promise<{ generated: number; by_profile: Record<string, number> }> {
    const res = await client.post('/slips/generate');
    return res.data;
}

// ── Analytics ────────────────────────────────────────────────────────────────

export async function fetchAnalytics(params: {
    profiles?: string[]; date_from?: string; date_to?: string;
    data_source?: DataSource;
}): Promise<AnalyticsData> {
    const res = await client.get<AnalyticsData>('/analytics', { params });
    return res.data;
}

// ── Matches ──────────────────────────────────────────────────────────────────

export async function fetchMatches(params: {
    page?: number; page_size?: number; search?: string;
    date_from?: string; date_to?: string;
    sort_by?: string; sort_dir?: string;
    min_consensus?: number; min_odds?: number;
    only_significant_movement?: boolean;
    data_source?: DataSource;
}): Promise<MatchesPage> {
    const res = await client.get<MatchesPage>('/matches', { params });
    return res.data;
}

// ── Odds History ─────────────────────────────────────────────────────────────

export async function fetchOddsHistory(matchId: number, dataSource: DataSource = 'live'): Promise<OddsHistory> {
    const res = await client.get<OddsHistory>(`/odds-history/${matchId}`, { params: { data_source: dataSource } });
    return res.data;
}

export async function fetchAllMovements(dataSource: DataSource = 'live'): Promise<Record<string, any>> {
    const res = await client.get<Record<string, any>>('/odds-history/movements/all', { params: { data_source: dataSource } });
    return res.data;
}

export async function fetchSignificantMovements(dataSource: DataSource = 'live'): Promise<Record<string, any>> {
    const res = await client.get<Record<string, any>>('/odds-history/movements/significant', { params: { data_source: dataSource } });
    return res.data;
}

// ── Services ─────────────────────────────────────────────────────────────────

export async function fetchServices(dataSource: DataSource = 'live'): Promise<ServicesData> {
    const res = await client.get<ServicesData>('/services', { params: { data_source: dataSource } });
    return res.data;
}

export async function saveServiceSettings(generate_hour: number, generate_minute: number): Promise<void> {
    await client.post('/services/settings', { generate_hour, generate_minute });
}

export async function toggleService(name: string): Promise<{ name: string; enabled: boolean }> {
    const res = await client.post<{ name: string; enabled: boolean }>(`/services/${name}/toggle`);
    return res.data;
}

// ── System ───────────────────────────────────────────────────────────────────

export async function pullDb(): Promise<{ status: string; timestamp: string }> {
    const res = await client.post<{ status: string; timestamp: string }>('/pull', {}, {
        // The backend expects /api/pull, but our client baseURL is /api, so we need /pull
    });
    return res.data;
}

export async function fetchStatus(): Promise<{ last_pull: string; matches_loaded: number }> {
    const res = await client.get('/status');
    return res.data;
}
