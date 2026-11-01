import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchServices, toggleService } from '../api/data';
import { useSocket } from '../hooks/useSocket';
import EmptyState, { ServicesEmptyIcon } from '../components/EmptyState';
import ServiceCard from '../components/ServiceCard';
import { TooltipIcon } from '../components/ui';
// NOTE: '../components/ui' resolves to the ui.tsx file, which shadows the ui/
// barrel directory — so NumberField is imported from its own module instead.
import { NumberField } from '../components/ui/NumberField';
import client from '../api/client';
import type { ProfileSchedule, ServicesData, StakeMode } from '../types';

// ── Relative time formatting (local timezone) ────────────────────────────────

function fmtRelativePast(iso: string, now: Date): string {
    const then = new Date(iso);
    const diffSec = Math.max(0, (now.getTime() - then.getTime()) / 1000);
    if (diffSec < 60) return '<1m ago';
    const mins = Math.floor(diffSec / 60);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    const time = then.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    if (days === 1) return `Yesterday ${time}`;
    if (days < 7) return `${then.toLocaleDateString('en-GB', { weekday: 'short' })} ${time}`;
    return `${then.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${time}`;
}

function fmtRelativeFuture(iso: string, now: Date): string {
    const then = new Date(iso);
    const diffSec = (then.getTime() - now.getTime()) / 1000;
    if (diffSec <= 0) return 'Missed';
    const mins = Math.floor(diffSec / 60);
    if (mins < 60) return `in ${mins}m`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) {
        const rem = mins % 60;
        return rem > 0 ? `in ${hours}h ${rem}m` : `in ${hours}h`;
    }
    const time = then.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    const today = new Date(now);
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);
    if (then.toDateString() === tomorrow.toDateString()) return `Tomorrow ${time}`;
    const days = Math.floor((then.getTime() - now.getTime()) / 86400000);
    if (days < 7) return `${then.toLocaleDateString('en-GB', { weekday: 'short' })} ${time}`;
    return `${then.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${time}`;
}

// Client-side next-run prediction so the column updates in-page the moment
// hour/minute change (no reload). Mirrors the server rule: active + own
// window → next local occurrence; otherwise null. Times are interpreted in
// the browser's local timezone, which matches the configured crawler tz in
// practice; the server remains the persisted source of truth on reload.
function computeNextRun(row: ProfileSchedule, now: Date): string | null {
    if (!row.auto_generate) return null;
    if (row.generate_hour == null || row.generate_minute == null) return null;
    const next = new Date(now);
    next.setHours(row.generate_hour, row.generate_minute, 0, 0);
    if (next.getTime() <= now.getTime()) next.setDate(next.getDate() + 1);
    // Guard: invalid date (e.g. from malformed hour/minute) throws RangeError
    if (!Number.isFinite(next.getTime())) return null;
    return next.toISOString();
}

function fmtAbsoluteTooltip(iso: string | null | undefined): string {
    if (!iso) return '';
    const d = new Date(iso);
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return `${d.toLocaleString('en-GB', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
    })} (${tz})`;
}

// ── Per-row stake state (keeps both units and payout in local state) ─────────

interface StakeState {
    mode: StakeMode;
    units: number | null;
    payout: number | null;
}

// ── Component ────────────────────────────────────────────────────────────────

