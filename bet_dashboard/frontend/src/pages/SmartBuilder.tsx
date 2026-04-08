import { useCallback, useEffect, useRef, useState } from 'react';
import BuilderPanel from '../components/BuilderPanel';
import { BetPreview } from '../components/BetComponents';
import {
    fetchPreview, fetchProfiles, saveProfile, deleteProfile,
    fetchExcluded, fetchExcludedDetails, addExcluded, removeExcluded, clearExcluded, addSlip,
    type ExcludedMatch
} from '../api/data';
import type { GlobalFilters } from '../components/Layout';
import type { BuilderConfig, ProfilesMap, PreviewResult, CandidateLeg } from '../types';
import { ALL_MARKETS } from '../types';

const DEFAULT_CFG: BuilderConfig = {
    target_odds: 3.0, target_legs: 3, max_legs_overflow: null,
    consensus_floor: 50, min_odds: 1.05, included_markets: null,
    tolerance_factor: null, stop_threshold: null, min_legs_fill_ratio: 0.7,
    quality_vs_balance: 0.5, consensus_vs_sources: 0.5,
    date_from: null, date_to: null,
};

interface Props { filters: GlobalFilters; refreshKey: number }

export default function SmartBuilder({ filters, refreshKey }: Props) {
    const [cfg, setCfg] = useState<BuilderConfig>(DEFAULT_CFG);
    const [preview, setPreview] = useState<PreviewResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [profiles, setProfiles] = useState<ProfilesMap>({});
    const [activeName, setActiveName] = useState('manual');
    const [units, setUnits] = useState(1.0);
    const [runDaily, setRunDaily] = useState(0);
    const [excluded, setExcluded] = useState<string[]>([]);
    const [excludedDetails, setExcludedDetails] = useState<ExcludedMatch[]>([]);
    const [status, setStatus] = useState('');
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Load profiles + excluded on mount
    useEffect(() => {
        fetchProfiles().then(p => setProfiles(p ?? {})).catch(() => setProfiles({}));
        fetchExcluded().then(e => setExcluded(e ?? [])).catch(() => setExcluded([]));
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
    }, []);

    // Merge global date filters into cfg and trigger preview
    useEffect(() => {
        const newCfg = { ...cfg, date_from: filters.dateFrom || null, date_to: filters.dateTo || null };
        setCfg(newCfg);
        triggerPreview(newCfg);
    }, [filters.dateFrom, filters.dateTo]); // eslint-disable-line

    // Debounced preview — 350ms after any config change
    const triggerPreview = useCallback((config: BuilderConfig) => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(async () => {
            setLoading(true);
            try {
                const result = await fetchPreview(config);
                setPreview(result);
            } catch {
                // Set empty preview on error
                setPreview({ legs: [], total_odds: 1, pending_urls: [] });
            }
            finally { setLoading(false); }
        }, 350);
    }, []);

    function handleCfgChange(next: BuilderConfig) {
        setCfg(next);
        setActiveName('manual');
        triggerPreview(next);
    }

    // Trigger preview when refreshKey changes (new matches loaded)
    useEffect(() => { triggerPreview(cfg); }, [refreshKey]); // eslint-disable-line

    async function handleExclude(url: string) {
        const next = await addExcluded(url);
        setExcluded(next);
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
        triggerPreview(cfg);
    }

    async function handleClearExcluded() {
        await clearExcluded();
        setExcluded([]);
        setExcludedDetails([]);
        triggerPreview(cfg);
    }

    function loadProfile(name: string, data: any) {
        const next: BuilderConfig = {
            target_odds: data.target_odds ?? 3,
            target_legs: data.target_legs ?? 3,
            max_legs_overflow: data.max_legs_overflow ?? null,
            consensus_floor: data.consensus_floor ?? 50,
            min_odds: data.min_odds ?? 1.05,
            included_markets: data.included_markets ?? null,
            tolerance_factor: data.tolerance_factor ?? null,
            stop_threshold: data.stop_threshold ?? null,
            min_legs_fill_ratio: data.min_legs_fill_ratio ?? 0.7,
            quality_vs_balance: data.quality_vs_balance ?? 0.5,
            consensus_vs_sources: data.consensus_vs_sources ?? 0.5,
            date_from: filters.dateFrom || null,
            date_to: filters.dateTo || null,
        };
        setCfg(next);
        setActiveName(name);
        setUnits(data.units ?? 1);
        setRunDaily(data.run_daily_count ?? 0);
        triggerPreview(next);
    }

    async function handleSaveProfile() {
        const clean = activeName.replace(/[^a-z0-9_-]/gi, '').toLowerCase();
        if (!clean || clean === 'manual') {
            setStatus('Enter a profile name first.'); return;
        }
        await saveProfile(clean, { name: clean, ...cfg, units, run_daily_count: runDaily });
        const updated = await fetchProfiles();
        setProfiles(updated ?? {});
        setStatus(`✓ Profile '${clean}' saved`);
    }

    async function handleDeleteProfile() {
        if (!activeName || activeName === 'manual') return;
        await deleteProfile(activeName);
        const updated = await fetchProfiles();
        setProfiles(updated ?? {});
        setActiveName('manual');
        setStatus(`Deleted '${activeName}'`);
    }

    async function handleAddToSlips() {
        if (!preview?.legs.length) {
            setStatus('No legs in preview.'); return;
        }
        const id = await addSlip(activeName, preview.legs as unknown as CandidateLeg[], units);
        setStatus(`✓ Slip #${id} added to '${activeName}'`);
        // Re-trigger preview to show "in pending slip" warnings
        triggerPreview(cfg);
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
    }

    return (
        <div className="flex gap-6">
            {/* ── Left panel ────────────────────────────────────────────────────── */}
            <div className="w-80 shrink-0">
                <div className="card p-4">
                    {/* Profiles */}
                    <div className="mb-4">
                        <span className="text-[10px] font-mono tracking-widest uppercase"
                            style={{ color: 'var(--text-muted)' }}>Profiles</span>
                        <div className="flex flex-wrap gap-1.5 mt-2">
                            {Object.keys(profiles).map(name => (
                                <button key={name}
                                    className="text-[10px] font-mono uppercase px-2 py-0.5 rounded transition-colors"
                                    style={{
                                        background: activeName === name ? 'var(--accent)' : 'var(--bg-raised)',
                                        border: `1px solid ${activeName === name ? 'var(--accent)' : 'var(--border-strong)'}`,
                                        color: activeName === name ? '#fff' : 'var(--text-secondary)',
                                    }}
                                    onClick={() => loadProfile(name, profiles[name])}>
                                    {name}
                                </button>
                            ))}
                            {!Object.keys(profiles).length && (
                                <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                    No saved profiles yet
                                </span>
                            )}
                        </div>
                    </div>

                    <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                        <BuilderPanel cfg={cfg} onChange={handleCfgChange} />
                    </div>
                </div>
            </div>

            {/* ── Right panel ───────────────────────────────────────────────────── */}
            <div className="flex-1 min-w-0">
                {/* Management bar */}
                <div className="card px-4 py-3 mb-4">
                    <div className="flex items-center gap-3 flex-wrap">
                        <input className="field w-40" placeholder="profile name"
                            value={activeName} onChange={e => setActiveName(e.target.value)} />
                        <button className="btn-primary" onClick={handleSaveProfile}>Save</button>
                        <button className="btn-danger" onClick={handleDeleteProfile}>Delete</button>

                        <div className="flex items-center gap-2 border-l pl-3" style={{ borderColor: 'var(--border)' }}>
                            <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Units</span>
                            <input className="field w-16" type="number" min={0.1} step={0.1}
                                value={units} onChange={e => setUnits(+e.target.value)} />
                        </div>

                        <button className="btn-success" onClick={handleAddToSlips}>+ Add to Slips</button>
                        <button className="btn-ghost" onClick={handleClearExcluded}>Reset excluded</button>

                        <div className="flex items-center gap-2 border-l pl-3" style={{ borderColor: 'var(--border)' }}>
                            <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Run Daily</span>
                            <input className="field w-16" type="number" min={0} step={1}
                                value={runDaily} onChange={e => setRunDaily(+e.target.value)} />
                        </div>

                        {status && (
                            <span className="text-[11px] font-mono ml-auto" style={{ color: 'var(--accent)' }}>
                                {status}
                            </span>
                        )}
                    </div>
                </div>

                {/* Live preview */}
                <div className="card p-4">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="w-1.5 h-1.5 rounded-full animate-pulse"
                            style={{ background: 'var(--accent)' }} />
                        <span className="text-[10px] font-mono tracking-widest uppercase"
                            style={{ color: 'var(--text-muted)' }}>
                            Live Preview — updates with every config change
                        </span>
                        {loading && (
                            <span className="ml-auto text-[10px] font-mono animate-pulse"
                                style={{ color: 'var(--text-muted)' }}>building…</span>
                        )}
                    </div>

                    <div style={{ opacity: loading ? 0.5 : 1, transition: 'opacity .15s' }}>
                        <BetPreview
                            legs={preview?.legs ?? []}
                            totalOdds={preview?.total_odds ?? 1}
                            pendingUrls={preview?.pending_urls ?? []}
                            excludedUrls={excluded}
                            onExclude={handleExclude}
                        />
                    </div>
                </div>

                {/* Excluded matches as cards */}
                {(excludedDetails?.length ?? 0) > 0 && (
                    <div className="card p-4 mt-4 fade-in">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-[10px] font-mono tracking-widest uppercase"
                                style={{ color: 'var(--text-muted)' }}>
                                Excluded Matches ({excludedDetails.length})
                            </span>
                            <button className="btn-ghost text-[10px]" onClick={handleClearExcluded}>
                                Clear All
                            </button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {excludedDetails.map((item, i) => {
                                const dt = item.datetime
                                    ? new Date(item.datetime).toLocaleString('en-GB', {
                                        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                                    })
                                    : '';
                                return (
                                    <div key={i} className="rounded-lg p-3"
                                        style={{
                                            background: 'var(--bg-raised)',
                                            border: '1px solid var(--border)',
                                        }}>
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="flex-1 min-w-0">
                                                <p className="font-sans text-[12px] font-medium truncate"
                                                    style={{ color: 'var(--text-bright)' }}>
                                                    {item.match_name}
                                                </p>
                                                {dt && (
                                                    <p className="text-[10px] font-mono mt-0.5"
                                                        style={{ color: 'var(--text-muted)' }}>
                                                        {dt}
                                                    </p>
                                                )}
                                                <p className="text-[9px] font-mono mt-1"
                                                    style={{ color: 'var(--loss)' }}>
                                                    {item.reason}
                                                </p>
                                            </div>
                                            <button className="btn-icon shrink-0"
                                                onClick={() => {
                                                    // Only remove from manual exclusions (not from pending slips)
                                                    if (item.reason === "Manually excluded") {
                                                        removeExcluded(item.url).then(next => {
                                                            setExcluded(next);
                                                            fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
                                                            triggerPreview(cfg);
                                                        });
                                                    }
                                                }}
                                                title={item.reason === "Manually excluded" ? "Remove from manual exclusions" : "Cannot remove - in pending slip"}
                                                style={{ opacity: item.reason === "Manually excluded" ? 1 : 0.3, cursor: item.reason === "Manually excluded" ? 'pointer' : 'not-allowed' }}>
                                                <span style={{ fontSize: 12 }}>✕</span>
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
