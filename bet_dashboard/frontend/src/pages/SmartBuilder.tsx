import { useCallback, useEffect, useRef, useState } from 'react';
import BuilderPanel from '../components/BuilderPanel';
import { BetPreview } from '../components/BetComponents';
import AnalyticsDashboard from '../components/AnalyticsDashboard';
import {
    fetchPreview, fetchProfiles, saveProfile, deleteProfile,
    fetchExcludedDetails, addExcluded, removeExcluded, clearExcluded, addSlip,
    type ExcludedMatch
} from '../api/data';
import type { GlobalFilters } from '../components/Layout';
import type { BuilderConfig, ProfilesMap, PreviewResult, ManualLegIn } from '../types';

const DEFAULT_CFG: BuilderConfig = {
    target_odds: 3.0, target_legs: 3, max_legs_overflow: null,
    consensus_floor: 50, min_odds: 1.05, included_markets: null,
    tolerance_factor: null, stop_threshold: null, min_legs_fill_ratio: 0.7,
    quality_vs_balance: 0.5, consensus_vs_sources: 0.5,
    date_from: null, date_to: null,
    consensus_shrinkage_k: null,
    min_source_edge: null,
    max_single_leg_odds: null,
    tol_lower: null,
    tol_upper: null,
    balance_decay: 'linear',
    min_pick_quality: null,
};

interface Props { filters: GlobalFilters; refreshKey: number }

const STORAGE_KEY = 'smart_builder_state';