export default function Services() {
    const [data, setData] = useState<ServicesData | null>(null);
    // Per-profile auto-generation rows: null = backend served the legacy
    // shape only, the per-profile section stays hidden and nothing changes.
    const [rows, setRows] = useState<ProfileSchedule[] | null>(null);
    const [rowsSaved, setRowsSaved] = useState('');
    // Timestamp of the last successful save — drives the fade-out of the
    // "✓ Profile schedules saved" indicator so it never lingers forever.
    const [rowsSavedAt, setRowsSavedAt] = useState<number | null>(null);
    const savedFadeRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    // Local stake state per row — keeps both values when switching modes
    const [stakeState, setStakeState] = useState<Record<string, StakeState>>({});
    // Tick every 30s to re-render relative times
    const [, setTick] = useState(0);
    // Auto-save to disk on change (same pattern as the builder tab): only a
    // real row edit sets this flag — loading rows never rewrites disk.
    const dirtyRef = useRef(false);
    const saveDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const load = useCallback(async () => {
        try {
            const d = await fetchServices();
            setData(d);
            const sorted = d.profile_schedules
                ? [...d.profile_schedules].sort(
                    // order may be null/non-numeric on hand-edited YAML: coerce
                    // and tie-break by name so the rendered order is stable.
                    (a, b) => (Number(a.order) || 0) - (Number(b.order) || 0) || a.name.localeCompare(b.name),
                )
                : null;
            setRows(sorted);
            // Initialize stake state from rows
            if (sorted) {
                const ss: Record<string, StakeState> = {};
                for (const r of sorted) {
                    // Seed BOTH values from the row so switching modes (or
                    // navigating away and back) never loses the other field.
                    // Preserve null values (meaning "not provided") so they
                    // don't get overwritten on first save.
                    ss[r.name] = {
                        mode: r.stake_mode ?? 'units',
                        units: r.units,
                        payout: r.target_payout,
                    };
                }
                setStakeState(ss);
            }
        } catch {
            // Network/API failure: keep the loading card rather than crash.
            setData(null);
        }
    }, []);

    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => { load(); }, [load]);

    // Live refresh while sitting on this tab: when the backend finishes a
    // (scheduled or manual) generation it broadcasts slips_updated — refetch
    // so Last generated / Next run / status update without a reload. Skip
    // when there are unsaved local edits pending the debounce.
    useSocket({
        slips_updated: useCallback(() => { if (!dirtyRef.current) void load(); }, [load]),
        service_toggled: useCallback(() => { if (!dirtyRef.current) void load(); }, [load]),
    });

    // Re-render relative times every 30s
    useEffect(() => {
        const interval = setInterval(() => setTick(t => t + 1), 30_000);
        return () => clearInterval(interval);
    }, []);

    // Auto-save rows (debounced 600ms) — the manual Save button is gone.
    useEffect(() => {
        if (!rows?.length || !dirtyRef.current) return;
        if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
        saveDebounceRef.current = setTimeout(async () => {
            dirtyRef.current = false;
            try {
                // Both stake values are ALWAYS persisted — stake_mode only
                // selects which is active. Never send null for either field
                // (backend treats null as "not provided" and keeps the disk
                // value, but we send the real numbers so nothing is ever lost).
                const payload = rows.map(r => {
                    const ss = stakeState[r.name];
                    if (!ss) return r;
                    return {
                        ...r,
                        units: ss.units ?? r.units ?? 1,
                        // Services-tab scope: payout always persists as a real
                        // number (default 1), never null in the YAML.
                        target_payout: ss.payout ?? r.target_payout ?? 1,
                        stake_mode: ss.mode,
                    };
                });
                await client.post('/services/settings', { profile_schedules: payload });
                setRowsSaved('✓ Profile schedules saved');
                setRowsSavedAt(Date.now());
                if (savedFadeRef.current) clearTimeout(savedFadeRef.current);
                // Fade the indicator out after 3s so subsequent saves are visible again
                savedFadeRef.current = setTimeout(() => { setRowsSaved(''); setRowsSavedAt(null); }, 3000);
            } catch {
                dirtyRef.current = true;
                // Clear rowsSavedAt so the error toast restarts its animation and
                // becomes visible (a forwards fill would keep opacity at 0).
                setRowsSavedAt(null);
                setRowsSaved('⚠ Failed to save profile schedules — will retry on next change');
            }
        }, 600);
        return () => {
            if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [rows, stakeState]);

    // Cleanup the saved-indicator fade timer on unmount
    useEffect(() => () => {
        if (savedFadeRef.current) clearTimeout(savedFadeRef.current);
    }, []);

    async function handleToggle(name: string) {
        await toggleService(name);
        await load();
    }

    function patchRow(index: number, patch: Partial<ProfileSchedule>) {
        dirtyRef.current = true;
        setRows(cur => (cur ?? []).map((row, i) => (i === index ? { ...row, ...patch } : row)));
    }

    // Auto toggle: ON seeds Daily at 1; OFF keeps the stored count but gates the fields.
    function patchAuto(index: number, on: boolean) {
        patchRow(index, on ? { auto_generate: true, run_daily_count: Math.max(1, rows?.[index]?.run_daily_count ?? 1) } : { auto_generate: false });
    }

    function patchDaily(index: number, n: number) {
        const clamped = Math.max(1, Math.round(n) || 1);
        patchRow(index, { run_daily_count: clamped, auto_generate: true });
    }

    function patchStakeMode(index: number, mode: StakeMode) {
        const name = rows?.[index]?.name;
        if (!name) return;
        setStakeState(prev => ({ ...prev, [name]: { ...prev[name], mode } }));
        dirtyRef.current = true;
    }

    function patchStakeValue(index: number, val: number) {
        const name = rows?.[index]?.name;
        if (!name) return;
        const ss = stakeState[name];
        if (!ss) return;
        // Both units and payout accept positive fractional values (step 0.1)
        if (ss.mode === 'units') {
            const units = val > 0 ? Math.round(val * 10) / 10 : val;
            setStakeState(prev => ({ ...prev, [name]: { ...prev[name], units } }));
            patchRow(index, { units });
        } else {
            const payout = val > 0 ? Math.round(val * 10) / 10 : val;
            setStakeState(prev => ({ ...prev, [name]: { ...prev[name], payout } }));
            patchRow(index, { target_payout: payout });
        }
    }

    function moveRow(index: number, direction: -1 | 1) {
        dirtyRef.current = true;
        setRows(cur => {
            if (!cur) return cur;
            const target = index + direction;
            if (target < 0 || target >= cur.length) return cur;
            const next = [...cur];
            [next[index], next[target]] = [next[target], next[index]];
            return next.map((row, i) => ({ ...row, order: i }));
        });
    }

    if (!data) return (
        <div>
            <div className="flex items-baseline justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Automation Services
                </h1>
            </div>
            <div className="card text-center py-16">
                <p className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>Loading services…</p>
            </div>
        </div>
    );

    const now = data.server_time ? new Date(data.server_time) : new Date();

    const HEADERS = ['Profile', 'Auto', 'Time', 'Daily', 'Stake', 'Last generated', 'Next run', 'Order'];

    return (
        <div>
            <div className="flex items-baseline justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Automation Services
                </h1>
                <span className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                    Server time: {now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
            </div>

            {/* Guidance only when the generator exists and is off. */}
            {data.services?.generator && !data.services.generator.enabled && (
                <div className="mb-5">
                    <EmptyState
                        icon={<ServicesEmptyIcon />}
                        title="Generate Slips is off"
                        steps={['Enable Generate Slips service', 'Set a per-profile schedule', 'Changes save automatically']}
                        primary={{ label: 'Enable Generate Slips', onClick: () => { void handleToggle('generator'); } }}
                    />
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {/* Service cards — each a third of the row on wide screens */}
                {Object.values(data.services ?? {}).map(svc => (
                    <ServiceCard
                        key={svc.name}
                        info={svc}
                        onToggle={() => handleToggle(svc.name)}
                    />
                ))}

                {/* Per-profile auto-generation schedule: the only scheduling
                    surface. Edits auto-save to disk (same debounce pattern as
                    the builder tab). */}
                {rows && rows.length > 0 && (
                    <div className="card p-4 lg:col-span-3">
                        <div className="flex items-center gap-1.5 mb-4">
                            <p className="font-mono text-[10px] tracking-widest uppercase"
                                style={{ color: 'var(--text-secondary)' }}>Per-Profile Scheduling</p>
                            <TooltipIcon
                                text="Each profile generates at its own time. Auto ON means the profile builds automatically at that time; Daily is how many slips it builds per day; Stake is the units or target payout per slip. Auto OFF keeps your settings but builds nothing (Manual only). Order decides which profile generates first when run times coincide. Changes save automatically."
                                align="right"
                            />
                            {rowsSaved && (
                                <span
                                    className={`ml-auto text-[11px] font-mono ${rowsSavedAt !== null ? 'sched-saved-fade' : ''}`}
                                    style={{ color: rowsSaved.startsWith('✓') ? 'var(--win)' : 'var(--loss)' }}
                                >{rowsSaved}</span>
                            )}
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr className="text-left">
                                        {HEADERS.map(h => (
                                            <th key={h} className="pb-2 pr-3 font-mono text-[10px] tracking-wider uppercase font-normal"
                                                style={{ color: 'var(--text-secondary)' }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((row, i) => {
                                        const autoOn = row.auto_generate;
                                        const gated = autoOn ? 'on' : 'off';
                                        const ss = stakeState[row.name] ?? { mode: 'units' as StakeMode, units: row.units, payout: row.target_payout };
                                        const stakeValue = ss.mode === 'units' ? (ss.units ?? row.units ?? 1) : (ss.payout ?? row.target_payout ?? 1);
                                        // Last generated display
                                        const lastGenText = row.last_generated_at
                                            ? fmtRelativePast(row.last_generated_at, now)
                                            : 'Never';
                                        const lastGenTooltip = row.last_generated_at
                                            ? fmtAbsoluteTooltip(row.last_generated_at) + (row.last_run_error ? `\nError: ${row.last_run_error}` : '')
                                            : 'Never generated';
                                        // Next run display — computed client-side from the
                                        // current row so hour/minute edits update in-page
                                        // without a reload; server value is the fallback.
                                        const nextRunIso = computeNextRun(row, now) ?? row.next_run_at ?? null;
                                        let nextRunText = '—';
                                        let nextRunColor: string | undefined;
                                        let nextRunTooltip = '';
                                        if (!autoOn) {
                                            nextRunText = '—';
                                        } else if (row.last_run_status === 'running') {
                                            nextRunText = 'Generating…';
                                            nextRunTooltip = 'Currently generating slips';
                                        } else if (row.last_run_status === 'failed') {
                                            nextRunText = row.last_generated_at ? `Failed ${fmtRelativePast(row.last_generated_at, now)}` : 'Failed';
                                            nextRunColor = 'var(--loss)';
                                            nextRunTooltip = fmtAbsoluteTooltip(row.last_generated_at) + (row.last_run_error ? `\nError: ${row.last_run_error}` : '');
                                        } else if (nextRunIso) {
                                            nextRunText = fmtRelativeFuture(nextRunIso, now);
                                            nextRunTooltip = fmtAbsoluteTooltip(nextRunIso);
                                        } else {
                                            // Active but no window of its own: never fires → "—"
                                            nextRunTooltip = 'No generation time set — profile never fires automatically';
                                        }

                                        return (
                                            <tr key={row.name} className="border-t" style={{ borderColor: 'var(--border)' }}>
                                                {/* Profile */}
                                                <td className="py-2 pr-3">
                                                    <span className="font-mono text-[12px]" title={row.name}
                                                        style={{ color: 'var(--text-bright)' }}>{row.name}</span>
                                                </td>
                                                {/* Auto — real switch */}
                                                <td className="py-2 pr-3">
                                                    <button
                                                        type="button"
                                                        role="switch"
                                                        aria-checked={autoOn}
                                                        aria-label={`Auto-generation for ${row.name}`}
                                                        className="relative inline-block w-8 h-4 rounded-full transition-colors duration-200 cursor-pointer border"
                                                        style={{
                                                            background: autoOn ? 'var(--accent)' : 'var(--bg-raised)',
                                                            borderColor: autoOn ? 'var(--accent)' : 'var(--border-strong)',
                                                        }}
                                                        onClick={() => patchAuto(i, !autoOn)}
                                                    >
                                                        <span
                                                            className="absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200"
                                                            style={{ transform: autoOn ? 'translateX(16px)' : 'translateX(0)' }}
                                                        />
                                                    </button>
                                                </td>
                                                {/* Time — gated */}
                                                <td className="py-2 pr-3">
                                                    <div className="sched-cell" data-stagger="0">
                                                        <div className="sched-cell-inner flex items-center gap-1" data-gated={gated} inert={!autoOn || undefined} aria-hidden={!autoOn}>
                                                            <select
                                                                aria-label={`Generation hour for ${row.name}`}
                                                                className="field w-[4.5rem]"
                                                                tabIndex={autoOn ? 0 : -1}
                                                                aria-disabled={!autoOn}
                                                                value={row.generate_hour ?? ''}
                                                                onChange={(e) => patchRow(i, { generate_hour: e.target.value === '' ? null : Number(e.target.value) })}
                                                            >
                                                                {/* null in YAML = no window — show an explicit
                                                                    placeholder instead of fabricating 08:00 */}
                                                                {row.generate_hour == null && <option value="">--</option>}
                                                                {Array.from({ length: 24 }, (_, h) => (
                                                                    <option key={h} value={h}>{String(h).padStart(2, '0')}</option>
                                                                ))}
                                                            </select>
                                                            <span className="font-mono text-[12px]" style={{ color: 'var(--text-secondary)' }}>:</span>
                                                            <select
                                                                aria-label={`Generation minute for ${row.name}`}
                                                                className="field w-[4.5rem]"
                                                                tabIndex={autoOn ? 0 : -1}
                                                                aria-disabled={!autoOn}
                                                                value={row.generate_minute ?? ''}
                                                                onChange={(e) => patchRow(i, { generate_minute: e.target.value === '' ? null : Number(e.target.value) })}
                                                            >
                                                                {row.generate_minute == null && <option value="">--</option>}
                                                                {Array.from({ length: 60 }, (_, m) => (
                                                                    <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                                                                ))}
                                                            </select>
                                                        </div>
                                                        <span className="sched-manual-label" data-gated={gated} aria-hidden={autoOn}>Manual only</span>
                                                    </div>
                                                </td>
                                                {/* Daily — gated */}
                                                <td className="py-2 pr-3">
                                                    <div className="sched-cell" data-stagger="1">
                                                        <div className="sched-cell-inner" data-gated={gated} inert={!autoOn || undefined} aria-hidden={!autoOn}>
                                                            <NumberField
                                                                label={`Daily run count for ${row.name}`}
                                                                min={1}
                                                                step={1}
                                                                value={Math.max(1, row.run_daily_count ?? 1)}
                                                                onChange={(n) => patchDaily(i, n)}
                                                                disabled={!autoOn}
                                                                className="w-16"
                                                            />
                                                        </div>
                                                        <span className="sched-manual-label" data-gated={gated} aria-hidden={autoOn}>Manual only</span>
                                                    </div>
                                                </td>
                                                {/* Stake — gated, segmented control + single input */}
                                                <td className="py-2 pr-3">
                                                    <div className="sched-cell" data-stagger="2">
                                                        <div className="sched-cell-inner flex items-center gap-1" data-gated={gated} inert={!autoOn || undefined} aria-hidden={!autoOn}>
                                                            <div
                                                                role="radiogroup"
                                                                aria-label={`Stake mode for ${row.name}`}
                                                                className="seg-control"
                                                            >
                                                                <button
                                                                    type="button"
                                                                    role="radio"
                                                                    aria-checked={ss.mode === 'units'}
                                                                    tabIndex={autoOn && ss.mode === 'units' ? 0 : -1}
                                                                    aria-disabled={!autoOn}
                                                                    onClick={() => patchStakeMode(i, 'units')}
                                                                >Units</button>
                                                                <button
                                                                    type="button"
                                                                    role="radio"
                                                                    aria-checked={ss.mode === 'payout'}
                                                                    tabIndex={autoOn && ss.mode === 'payout' ? 0 : -1}
                                                                    aria-disabled={!autoOn}
                                                                    onClick={() => patchStakeMode(i, 'payout')}
                                                                >Payout</button>
                                                            </div>
                                                            <NumberField
                                                                label={ss.mode === 'units' ? `Units for ${row.name}` : `Target payout for ${row.name}`}
                                                                value={stakeValue}
                                                                min={0.1}
                                                                step={0.1}
                                                                disabled={!autoOn}
                                                                className="w-24"
                                                                onChange={(n) => patchStakeValue(i, n)}
                                                            />
                                                        </div>
                                                        <span className="sched-manual-label" data-gated={gated} aria-hidden={autoOn}>Manual only</span>
                                                    </div>
                                                </td>
                                                {/* Last generated */}
                                                <td className="py-2 pr-3">
                                                    <span
                                                        className="font-mono text-[12px]"
                                                        style={{ color: row.last_run_status === 'failed' ? 'var(--loss)' : 'var(--text-secondary)' }}
                                                        title={lastGenTooltip}
                                                    >
                                                        {row.last_run_status === 'running' ? (
                                                            <><span className="sched-spinner" />Generating…</>
                                                        ) : lastGenText}
                                                    </span>
                                                </td>
                                                {/* Next run */}
                                                <td className="py-2 pr-3">
                                                    <span
                                                        className="font-mono text-[12px]"
                                                        style={{ color: nextRunColor ?? 'var(--text-secondary)' }}
                                                        title={nextRunTooltip}
                                                    >
                                                        {nextRunText}
                                                    </span>
                                                </td>
                                                {/* Order */}
                                                <td className="py-2">
                                                    <div className="flex items-center gap-1" title="Order decides which profile generates first when run times coincide.">
                                                        <button
                                                            className="btn-ghost"
                                                            aria-label={`Move ${row.name} up`}
                                                            disabled={i === 0}
                                                            onClick={() => moveRow(i, -1)}
                                                        >↑</button>
                                                        <button
                                                            className="btn-ghost"
                                                            aria-label={`Move ${row.name} down`}
                                                            disabled={i === rows.length - 1}
                                                            onClick={() => moveRow(i, 1)}
                                                        >↓</button>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
