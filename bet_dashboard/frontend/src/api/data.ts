import client from './client';
import type {
    BuilderConfig, PreviewResult,
    ProfilesMap, Profile,
    SlipsPage, ManualLegIn,
    AnalyticsData,
    ServicesData,
} from '../types';

// ── Builder ──────────────────────────────────────────────────────────────────

export async function fetchPreview(cfg: BuilderConfig): Promise<PreviewResult> {
    const res = await client.post<PreviewResult>('/builder/preview', cfg);
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
}): Promise<AnalyticsData> {
    const res = await client.get<AnalyticsData>('/analytics', { params });
    return res.data;
}

// ── Services ─────────────────────────────────────────────────────────────────

export async function fetchServices(): Promise<ServicesData> {
    const res = await client.get<ServicesData>('/services');
    return res.data;
}

export async function saveServiceSettings(pull_hour: number, generate_hour: number): Promise<void> {
    await client.post('/services/settings', { pull_hour, generate_hour });
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
