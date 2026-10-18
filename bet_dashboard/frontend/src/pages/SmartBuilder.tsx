import { useCallback, useEffect, useRef, useState } from 'react';
import { Autocomplete, TextField } from '@mui/material';
import BuilderPanel from '../components/BuilderPanel';
import { BetPreview } from '../components/BetComponents';
import EmptyState, { BuildEmptyIcon } from '../components/EmptyState';
import { FirstSlipToast } from '../components/OnboardingTour';
import { markFirstSlip } from '../components/tourStorage';
import AnalyticsDashboard from '../components/AnalyticsDashboard';
import { TooltipIcon } from '../components/ui';
import {
    fetchPreview, fetchProfiles, saveProfile, deleteProfile,
    fetchExcludedDetails, addExcluded, removeExcluded, clearExcluded, addSlip,
    fetchLeagues, fetchSourcesConfig,
    type ExcludedMatch
} from '../api/data';
import type { GlobalFilters } from '../components/Layout';
import type { BuilderConfig, Profile, ProfilesMap, PreviewResult, ManualLegIn } from '../types';

const DEFAULT_CFG: BuilderConfig = {
    target_odds: 3.0, target_legs: 3, max_legs_overflow: null,
    consensus_floor: 50, min_odds: 1.05, included_markets: null, included_leagues: null,
    tolerance_factor: null, stop_threshold: null, min_legs_fill_ratio: 0.7,
    quality_vs_balance: 0.5, consensus_vs_sources: 0.5,
    date_from: null, date_to: null,
    excluded_sources: null,
    consensus_shrinkage_k: null,
    min_source_edge: null,
    max_single_leg_odds: null,
    tol_lower: null,
    tol_upper: null,
    balance_decay: 'gaussian',
    min_pick_quality: null,
    odds_movement_weight: null,
    odds_movement_strength_min: null,
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
        return saved ? (JSON.parse(saved).units ?? 1.0) : 1.0;
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
    const [availableLeagues, setAvailableLeagues] = useState<string[]>([]);
    const [availableSources, setAvailableSources] = useState<string[]>([]);
    const [status, setStatus] = useState('');
    const [milestoneOpen, setMilestoneOpen] = useState(false);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Persist state to localStorage
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            cfg: { ...cfg, date_from: null, date_to: null },
            activeName,
            units,
            targetPayout
        }));
    }, [cfg, activeName, units, targetPayout]);

    // Load profiles + excluded on mount
    useEffect(() => {
        // Legacy payloads kept a `runDaily` key that no longer exists in this
        // page (moved to Services); drop it once so storage stays clean
        // (AC-infra: removed keys are cleaned safely on load, review F16).
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                const parsed = JSON.parse(saved) as Record<string, unknown>;
                if ('runDaily' in parsed) {
                    delete parsed.runDaily;
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
                }
            } catch {
                // Corrupt payload: leave it for the writer to overwrite.
            }
        }
        fetchProfiles().then(p => setProfiles(p ?? {})).catch(() => setProfiles({}));
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
        fetchLeagues().then(setAvailableLeagues).catch(() => setAvailableLeagues([]));
        fetchSourcesConfig().then(c => setAvailableSources(c.sources)).catch(() => setAvailableSources([]));
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

    // Trigger preview when refreshKey or global filters change. Deliberate
    // dep omission: cfg is NOT a dep — config changes trigger the preview
    // directly in handleCfgChange (adding cfg here would double-fire).
    useEffect(() => { triggerPreview(mergedCfg); }, [refreshKey, filters.dateFrom, filters.dateTo]); // eslint-disable-line react-hooks/exhaustive-deps -- deliberate: cfg handled in handleCfgChange

    // Force preview refresh when excluded_sources changes (bypass debounce for immediate feedback)
    const lastExcluded = useRef<string | null>(null);
    useEffect(() => {
        if (lastExcluded.current === JSON.stringify(cfg.excluded_sources ?? null)) return;
        lastExcluded.current = JSON.stringify(cfg.excluded_sources ?? null);
        triggerPreview({ ...cfg, date_from: filters.dateFrom || null, date_to: filters.dateTo || null });
    }, [cfg.excluded_sources, filters.dateFrom, filters.dateTo, triggerPreview]); // eslint-disable-line react-hooks/exhaustive-deps -- cfg is read, not tracked: exclusion-only trigger with a change guard

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
    }, [targetPayout, preview?.total_odds, preview?.legs, preview?.legs.length, cfg.target_odds, units]);

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

    function loadProfile(name: string, data: Profile) {
        const next: BuilderConfig = {
            target_odds: data.target_odds ?? 3,
            target_legs: data.target_legs ?? 3,
            max_legs_overflow: data.max_legs_overflow ?? null,
            consensus_floor: data.consensus_floor ?? 50,
            min_odds: data.min_odds ?? 1.05,
            included_markets: data.included_markets ?? null,
            included_leagues: data.included_leagues ?? null,
            tolerance_factor: data.tolerance_factor ?? null,
            stop_threshold: data.stop_threshold ?? null,
            min_legs_fill_ratio: data.min_legs_fill_ratio ?? 0.7,
            quality_vs_balance: data.quality_vs_balance ?? 0.5,
            consensus_vs_sources: data.consensus_vs_sources ?? 0.5,
            date_from: null,
            date_to: null,
            excluded_sources: data.excluded_sources ?? null,
            consensus_shrinkage_k: data.consensus_shrinkage_k ?? null,
            min_source_edge: data.min_source_edge ?? null,
            max_single_leg_odds: data.max_single_leg_odds ?? null,
            tol_lower: data.tol_lower ?? null,
            tol_upper: data.tol_upper ?? null,
            balance_decay: data.balance_decay ?? 'gaussian',
            min_pick_quality: data.min_pick_quality ?? null,
            odds_movement_weight: data.odds_movement_weight ?? null,
            odds_movement_strength_min: data.odds_movement_strength_min ?? null,
        };
        setCfg(next);
        setActiveName(name);
        setUnits(data.units ?? 1);
        setTargetPayout(data.target_payout ?? 0);
        triggerPreview({ ...next, date_from: filters.dateFrom || null, date_to: filters.dateTo || null });
    }

    async function handleSaveProfile() {
        const clean = activeName.replace(/[^a-z0-9_-]/gi, '').toLowerCase();
        if (!clean || clean === 'manual') {
            setStatus('Enter a profile name first.'); return;
        }
        // Profile accepts null dates (cycle-6 pin: runtime-only keys nulled on
        // disk) — null them explicitly instead of destructuring them out.
        await saveProfile({ name: clean, ...cfg, date_from: null, date_to: null, units, target_payout: targetPayout });
        const updated = await fetchProfiles();
        setProfiles(updated ?? {});
        setStatus(`✓ Profile '${clean}' saved`);
    }

    async function handleDeleteProfile() {
        if (!activeName || activeName === 'manual') return;
        // Deleting a name that is not a saved profile would either 404 or
        // remove the wrong file after a typo (review F9) — block and tell the
        // user instead.
        if (!(activeName in profiles)) {
            setStatus(`'${activeName}' is not a saved profile`);
            return;
        }
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
            league: leg.league,
            predictions: leg.predictions || [],
        }));

        const id = await addSlip(activeName, manualLegs, units);
        // AC-06: first successful addSlip (Build) counts as first slip.
        if (markFirstSlip()) setMilestoneOpen(true);
        setStatus(`✓ Slip #${id} added to '${activeName}'`);
        triggerPreview(mergedCfg);
        fetchExcludedDetails().then(d => setExcludedDetails(d ?? [])).catch(() => setExcludedDetails([]));
    }

    return (
        <>
        <div className="flex flex-col xl:flex-row gap-6 lg:gap-8 min-h-screen">
            {/* ── Left Sidebar — Responsive width ─────────────────────────────── */}
            <div className="w-full xl:w-[350px] 2xl:w-[400px] shrink-0">
                <div className="sticky top-4 space-y-4">
                    <div className="rounded-xl overflow-hidden"
                        style={{
                            background: 'linear-gradient(180deg, var(--bg-base) 0%, var(--bg-surface) 100%)',
                            border: '1px solid var(--border)',
                            boxShadow: 'var(--shadow-lg)',
                        }}>
                        <div className="px-3 py-4">
                            <BuilderPanel
                                cfg={cfg}
                                availableLeagues={availableLeagues}
                                availableSources={availableSources}
                                onChange={handleCfgChange}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Main Content — Flexible ─────────────────────────────────────── */}
            <div className="flex-1 min-w-0">
                {/* Top Header / Management Bar */}
                <div className="rounded-xl px-5 py-3.5 mb-5"
                    style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                        backdropFilter: 'blur(10px)',
                    }}>
                    {/* AC-03: page heading in the management bar */}
                    <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>Build</h1>
                    <div className="flex items-start gap-3 flex-wrap">
                        {/* Zone 1 — identity: pick a saved profile or type a new name */}
                        <div className="flex items-center gap-2">
                            <Autocomplete
                                freeSolo
                                sx={{
                                    width: 220,
                                    '& .MuiOutlinedInput-root': {
                                        background: 'var(--bg-raised)',
                                        color: 'var(--text-primary)',
                                        fontSize: 12,
                                    },
                                }}
                                options={Object.keys(profiles)}
                                value={activeName}
                                inputValue={activeName}
                                onInputChange={(_, next) => setActiveName(next ?? '')}
                                onChange={(_, next) => {
                                    if (typeof next === 'string' && profiles[next]) {
                                        loadProfile(next, profiles[next]);
                                    }
                                }}
                                renderInput={(params) => (
                                    <TextField {...params} placeholder="profile name" />
                                )}
                            />
                        </div>

                        {/* Zone 3 — actions: persist / discard the profile above */}
                        <div className="flex items-center gap-2 border-l pl-3" style={{ borderColor: 'var(--border)' }}>
                            <button className="btn-primary" data-tour="build-save" onClick={handleSaveProfile}>Save</button>
                            <button className="btn-danger" onClick={handleDeleteProfile}>Delete</button>
                        </div>

                        {/* Zone 2 — stake sizing for MANUAL bets only. Slips produced by
                            auto-generation use the units/target payout set in Services. */}
                        <div className="flex items-center gap-3 border-l pl-3" style={{ borderColor: 'var(--border)' }}>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Units</span>
                                <TooltipIcon text="Units for a MANUAL bet placed from this builder. Slips produced by auto-generation use the units configured on the Services page." align="right" />
                                <input className="field w-16" type="number" min={0.1} step={0.1}
                                    disabled={targetPayout > 0}
                                    style={{ opacity: targetPayout > 0 ? 0.5 : 1, cursor: targetPayout > 0 ? 'not-allowed' : 'text' }}
                                    value={units} onChange={e => setUnits(+e.target.value)} />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>Target Payout</span>
                                <TooltipIcon text="Automatically calculates units based on desired payout. Enter your target payout amount and the system will determine the required units to achieve it." align="right" />
                                <input className="field w-20" type="number" min={0} step={5}
                                    placeholder="Off"
                                    value={targetPayout || ''} onChange={e => setTargetPayout(+e.target.value)} />
                            </div>
                        </div>

                        {status && (
                            <span className="text-[11px] font-mono ml-auto px-3 py-1 rounded-lg"
                                style={{
                                    color: 'var(--accent)',
                                    background: 'var(--accent-glow)',
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
                    data-tour="build-preview"
                    style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
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
                        {/* Add to Slips lives with the legs it commits — hidden when
                            the preview is empty (issue #41 note 7). */}
                        {(preview?.legs?.length ?? 0) > 0 && (
                            <button className="btn-success ml-auto" onClick={handleAddToSlips}>+ Add to Slips</button>
                        )}
                        {loading && (
                            <span className="ml-auto text-[10px] font-mono animate-pulse px-2 py-0.5 rounded"
                                style={{
                                    color: 'var(--accent)',
                                    background: 'var(--accent-glow)',
                                }}>building…</span>
                        )}
                    </div>

                    <div style={{ opacity: loading ? 0.5 : 1, transition: 'opacity .2s ease' }}>
                        {/* AC-03: replace BetPreview empty branch only; populated cards stay */}
                        {!(preview?.legs?.length) ? (
                            <EmptyState
                                icon={<BuildEmptyIcon />}
                                title="No preview yet"
                                steps={['Select a preset', 'Test config', 'Add to Slips']}
                                primary={{
                                    label: 'Select a Preset',
                                    onClick: () => {
                                        const target = document.querySelector<HTMLInputElement>('input[placeholder="profile name"]');
                                        target?.focus();
                                        target?.scrollIntoView({ block: 'center' });
                                    },
                                }}
                                secondary={{ label: 'Add to Slips', onClick: () => { void handleAddToSlips(); } }}
                            />
                        ) : (
                            <BetPreview
                                legs={preview.legs}
                                totalOdds={preview.total_odds ?? 1}
                                pendingUrls={preview.pending_urls ?? []}
                                onExclude={handleExclude}
                                minStrength={cfg.odds_movement_strength_min ?? undefined}
                            />
                        )}
                    </div>
                </div>

                {/* Excluded matches as cards */}
                {(excludedDetails?.length ?? 0) > 0 && (
                    <div className="rounded-xl p-5 mt-5 fade-in"
                        style={{
                            background: 'var(--bg-card)',
                            border: '1px solid var(--border)',
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
                                            background: 'var(--bg-card)',
                                            border: '1px solid var(--border)',
                                        }}>
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="flex-1 min-w-0">
                                                <p className="font-sans text-[12px] font-medium truncate"
                                                    style={{ color: 'var(--text-secondary)' }}>
                                                    {item.match_name}
                                                </p>
                                                {dt && (
                                                    <p className="text-[10px] font-mono mt-0.5"
                                                        style={{ color: 'var(--text-secondary)' }}>
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
        <FirstSlipToast open={milestoneOpen} onClose={() => setMilestoneOpen(false)} />
        </>
    );
}
