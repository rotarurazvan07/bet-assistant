import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchServices, toggleService } from '../api/data';
import EmptyState, { ServicesEmptyIcon } from '../components/EmptyState';
import ServiceCard from '../components/ServiceCard';
import { TooltipIcon } from '../components/ui';
import client from '../api/client';
import type { ProfileSchedule, ServicesData } from '../types';

export default function Services() {
    const [data, setData] = useState<ServicesData | null>(null);
    // Per-profile auto-generation rows: null = backend served the legacy
    // shape only, the per-profile section stays hidden and nothing changes.
    const [rows, setRows] = useState<ProfileSchedule[] | null>(null);
    const [rowsSaved, setRowsSaved] = useState('');
    // Auto-save to disk on change (same pattern as the builder tab): only a
    // real row edit sets this flag — loading rows never rewrites disk.
    const dirtyRef = useRef(false);
    const saveDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const load = useCallback(async () => {
        try {
            const d = await fetchServices();
            setData(d);
            setRows(d.profile_schedules
                ? [...d.profile_schedules].sort(
                    // order may be null/non-numeric on hand-edited YAML: coerce
                    // and tie-break by name so the rendered order is stable.
                    (a, b) => (Number(a.order) || 0) - (Number(b.order) || 0) || a.name.localeCompare(b.name),
                )
                : null);
        } catch {
            // Network/API failure: keep the loading card rather than crash.
            setData(null);
        }
    }, []);

    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => { load(); }, [load]);

    // Auto-save rows (debounced 600ms) — the manual Save button is gone.
    useEffect(() => {
        if (!rows?.length || !dirtyRef.current) return;
        if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
        saveDebounceRef.current = setTimeout(async () => {
            dirtyRef.current = false;
            try {
                await client.post('/services/settings', { profile_schedules: rows });
                setRowsSaved('✓ Profile schedules saved');
            } catch {
                dirtyRef.current = true;
                setRowsSaved('⚠ Failed to save profile schedules — will retry on next change');
            }
        }, 600);
        return () => {
            if (saveDebounceRef.current) clearTimeout(saveDebounceRef.current);
        };
    }, [rows]);

    async function handleToggle(name: string) {
        await toggleService(name);
        await load();
    }

    function patchRow(index: number, patch: Partial<ProfileSchedule>) {
        dirtyRef.current = true;
        setRows(cur => (cur ?? []).map((row, i) => (i === index ? { ...row, ...patch } : row)));
    }

    // Units and Target Payout are mutually exclusive: writing one blocks the
    // other. Typing in units clears the payout; typing a payout keeps units
    // stored but the units input becomes read-only via the disabled flag.
    function patchUnits(index: number, raw: string) {
        const units = raw === '' ? 0 : Number(raw);
        patchRow(index, { units, target_payout: units > 0 ? null : (rows?.[index]?.target_payout ?? null) });
    }

    function patchPayout(index: number, raw: string) {
        patchRow(index, { target_payout: raw === '' ? null : Number(raw) });
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
                    surface. The global schedule time is gone — each profile
                    runs at its own row time with no fallback. Edits auto-save
                    to disk (same debounce pattern as the builder tab). */}
                {rows && rows.length > 0 && (
                    <div className="card p-4 lg:col-span-3">
                        <div className="flex items-center gap-1.5 mb-4">
                            <p className="font-mono text-[10px] tracking-widest uppercase"
                                style={{ color: 'var(--text-secondary)' }}>Per-Profile Scheduling</p>
                            <TooltipIcon
                                text="Each profile generates at its own time. Units and Target Payout are mutually exclusive — fill one, the other is blocked. Daily run count caps how many slips that profile builds per day. Changes save automatically."
                                align="right"
                            />
                            {rowsSaved && (
                                <span className="ml-auto text-[11px] font-mono" style={{ color: 'var(--win)' }}>{rowsSaved}</span>
                            )}
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr className="text-left">
                                        {['Profile', 'Time', 'Daily', 'Auto', 'Units', 'Target Payout', 'Order'].map(h => (
                                            <th key={h} className="pb-2 pr-3 font-mono text-[10px] tracking-wider uppercase font-normal"
                                                style={{ color: 'var(--text-secondary)' }}>{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows.map((row, i) => {
                                        const payoutOn = row.target_payout != null && row.target_payout > 0;
                                        const unitsOn = !payoutOn && (row.units ?? 0) > 0;
                                        return (
                                            <tr key={row.name} className="border-t" style={{ borderColor: 'var(--border)' }}>
                                                <td className="py-2 pr-3">
                                                    <span className="font-mono text-[12px]" title={row.name}
                                                        style={{ color: 'var(--text-bright)' }}>{row.name}</span>
                                                </td>
                                                <td className="py-2 pr-3">
                                                    <div className="flex items-center gap-1">
                                                        <select
                                                            aria-label={`Generation hour for ${row.name}`}
                                                            className="field w-20"
                                                            value={row.generate_hour}
                                                            onChange={(e) => patchRow(i, { generate_hour: Number(e.target.value) })}
                                                        >
                                                            {Array.from({ length: 24 }, (_, h) => (
                                                                <option key={h} value={h}>{String(h).padStart(2, '0')}</option>
                                                            ))}
                                                        </select>
                                                        <span className="font-mono text-[12px]" style={{ color: 'var(--text-secondary)' }}>:</span>
                                                        <select
                                                            aria-label={`Generation minute for ${row.name}`}
                                                            className="field w-20"
                                                            value={row.generate_minute}
                                                            onChange={(e) => patchRow(i, { generate_minute: Number(e.target.value) })}
                                                        >
                                                            {Array.from({ length: 60 }, (_, m) => (
                                                                <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                </td>
                                                <td className="py-2 pr-3">
                                                    <input
                                                        aria-label={`Daily run count for ${row.name}`}
                                                        className="field w-20"
                                                        type="number"
                                                        min={0}
                                                        step={1}
                                                        value={row.run_daily_count ?? 0}
                                                        onChange={(e) => patchRow(i, { run_daily_count: e.target.value === '' ? 0 : Number(e.target.value) })}
                                                    />
                                                </td>
                                                <td className="py-2 pr-3">
                                                    <button
                                                        className={row.auto_generate ? 'btn-primary' : 'btn-ghost'}
                                                        aria-label={`${row.auto_generate ? 'Disable' : 'Enable'} auto-generation for ${row.name}`}
                                                        onClick={() => patchRow(i, { auto_generate: !row.auto_generate })}
                                                    >
                                                        {row.auto_generate ? 'On' : 'Off'}
                                                    </button>
                                                </td>
                                                <td className="py-2 pr-3">
                                                    <input
                                                        aria-label={`Units for ${row.name}`}
                                                        className="field w-20"
                                                        type="number"
                                                        min={0}
                                                        step={0.1}
                                                        disabled={payoutOn}
                                                        style={{ opacity: payoutOn ? 0.5 : 1, cursor: payoutOn ? 'not-allowed' : 'text' }}
                                                        value={row.units ?? ''}
                                                        onChange={(e) => patchUnits(i, e.target.value)}
                                                    />
                                                </td>
                                                <td className="py-2 pr-3">
                                                    <input
                                                        aria-label={`Target payout for ${row.name}`}
                                                        className="field w-24"
                                                        type="number"
                                                        min={0}
                                                        step={0.1}
                                                        disabled={unitsOn}
                                                        style={{ opacity: unitsOn ? 0.5 : 1, cursor: unitsOn ? 'not-allowed' : 'text' }}
                                                        value={row.target_payout ?? ''}
                                                        onChange={(e) => patchPayout(i, e.target.value)}
                                                    />
                                                </td>
                                                <td className="py-2">
                                                    <div className="flex items-center gap-1">
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
