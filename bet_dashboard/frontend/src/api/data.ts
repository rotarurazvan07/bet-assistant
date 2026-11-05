import client from './client';
import type {
    BuilderConfig, PreviewResult,
    ProfilesMap, Profile,
    SlipsPage, SlipCalendarData, BetSlip, ManualLegIn,
    AnalyticsData,
    ServicesData,
} from '../types';

// ── Builder ──────────────────────────────────────────────────────────────────

export async function fetchPreview(cfg: BuilderConfig): Promise<PreviewResult> {
    const res = await client.post<PreviewResult>('/builder/preview', cfg);
    return res.data;
}

export async function fetchLeagues(): Promise<string[]> {
    const res = await client.get<string[]>('/builder/leagues');
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

export async function fetchExcludedDetails(): Promise<ExcludedMatch[]> {
    const res = await client.get<{ excluded: ExcludedMatch[] }>('/builder/excluded/details');
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

export async function fetchProfiles(): Promise<ProfilesMap> {
    const res = await client.get<{ profiles: ProfilesMap }>('/profiles');
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
    page?: number; page_size?: number;
    sort_by?: 'net_profit_desc' | 'net_profit_asc' | 'date_desc' | 'date_asc' | 'odds_desc' | 'odds_asc' | 'stake_desc' | 'stake_asc';
}): Promise<SlipsPage> {
    const res = await client.get<SlipsPage>('/slips', { params });
    return res.data;
}

export async function fetchSlipCalendar(params: {
    date_from: string; date_to: string; profiles?: string[];
}): Promise<SlipCalendarData> {
    const res = await client.get<SlipCalendarData>('/slips/calendar', { params });
    return res.data;
}

export async function fetchAllSlips(
    params: Omit<Parameters<typeof fetchSlips>[0], 'page' | 'page_size'>,
): Promise<BetSlip[]> {
    const slips: BetSlip[] = [];
    let page = 1;
    let totalPages = 1;
    do {
        const result = await fetchSlips({ ...params, page, page_size: 100 });
        slips.push(...result.slips);
        totalPages = result.total_pages;
        page += 1;
    } while (page <= totalPages);
    return slips;
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
}): Promise<AnalyticsData> {
    const res = await client.get<AnalyticsData>('/analytics', { params });
    return res.data;
}

// ── Services ─────────────────────────────────────────────────────────────────

export async function fetchServices(): Promise<ServicesData> {
    const res = await client.get<ServicesData>('/services');
    return res.data;
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

// ── Config ──────────────────────────────────────────────────────────────────────

export interface SourcesConfig {
    sources: string[];
}

export async function fetchSourcesConfig(): Promise<SourcesConfig> {
    const res = await client.get<SourcesConfig>('/config/sources');
    return res.data;
}
