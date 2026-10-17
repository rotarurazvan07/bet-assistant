import { useCallback, useEffect, useState } from 'react';
import { fetchProfiles, fetchServices, saveServiceSettings, toggleService } from '../api/data';
import EmptyState, { ServicesEmptyIcon } from '../components/EmptyState';
import ServiceCard from '../components/ServiceCard';
import { TooltipIcon } from '../components/ui';
import type { ProfileSchedulePayload, ServicesData } from '../types';

const HOURS = Array.from({ length: 24 }, (_, i) => i);
// M3: every minute 0–59, so a legacy generate_minute like 47 always has a
// matching option instead of rendering a blank select.
const MINUTES = Array.from({ length: 60 }, (_, i) => i);

// ── Row toggle (role=switch, design-system tokens, no new deps) ──────────────

function RowToggle({ enabled, onToggle, label }: {
    enabled: boolean; onToggle: (v: boolean) => void; label: string;
}) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={enabled}
            aria-label={label}
            onClick={() => onToggle(!enabled)}
            className="relative w-10 h-5 rounded-full transition-all duration-300 cursor-pointer shrink-0"
            style={{
                background: enabled
                    ? 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)'
                    : 'var(--bg-raised)',
                border: `1px solid ${enabled ? 'var(--border-accent)' : 'var(--border)'}`,
                boxShadow: enabled ? '0 0 12px var(--accent-glow)' : 'none',
            }}
        >
            <span
                className="absolute top-[2px] w-4 h-4 rounded-full bg-white transition-all duration-300"
                style={{
                    left: enabled ? 'calc(100% - 18px)' : '2px',
                    boxShadow: 'var(--shadow-sm)',
                }}
            />
        </button>
    );
}