export default function SmartBuilder({ filters, refreshKey }: Props) {
    // Load persisted state from localStorage
    const [cfg, setCfg] = useState<BuilderConfig>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            return { ...DEFAULT_CFG, ...parsed.cfg };
        }
        return DEFAULT_CFG;
    });
    const [activeName, setActiveName] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).activeName : 'manual';
    });
    const [units, setUnits] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).units : 1.0;
    });
    const [runDaily, setRunDaily] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).runDaily : 0;
    });

    // New: Target Payout logic
    const [targetPayout, setTargetPayout] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? (JSON.parse(saved).targetPayout ?? 0) : 0;
    });

    const [preview, setPreview] = useState<PreviewResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [profiles, setProfiles] = useState<ProfilesMap>({});
    const [excludedDetails, setExcludedDetails] = useState<ExcludedMatch[]>([]);
    const [status, setStatus] = useState('');
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Persist state to localStorage
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            cfg: { ...cfg, date_from: null, date_to: null },
            activeName,
            units,
            runDaily,
            targetPayout
        }));
    }, [cfg, activeName, units, runDaily, targetPayout]);

    // Load profiles + excluded on mount
    useEffect(() => {
        fetchProfiles().then(p => setProfiles(p ?? {})).catch(() => setProfiles({}));
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
    }, []);

    // Compute merged config with global date filters (for preview only)
    const mergedCfg = { ...cfg, date_from: filters.dateFrom || null, date_to: filters.dateTo || null };

    // Debounced preview — 350ms after any config change
    const triggerPreview = useCallback((config: BuilderConfig) => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(async () => {
            setLoading(true);
            try {
                const result = await fetchPreview(config);
                setPreview(result);
            } catch {
                setPreview({ legs: [], total_odds: 1, pending_urls: [] });
            }
            finally { setLoading(false); }
        }, 350);
    }, []);

    function handleCfgChange(next: BuilderConfig) {
        setCfg(next);
        setActiveName('manual');
        triggerPreview({ ...next, date_from: filters.dateFrom || null, date_to: filters.dateTo || null });
    }

    // Trigger preview when refreshKey or global filters change
    useEffect(() => { triggerPreview(mergedCfg); }, [refreshKey, filters.dateFrom, filters.dateTo]); // eslint-disable-line

    // Auto-calculate units if target payout is set — anchored to LIVE PREVIEW odds
    useEffect(() => {
        if (targetPayout > 0) {
            // Priority 1: Actual odds from the builder preview
            // Priority 2: Fallback to the requested target odds (if no legs found yet)
            const currentOdds = (preview?.legs && preview.legs.length > 0)
                ? (preview.total_odds || 1)
                : (cfg.target_odds || 1);

            const calculated = targetPayout / currentOdds;

            // Round to 1 decimal place to match stepper system
            const finalUnits = Math.round(calculated * 10) / 10 || 0.1;

            if (finalUnits !== units) {
                setUnits(finalUnits);
            }
        }
    }, [targetPayout, preview?.total_odds, preview?.legs.length, cfg.target_odds, units]);

    async function handleExclude(url: string) {
        await addExcluded(url);
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
        triggerPreview(mergedCfg);
    }

    async function handleClearExcluded() {
        await clearExcluded();
        setExcludedDetails([]);
        triggerPreview(mergedCfg);
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
            date_from: null,
            date_to: null,
            consensus_shrinkage_k: data.consensus_shrinkage_k ?? null,
            min_source_edge: data.min_source_edge ?? null,
            max_single_leg_odds: data.max_single_leg_odds ?? null,
            tol_lower: data.tol_lower ?? null,
            tol_upper: data.tol_upper ?? null,
            balance_decay: data.balance_decay ?? 'linear',
            min_pick_quality: data.min_pick_quality ?? null,
        };
        setCfg(next);
        setActiveName(name);
        setUnits(data.units ?? 1);
        setRunDaily(data.run_daily_count ?? 0);
        setTargetPayout(data.target_payout ?? 0);
        triggerPreview({ ...next, date_from: filters.dateFrom || null, date_to: filters.dateTo || null });
    }

    async function handleSaveProfile() {
        const clean = activeName.replace(/[^a-z0-9_-]/gi, '').toLowerCase();
        if (!clean || clean === 'manual') {
            setStatus('Enter a profile name first.'); return;
        }
        const { date_from, date_to, ...cfgWithoutDates } = cfg;
        await saveProfile({ name: clean, ...cfgWithoutDates, units, target_payout: targetPayout, run_daily_count: runDaily });
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

        const validLegs = preview.legs.filter(leg =>
            leg.odds != null && leg.odds > 0 &&
            leg.consensus != null && leg.consensus > 0 &&
            leg.sources != null && leg.sources >= 0 &&
            leg.datetime != null &&
            leg.match_name &&
            leg.market &&
            leg.market_type &&
            leg.result_url
        );

        if (validLegs.length !== preview.legs.length) {
            setStatus(`Skipped ${preview.legs.length - validLegs.length} legs missing required data`);
            return;
        }

        const manualLegs: ManualLegIn[] = validLegs.map(leg => ({
            match_name: leg.match_name,
            market: leg.market,
            market_type: leg.market_type,
            odds: leg.odds,
            result_url: leg.result_url!,
            datetime: leg.datetime!,
            consensus: leg.consensus,
            sources: leg.sources,
        }));

        const id = await addSlip(activeName, manualLegs, units);
        setStatus(`✓ Slip #${id} added to '${activeName}'`);
        triggerPreview(mergedCfg);
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
    }

    return (
        <div className="flex flex-col xl:flex-row gap-6 lg:gap-8 min-h-screen">
            {/* ── Left Sidebar — Responsive width ─────────────────────────────── */}
            <div className="w-full xl:w-[350px] 2xl:w-[400px] shrink-0">
                <div className="sticky top-4 space-y-4">
                    <div className="rounded-xl overflow-hidden"
                        style={{
                            background: 'linear-gradient(180deg, rgba(5,8,15,.95) 0%, rgba(13,19,33,.9) 100%)',
                            border: '1px solid rgba(255,255,255,.05)',
                            boxShadow: '0 8px 32px rgba(0,0,0,.4)',
                        }}>
                        <div className="px-5 pt-5 pb-4"
                            style={{ borderBottom: '1px solid rgba(255,255,255,.05)' }}>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-sm">👤</span>
                                <span className="text-[10px] font-mono tracking-[0.2em] uppercase font-medium"
                                    style={{ color: 'var(--text-muted)' }}>Profiles</span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {Object.keys(profiles).map(name => (
                                    <button key={name}
                                        className="text-[10px] font-mono uppercase px-2.5 py-1 rounded-lg transition-all duration-200"
                                        style={{
                                            background: activeName === name
                                                ? 'linear-gradient(135deg, var(--accent) 0%, #2563EB 100%)'
                                                : 'rgba(19,28,46,.6)',
                                            border: `1px solid ${activeName === name ? 'var(--accent)' : 'rgba(255,255,255,.06)'}`,
                                            color: activeName === name ? '#fff' : 'var(--text-secondary)',
                                            boxShadow: activeName === name ? '0 2px 12px rgba(61,123,255,.2)' : 'none',
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
                        <div className="px-3 py-4">
                            <BuilderPanel cfg={cfg} onChange={handleCfgChange} />
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Main Content — Flexible ─────────────────────────────────────── */}
            <div className="flex-1 min-w-0">
                {/* Top Header / Management Bar */}
                <div className="rounded-xl px-5 py-3.5 mb-5"
                    style={{
                        background: 'linear-gradient(180deg, rgba(24,36,58,.6) 0%, rgba(13,19,33,.6) 100%)',
                        border: '1px solid rgba(255,255,255,.05)',
                        backdropFilter: 'blur(10px)',
                    }}>
                    <div className="flex items-center gap-3 flex-wrap">
                        <input className="field w-40" placeholder="profile name"
                            value={activeName} onChange={e => setActiveName(e.target.value)} />
                        <button className="btn-primary" onClick={handleSaveProfile}>Save</button>
                        <button className="btn-danger" onClick={handleDeleteProfile}>Delete</button>

                        {/* Units & Target Payout */}
                        <div className="flex items-center gap-3 border-l pl-3" style={{ borderColor: 'rgba(255,255,255,.08)' }}>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Units</span>
                                <input className="field w-16" type="number" min={0.1} step={0.1}
                                    disabled={targetPayout > 0}
                                    style={{ opacity: targetPayout > 0 ? 0.5 : 1, cursor: targetPayout > 0 ? 'not-allowed' : 'text' }}
                                    value={units} onChange={e => setUnits(+e.target.value)} />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Target Payout</span>
                                <input className="field w-20" type="number" min={0} step={5}
                                    placeholder="Off"
                                    value={targetPayout || ''} onChange={e => setTargetPayout(+e.target.value)} />
                            </div>
                        </div>

                        <button className="btn-success" onClick={handleAddToSlips}>+ Add to Slips</button>
                        <button className="btn-ghost" onClick={handleClearExcluded}>Reset excluded</button>

                        <div className="flex items-center gap-2 border-l pl-3" style={{ borderColor: 'rgba(255,255,255,.08)' }}>
                            <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Run Daily</span>
                            <input className="field w-16" type="number" min={0} step={1}
                                value={runDaily} onChange={e => setRunDaily(+e.target.value)} />
                        </div>

                        {status && (
                            <span className="text-[11px] font-mono ml-auto px-3 py-1 rounded-lg"
                                style={{
                                    color: 'var(--accent)',
                                    background: 'rgba(61,123,255,.08)',
                                }}>
                                {status}
                            </span>
                        )}
                    </div>
                </div>

                {/* Analytics Dashboard */}
                <AnalyticsDashboard
                    legs={preview?.legs ?? []}
                    totalOdds={preview?.total_odds ?? 1}
                />

                {/* Live Preview */}
                <div className="rounded-xl p-5"
                    style={{
                        background: 'linear-gradient(180deg, rgba(24,36,58,.4) 0%, rgba(13,19,33,.3) 100%)',
                        border: '1px solid rgba(255,255,255,.04)',
                    }}>
                    <div className="flex items-center gap-2.5 mb-5">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                                style={{ background: 'var(--accent)' }} />
                            <span className="relative inline-flex rounded-full h-2 w-2"
                                style={{ background: 'var(--accent)' }} />
                        </span>
                        <span className="text-[10px] font-mono tracking-[0.15em] uppercase"
                            style={{ color: 'var(--text-secondary)' }}>
                            Live Preview — updates with every config change
                        </span>
                        {loading && (
                            <span className="ml-auto text-[10px] font-mono animate-pulse px-2 py-0.5 rounded"
                                style={{
                                    color: 'var(--accent)',
                                    background: 'rgba(61,123,255,.08)',
                                }}>building…</span>
                        )}
                    </div>

                    <div style={{ opacity: loading ? 0.5 : 1, transition: 'opacity .2s ease' }}>
                        <BetPreview
                            legs={preview?.legs ?? []}
                            totalOdds={preview?.total_odds ?? 1}
                            pendingUrls={preview?.pending_urls ?? []}
                            onExclude={handleExclude}
                        />
                    </div>
                </div>

                {/* Excluded matches as cards */}
                {(excludedDetails?.length ?? 0) > 0 && (
                    <div className="rounded-xl p-5 mt-5 fade-in"
                        style={{
                            background: 'linear-gradient(180deg, rgba(24,36,58,.3) 0%, rgba(13,19,33,.2) 100%)',
                            border: '1px solid rgba(255,255,255,.04)',
                        }}>
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <span className="text-sm">🚫</span>
                                <span className="text-[10px] font-mono tracking-[0.15em] uppercase"
                                    style={{ color: 'var(--text-secondary)' }}>
                                    Excluded Matches ({excludedDetails.length})
                                </span>
                            </div>
                            <button className="btn-ghost text-[10px]" onClick={handleClearExcluded}>
                                Clear All
                            </button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {excludedDetails.map((item, i) => {
                                const dt = item.datetime
                                    ? new Date(item.datetime).toLocaleString('en-GB', {
                                        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                                    })
                                    : '';
                                return (
                                    <div key={i} className="rounded-lg p-3 group transition-all duration-200"
                                        style={{
                                            background: 'rgba(13,19,33,.6)',
                                            border: '1px solid rgba(255,255,255,.05)',
                                        }}>
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="flex-1 min-w-0">
                                                <p className="font-sans text-[12px] font-medium truncate"
                                                    style={{ color: 'var(--text-secondary)' }}>
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
                                            <button className="btn-icon shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                onClick={() => {
                                                    if (item.reason === "Manually excluded") {
                                                        removeExcluded(item.url).then(() => {
                                                            fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
                                                            triggerPreview(mergedCfg);
                                                        });
                                                    }
                                                }}
                                                title={item.reason === "Manually excluded" ? "Remove from manual exclusions" : "Cannot remove - in pending slip"}
                                                style={{ opacity: item.reason === "Manually excluded" ? undefined : 0.3, cursor: item.reason === "Manually excluded" ? 'pointer' : 'not-allowed' }}>
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
