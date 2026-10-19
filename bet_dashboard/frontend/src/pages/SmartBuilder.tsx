import { useCallback, useEffect, useRef, useState } from 'react';
import BuilderPanel from '../components/BuilderPanel';
import { BetPreview } from '../components/BetComponents';
import EmptyState, { BuildEmptyIcon } from '../components/EmptyState';
import { FirstSlipToast } from '../components/OnboardingTour';
import { markFirstSlip } from '../components/tourStorage';
import AnalyticsDashboard from '../components/AnalyticsDashboard';
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

// Units and Target Payout are mutually exclusive: the filled one drives the
// slip stake, the other shows a live calculated preview while disabled.
interface AddToSlipsModalProps {
    legsCount: number;
    totalOdds: number;
    units: number;
    targetPayout: number;
    onUnitsChange: (units: number) => void;
    onTargetPayoutChange: (payout: number) => void;
    onConfirm: () => void;
    onClose: () => void;
}

function AddToSlipsModal({
    legsCount, totalOdds, units, targetPayout,
    onUnitsChange, onTargetPayoutChange, onConfirm, onClose,
}: AddToSlipsModalProps) {
    // Escape closes (matches SlipDetailModal overlay contract).
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleEscape);
        return () => window.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    // Both inputs start EMPTY on open (no placeholder text). Typing a number
    // in one field claims it: the other field becomes disabled and shows the
    // live calculated preview. Clearing the field releases it back to empty
    // and re-enables the other input. One field is active at a time.
    const [mode, setMode] = useState<'units' | 'payout' | null>(null);
    const [unitsText, setUnitsText] = useState('');
    const [payoutText, setPayoutText] = useState('');

    const payoutActive = mode === 'payout';
    const unitsActive = mode === 'units';
    // required units for the typed payout = payout / total odds, 1dp
    const previewUnits = Math.round((targetPayout / (totalOdds || 1)) * 10) / 10;
    // resulting payout for the typed units = units × total odds, 1dp
    const previewPayout = Math.round(units * (totalOdds || 1) * 10) / 10;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
            <div role="dialog" aria-modal="true" aria-label="Add to Slips"
                className="relative w-full max-w-md rounded-xl shadow-2xl"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                <div className="px-5 py-4 border-b flex items-center justify-between"
                    style={{ borderColor: 'var(--border)' }}>
                    <h2 className="text-lg font-display font-bold" style={{ color: 'var(--text-bright)' }}>
                        Add to Slips
                    </h2>
                    <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>
                        {legsCount} legs @ {totalOdds.toFixed(2)}
                    </span>
                </div>
                <div className="px-5 py-4 space-y-4">
                    <p className="text-[11px] font-sans" style={{ color: 'var(--text-secondary)' }}>
                        Units and Target Payout are mutually exclusive — fill one, the other previews the calculated value.
                    </p>
                    <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono uppercase w-24" style={{ color: 'var(--text-secondary)' }}>Units</span>
                        <input
                            aria-label="Units"
                            className="field w-24"
                            type="number"
                            min={0.1}
                            step={0.1}
                            autoFocus
                            disabled={payoutActive}
                            style={{
                                opacity: payoutActive ? 0.5 : 1,
                                cursor: payoutActive ? 'not-allowed' : 'text',
                                color: payoutActive ? 'var(--text-secondary)' : undefined,
                            }}
                            value={payoutActive ? String(previewUnits) : unitsText}
                            onChange={e => {
                                const v = e.target.value;
                                setUnitsText(v);
                                setMode(v === '' ? null : 'units');
                                onUnitsChange(v === '' ? 1 : +v);
                            }} />
                        {payoutActive && (
                            <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>preview</span>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        <span className="text-[10px] font-mono uppercase w-24" style={{ color: 'var(--text-secondary)' }}>Target Payout</span>
                        <input
                            aria-label="Target Payout"
                            className="field w-24"
                            type="number"
                            min={0}
                            step={0.1}
                            disabled={unitsActive}
                            style={{
                                opacity: unitsActive ? 0.5 : 1,
                                cursor: unitsActive ? 'not-allowed' : 'text',
                                color: unitsActive ? 'var(--text-secondary)' : undefined,
                            }}
                            value={unitsActive ? String(previewPayout) : payoutText}
                            onChange={e => {
                                const v = e.target.value;
                                setPayoutText(v);
                                setMode(v === '' ? null : 'payout');
                                onTargetPayoutChange(v === '' ? 0 : +v);
                            }} />
                        {unitsActive && (
                            <span className="text-[10px] font-mono" style={{ color: 'var(--text-secondary)' }}>preview</span>
                        )}
                    </div>
                </div>
                <div className="px-5 py-4 border-t flex justify-end gap-2"
                    style={{ borderColor: 'var(--border)' }}>
                    <button className="btn-ghost" onClick={onClose}>Cancel</button>
                    <button className="btn-success" onClick={onConfirm}>Add to Slips</button>
                </div>
            </div>
        </div>
    );
}

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
    // The 'manual' profile is gone: the active selection is always a saved
    // profile and defaults to the first one served by the backend.
    const [activeName, setActiveName] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? (JSON.parse(saved).activeName || '') : '';
    });
    const [units, setUnits] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? (JSON.parse(saved).units ?? 1.0) : 1.0;
    });

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
    const [slipModalOpen, setSlipModalOpen] = useState(false);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    // Auto-save to the active profile: only a real config edit (or a stake
    // edit) sets this flag — profile switches/loads must not rewrite disk.
    const dirtyRef = useRef(false);
    const saveDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        // page (moved to Services); drop it once so storage stays clean.
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

    // Once profiles arrive: default-select the first profile when nothing is
    // selected (or the persisted selection no longer exists).
    useEffect(() => {
        if (Object.keys(profiles).length === 0) return;
        if (activeName && activeName in profiles) return;
        const first = Object.keys(profiles)[0];
        setActiveName(first);
        const data = profiles[first];
        setCfg(cfgFromProfile(data));
        setUnits(data.units ?? 1);
        setTargetPayout(data.target_payout ?? 0);
        dirtyRef.current = false;
        // preview triggered by the effect below via mergedCfg dependency chain
    }, [profiles]); // eslint-disable-line react-hooks/exhaustive-deps -- one-shot default selection when profiles load

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

    function profileFromConfig(name: string) {
        return { name, ...cfg, date_from: null, date_to: null, units, target_payout: targetPayout };
    }

    function handleCfgChange(next: BuilderConfig) {
        setCfg(next);
        dirtyRef.current = true;
        setStatus('');
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

    // Auto-save to the ACTIVE profile (debounced). The manual Save button is
    // gone — every config/stake change lands on the selected profile on disk.
    useEffect(() => {
        if (!activeName || !dirtyRef.current) return;
        if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
        saveDebounceRef.current = setTimeout(async () => {
            dirtyRef.current = false;
            try {
                await saveProfile(profileFromConfig(activeName));
                const updated = await fetchProfiles();
                setProfiles(updated ?? {});
                setStatus(`✓ Saved to '${activeName}'`);
            } catch {
                dirtyRef.current = true;
                setStatus('⚠ Save failed — will retry on next change');
            }
        }, 600);
        return () => {
            if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
        };
    }, [cfg, activeName, units, targetPayout]); // eslint-disable-line react-hooks/exhaustive-deps -- profileFromConfig/filters read at call time; deps cover every input to the payload

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

    function cfgFromProfile(data: Profile): BuilderConfig {
        return {
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
    }

    function loadProfile(name: string, data: Profile) {
        setCfg(cfgFromProfile(data));
        setActiveName(name);
        setUnits(data.units ?? 1);
        setTargetPayout(data.target_payout ?? 0);
        dirtyRef.current = false;
        triggerPreview({ ...cfgFromProfile(data), date_from: filters.dateFrom || null, date_to: filters.dateTo || null });
    }

    // Per-card delete. Deleting the ACTIVE profile re-selects the first
    // remaining profile (there is no 'manual' fallback anymore).
    async function handleDeleteProfile(name: string) {
        if (!name || !(name in profiles)) {
            setStatus(`'${name}' is not a saved profile`);
            return;
        }
        await deleteProfile(name);
        const updated = await fetchProfiles();
        setProfiles(updated ?? {});
        const remaining = Object.keys(updated ?? {});
        if (activeName === name) {
            if (remaining.length > 0) {
                loadProfile(remaining[0], (updated as ProfilesMap)[remaining[0]]);
            } else {
                setActiveName('');
            }
        }
        setStatus(`Deleted '${name}'`);
    }

    // '+' creates a profile copying the CURRENT builder config. Name is the
    // smallest unused new{N} — deterministic even after deletions.
    const createBusy = useRef(false);
    async function handleCreateProfile() {
        // Two fast clicks would both read the same stale profiles map and
        // both save 'new1' (POST overwrites same-name profiles) — guard the
        // in-flight save so '+' is single-shot until the refetch lands.
        if (createBusy.current) return;
        createBusy.current = true;
        try {
            let n = 1;
            while (`new${n}` in profiles) n += 1;
            const name = `new${n}`;
            const payload = profileFromConfig(name);
            await saveProfile(payload);
            const updated = await fetchProfiles();
            setProfiles(updated ?? {});
            loadProfile(name, updated?.[name] ?? (payload as unknown as Profile));
            setStatus(`✓ Saved to '${name}'`);
        } finally {
            createBusy.current = false;
        }
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
        setSlipModalOpen(false);
        // first successful addSlip (Build) counts as first slip.
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
                    <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>Profiles</h1>
                    <div className="flex items-start gap-3 flex-wrap mt-2">
                        {/* Profile cards: every saved profile renders as a card;
                            click selects+loads it; edits auto-save to it. */}
                        <div className="flex items-center gap-2 flex-wrap" data-testid="profile-cards">
                            {Object.keys(profiles).map(name => {
                                const active = activeName === name;
                                return (
                                    <div key={name}
                                        data-profile-chip={name}
                                        className="inline-flex items-center rounded-xl px-1 transition-all duration-200"
                                        style={{
                                            background: active
                                                ? 'linear-gradient(180deg, var(--accent-glow) 0%, var(--bg-raised) 100%)'
                                                : 'var(--bg-raised)',
                                            border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                                            boxShadow: active ? 'var(--shadow-md)' : 'none',
                                        }}>
                                        {/* select the profile */}
                                        <button
                                            type="button"
                                            aria-pressed={active}
                                            onClick={() => loadProfile(name, profiles[name])}
                                            className="px-3 py-2 text-sm font-sans font-semibold rounded-xl"
                                            style={{
                                                color: active ? 'var(--accent)' : 'var(--text-primary)',
                                                cursor: 'pointer',
                                                background: 'transparent',
                                                border: 'none',
                                            }}>
                                            {name}
                                        </button>
                                        {/* per-card X: transparent until hover, then loss-red */}
                                        <button
                                            type="button"
                                            className="w-6 h-6 mr-1 flex items-center justify-center rounded-lg transition-all duration-200"
                                            style={{
                                                color: 'var(--text-secondary)',
                                                background: 'transparent',
                                                border: '1px solid transparent',
                                                opacity: 0.55,
                                                cursor: 'pointer',
                                            }}
                                            title={`Delete profile '${name}'`}
                                            aria-label={`Delete profile '${name}'`}
                                            onMouseEnter={e => {
                                                e.currentTarget.style.opacity = '1';
                                                e.currentTarget.style.color = 'var(--loss)';
                                                e.currentTarget.style.background = 'var(--loss-glow, rgba(239, 68, 68, 0.12))';
                                                e.currentTarget.style.borderColor = 'var(--loss-border, rgba(239, 68, 68, 0.35))';
                                            }}
                                            onMouseLeave={e => {
                                                e.currentTarget.style.opacity = '0.55';
                                                e.currentTarget.style.color = 'var(--text-secondary)';
                                                e.currentTarget.style.background = 'transparent';
                                                e.currentTarget.style.borderColor = 'transparent';
                                            }}
                                            onClick={() => void handleDeleteProfile(name)}
                                        >✕</button>
                                    </div>
                                );
                            })}
                            {/* trailing '+': same card treatment, accent-tinted */}
                            <button
                                aria-label="Create new profile"
                                className="inline-flex items-center justify-center w-9 h-9 rounded-xl text-lg font-bold transition-all duration-200"
                                style={{
                                    background: activeName && profiles[activeName]
                                        ? 'linear-gradient(180deg, var(--accent-glow) 0%, var(--bg-raised) 100%)'
                                        : 'var(--bg-raised)',
                                    border: `1px solid ${activeName && profiles[activeName] ? 'var(--accent)' : 'var(--border)'}`,
                                    color: 'var(--accent)',
                                    cursor: 'pointer',
                                    boxShadow: 'var(--shadow-sm, none)',
                                }}
                                title="Create a new profile from the current config"
                                onClick={() => void handleCreateProfile()}
                            >+</button>
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
                        {/* Add to Slips OPENS the confirmation modal (Units +
                            Target Payout live there); confirm posts the slip.
                            Hidden when the preview is empty. */}
                        {(preview?.legs?.length ?? 0) > 0 && (
                            <button className="btn-success ml-auto" onClick={() => setSlipModalOpen(true)}>+ Add to Slips</button>
                        )}
                        {loading && (
                            <span className="ml-auto text-[10px] font-mono animate-pulse px-2 py-0.5 rounded"
                                style={{ color: 'var(--accent)', background: 'var(--accent-glow)' }}>building…</span>
                        )}
                    </div>

                    <div style={{ opacity: loading ? 0.5 : 1, transition: 'opacity .2s ease' }}>
                        {!(preview?.legs?.length) ? (
                            <EmptyState
                                icon={<BuildEmptyIcon />}
                                title="No preview yet"
                                steps={['Select a profile', 'Tweak the config', 'Add to Slips']}
                                primary={{
                                    label: 'Select a Profile',
                                    onClick: () => {
                                        // Focus the first profile card button so
                                        // keyboard users land on the control.
                                        const target = document.querySelector<HTMLElement>('[data-testid="profile-cards"] button');
                                        target?.focus();
                                        target?.scrollIntoView({ block: 'center' });
                                    },
                                }}
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
        {slipModalOpen && (
            <AddToSlipsModal
                legsCount={preview?.legs?.length ?? 0}
                totalOdds={preview?.total_odds ?? 1}
                units={units}
                targetPayout={targetPayout}
                onUnitsChange={(u) => { setUnits(u); setTargetPayout(0); dirtyRef.current = true; }}
                onTargetPayoutChange={(p) => { setTargetPayout(p); dirtyRef.current = true; }}
                onConfirm={() => void handleAddToSlips()}
                onClose={() => setSlipModalOpen(false)}
            />
        )}
        <FirstSlipToast open={milestoneOpen} onClose={() => setMilestoneOpen(false)} />
        </>
    );
}