export default function Services() {
    const [data, setData] = useState<ServicesData | null>(null);
    const [rows, setRows] = useState<Record<string, ProfileSchedulePayload>>({});
    // M4: raw text for the numeric inputs so clearing/typing never collapses to
    // 0 or NaN mid-edit; parsed values commit to `rows` only when finite > 0.
    const [drafts, setDrafts] = useState<Record<string, string>>({});
    const [status, setStatus] = useState('');
    const [saving, setSaving] = useState(false);

    const unitText = (name: string) => drafts[`${name}:units`] ?? String(rows[name]?.units ?? '');
    const payoutText = (name: string) => drafts[`${name}:payout`] ?? String(rows[name]?.target_payout ?? '');
    const unitsInvalid = (name: string) => {
        const t = unitText(name).trim();
        if (t === '' || t === '—') return false; // untouched placeholder
        return !Number.isFinite(Number(t)) || Number(t) <= 0;
    };
    const payoutInvalid = (name: string) => {
        const t = payoutText(name).trim();
        if (t === '') return false; // empty means "no target payout"
        return !Number.isFinite(Number(t)) || Number(t) <= 0;
    };

    const load = useCallback(async () => {
        try {
            const [d, profiles] = await Promise.all([fetchServices(), fetchProfiles()]);
            setData(d);
            const names = Object.keys(profiles).sort();
            setRows(() => {
                const next: Record<string, ProfileSchedulePayload> = {};
                for (const name of names) {
                    const saved = d.profiles_schedule?.[name];
                    // Backwards compat: profiles without a saved schedule prefill from the
                    // legacy global generate_hour/generate_minute so Schedule behaviour
                    // does not regress (issue #41 / Part D).
                    next[name] = saved
                        ? {
                            enabled: saved.enabled,
                            hour: saved.hour,
                            minute: saved.minute,
                            units: saved.units,
                            target_payout: saved.target_payout,
                        }
                        : {
                            enabled: false,
                            hour: d.generate_hour,
                            minute: d.generate_minute,
                            units: 1,
                            target_payout: null,
                        };
                }
                return next;
            });
        } catch {
            // Network/API failure: keep the loading card rather than crash;
            // surface the failure in the status line (existing app pattern).
            setStatus('⚠ Failed to load services — check connection');
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    function updateRow(name: string, patch: Partial<ProfileSchedulePayload>) {
        setRows(prev => ({
            ...prev,
            [name]: { ...prev[name], ...patch },
        }));
    }

    async function handleSave() {
        // M4: validate before posting so a cleared/invalid units field shows a
        // per-row error instead of an opaque 422 from the backend.
        const bad = profileNames.filter(n => unitsInvalid(n) || payoutInvalid(n));
        if (bad.length) {
            setStatus(`⚠ Fix the highlighted ${bad.length > 1 ? 'rows' : 'row'} before saving`);
            return;
        }
        setSaving(true);
        try {
            // Commit validated drafts into rows: empty units keeps the loaded
            // value; empty payout means "no target payout" (null).
            const commit: Record<string, ProfileSchedulePayload> = {};
            for (const name of profileNames) {
                const row = rows[name];
                const unitTxt = unitText(name).trim();
                const payoutTxt = payoutText(name).trim();
                commit[name] = {
                    ...row,
                    units: unitTxt === '' || unitTxt === '—' ? row.units : Number(unitTxt),
                    target_payout: payoutTxt === '' ? null : Number(payoutTxt),
                };
            }
            setRows(commit);
            await saveServiceSettings({ profiles: commit });
            setStatus('✓ Schedules saved — per-profile generation updated');
            setDrafts({});
            await load();
        } catch {
            setStatus('⚠ Save failed — check the values and retry');
        } finally {
            setSaving(false);
        }
    }

    async function handleToggle(name: string) {
        await toggleService(name);
        await load();
    }

    if (!data) return (
        <div>
            <div className="flex items-baseline justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Automation Services
                </h1>
            </div>
            <div className="card text-center py-16">
                <p className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Loading services…
                </p>
            </div>
        </div>
    );

    const now = data.server_time ? new Date(data.server_time) : new Date();
    const profileNames = Object.keys(rows);

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

            {/* AC-06: guidance only when generator exists and is off. Loader stays loader. */}
            {data.services?.generator && !data.services.generator.enabled && (
                <div className="mb-5">
                    <EmptyState
                        icon={<ServicesEmptyIcon />}
                        title="Generate Slips is off"
                        steps={['Enable Generate Slips service', 'Set schedule', 'Save']}
                        primary={{ label: 'Enable Generate Slips', onClick: () => { void handleToggle('generator'); } }}
                        secondary={{ label: 'Save schedule', onClick: () => { void handleSave(); } }}
                    />
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

                {/* Service cards */}
                {Object.values(data.services ?? {}).map(svc => (
                    <ServiceCard
                        key={svc.name}
                        info={svc}
                        onToggle={() => handleToggle(svc.name)}
                    />
                ))}

                {/* Per-profile auto-generation scheduler */}
                <div className="card p-4 lg:col-span-3" data-testid="profile-scheduler">
                    <div className="flex items-center gap-1.5 mb-4">
                        <p className="font-mono text-[10px] tracking-widest uppercase"
                            style={{ color: 'var(--text-secondary)' }}>Per-profile Auto-Generation</p>
                        <TooltipIcon
                            text="Each enabled profile generates its own slips automatically at the scheduled time, using the units and target payout set here — independent of the Smart Builder values."
                            align="right"
                        />
                    </div>

                    {profileNames.length === 0 ? (
                        <p className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                            No saved profiles yet — create one in the Smart Builder first.
                        </p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="font-mono text-[9px] uppercase tracking-widest"
                                        style={{ color: 'var(--text-secondary)' }}>
                                        <th className="py-2 pr-3">Profile</th>
                                        <th className="py-2 pr-3">Auto</th>
                                        <th className="py-2 pr-3">Hour</th>
                                        <th className="py-2 pr-3">Minute</th>
                                        <th className="py-2 pr-3">Units</th>
                                        <th className="py-2 pr-3">Target Payout</th>
                                        <th className="py-2">Next Run</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {profileNames.map(name => {
                                        const row = rows[name];
                                        const nextRun = data.profiles_schedule?.[name]?.next_run;
                                        return (
                                            <tr key={name} style={{ borderTop: '1px solid var(--border)' }}>
                                                <td className="py-2.5 pr-3">
                                                    <span className="font-mono text-[11px] font-semibold"
                                                        style={{ color: 'var(--text-bright)' }}>{name}</span>
                                                </td>
                                                <td className="py-2.5 pr-3">
                                                    <RowToggle
                                                        enabled={row.enabled}
                                                        onToggle={v => updateRow(name, { enabled: v })}
                                                        label={`Auto-generate ${name}`}
                                                    />
                                                </td>
                                                <td className="py-2.5 pr-3">
                                                    <select
                                                        className="field w-20"
                                                        aria-label={`${name} hour`}
                                                        value={row.hour}
                                                        onChange={e => updateRow(name, { hour: Number(e.target.value) })}
                                                    >
                                                        {HOURS.map(h => (
                                                            <option key={h} value={h}>{String(h).padStart(2, '0')}</option>
                                                        ))}
                                                    </select>
                                                </td>
                                                <td className="py-2.5 pr-3">
                                                    <select
                                                        className="field w-20"
                                                        aria-label={`${name} minute`}
                                                        value={row.minute}
                                                        onChange={e => updateRow(name, { minute: Number(e.target.value) })}
                                                    >
                                                        {MINUTES.map(m => (
                                                            <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                                                        ))}
                                                    </select>
                                                </td>
                                                <td className="py-2.5 pr-3">
                                                    <input
                                                        type="number"
                                                        className="field w-20"
                                                        aria-label={`${name} units`}
                                                        min={0.5}
                                                        step={0.5}
                                                        value={unitText(name)}
                                                        onChange={e => {
                                                            const t = e.target.value;
                                                            setDrafts(prev => ({ ...prev, [`${name}:units`]: t }));
                                                            const n = Number(t);
                                                            if (t.trim() !== '' && Number.isFinite(n) && n > 0) {
                                                                updateRow(name, { units: n });
                                                            }
                                                        }}
                                                    />
                                                    {unitsInvalid(name) && (
                                                        <span className="block font-mono text-[9px] mt-1" style={{ color: 'var(--loss)' }}>
                                                            must be &gt; 0
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="py-2.5 pr-3">
                                                    <input
                                                        type="number"
                                                        className="field w-24"
                                                        aria-label={`${name} target payout`}
                                                        min={0}
                                                        step={10}
                                                        value={payoutText(name)}
                                                        placeholder="—"
                                                        onChange={e => {
                                                            const t = e.target.value;
                                                            setDrafts(prev => ({ ...prev, [`${name}:payout`]: t }));
                                                            const n = Number(t);
                                                            updateRow(name, {
                                                                target_payout:
                                                                    t.trim() === '' || !Number.isFinite(n) || n <= 0
                                                                        ? null
                                                                        : n,
                                                            });
                                                        }}
                                                    />
                                                    {payoutInvalid(name) && (
                                                        <span className="block font-mono text-[9px] mt-1" style={{ color: 'var(--loss)' }}>
                                                            must be &gt; 0
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="py-2.5">
                                                    <span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                                                        {nextRun ?? '—'}
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}

                    <div className="flex items-center gap-3 pt-4 mt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                        <button className="btn-primary" onClick={handleSave} disabled={saving}>
                            {saving ? 'Saving…' : 'Save Settings'}
                        </button>
                        {status && (
                            <span className="text-[11px] font-mono" style={{ color: 'var(--win)' }}>{status}</span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
