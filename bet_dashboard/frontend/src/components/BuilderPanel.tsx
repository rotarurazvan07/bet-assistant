import { useState } from 'react';
import { BaseCard } from './ui/BaseCard';
import { BaseDataRow } from './ui/BaseDataRow';
import type { BuilderConfig } from '../types';
import { ALL_MARKETS } from '../types';

interface Props {
    cfg: BuilderConfig;
    onChange: (c: BuilderConfig) => void;
}

function set<K extends keyof BuilderConfig>(
    cfg: BuilderConfig, k: K, v: BuilderConfig[K]
): BuilderConfig { return { ...cfg, [k]: v }; }

// ── Accordion Section ─────────────────────────────────────────────────────────

function AccordionSection({ title, icon, defaultOpen = false, children }: {
    title: string; icon: string; defaultOpen?: boolean; children: React.ReactNode;
}) {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="space-y-3">
            <BaseCard status={open ? 'info' : 'default'}>
                <button
                    type="button"
                    onClick={() => setOpen(!open)}
                    className="w-full flex items-center justify-between px-4 py-3 transition-colors duration-150"
                    style={{
                        background: open ? 'var(--accent-glow)' : 'transparent',
                        borderBottom: open ? '1px solid var(--border)' : 'none'
                    }}
                >
                    <div className="flex items-center gap-2">
                        <span className="text-xs opacity-80">{icon}</span>
                        <span className="text-[11px] font-sans font-semibold tracking-wide uppercase"
                            style={{ color: open ? 'var(--text-bright)' : 'var(--text-secondary)' }}>
                            {title}
                        </span>
                    </div>
                    <svg
                        className="w-3 h-3 transition-transform duration-300"
                        style={{
                            color: 'var(--text-secondary)',
                            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
                        }}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                </button>
                <div
                    className="transition-all duration-300 ease-in-out"
                    style={{
                        maxHeight: open ? '1500px' : '0px',
                        opacity: open ? 1 : 0,
                        overflow: open ? 'visible' : 'hidden',
                        pointerEvents: open ? 'auto' : 'none'
                    }}
                >
                    <div className="px-4 pb-4 pt-1"
                        style={{ background: 'var(--bg-raised)' }}>
                        {children}
                    </div>
                </div>
            </BaseCard>
        </div>
    );
}

// ── Row Components ────────────────────────────────────────────────────────────

function Row({ label, tip, children }: { label: string; tip?: string; children: React.ReactNode }) {
    return (
        <BaseDataRow label={label} value={children} actions={tip && <span className="text-xs opacity-80 ml-1">ⓘ</span>} />
    );
}

function SliderWithTicks({ min, max, step, value, onChange, showCenter = false, dual = false, disabled = false }: {
    min: number; max: number; step: number; value: number; onChange: (v: number) => void;
    showCenter?: boolean; dual?: boolean; disabled?: boolean;
}) {
    const pct = ((value - min) / (max - min)) * 100;

    // Choose colors based on which half we are in
    const isLeft = pct <= 50;
    const thumbColor = dual ? (isLeft ? 'var(--win)' : 'var(--accent)') : 'var(--accent)';
    const thumbGlow = dual ? (isLeft ? 'var(--win-bg)' : 'var(--accent-glow)') : 'var(--accent-glow)';


    // In dual mode, the inactive part of the gradient should be softer
    const background = dual
        ? `linear-gradient(to right, var(--win) 0%, var(--win-bg) 50%, var(--accent-glow) 50%, var(--accent) 100%)`
        : `linear-gradient(to right, var(--accent) ${pct}%, var(--bg-raised) ${pct}%)`;

    return (
        <div className="relative pt-1 pb-2">
            {/* Ticks - Subtle markers */}
            <div className="absolute top-1 left-0 right-0 flex justify-between px-[6px] pointer-events-none opacity-10">
                <div className="w-px h-1 bg-white" />
                <div className="w-px h-1 bg-white" />
                <div className="w-px h-1 bg-white" />
                <div className="w-px h-1 bg-white" />
                <div className="w-px h-1 bg-white" />
            </div>

            {showCenter && (
                <div className="absolute top-0 left-1/2 -translate-x-1/2 h-3 w-[2px] bg-accent opacity-30 pointer-events-none" />
            )}

            <input type="range" className={`w-full relative z-10 ${disabled ? 'opacity-30 cursor-not-allowed' : ''}`}
                min={min} max={max} step={step}
                value={value}
                disabled={disabled}
                style={{
                    background: disabled ? 'var(--bg-raised)' : background,
                    '--thumb-color': disabled ? 'var(--text-secondary)' : thumbColor,
                    '--thumb-glow': disabled ? 'none' : thumbGlow
                } as any}
                onChange={e => onChange(+e.target.value)} />
        </div>
    );
}

function SliderRow({ label, tip, value, min, max, step, format, onChange, showCenter = false }: {
    label: string; tip?: string; value: number; min: number; max: number; step: number;
    format?: (v: number) => string; onChange: (v: number) => void; showCenter?: boolean;
}) {
    const fmt = format ?? ((v: number) => String(v));
    return (
        <div className="py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1">
                    <span className="text-[11px] font-sans font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                    {tip && <span className="text-xs opacity-80 ml-1">ⓘ</span>}
                </div>
                <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded"
                    style={{ color: 'var(--accent)', background: 'var(--accent-glow)' }}>
                    {fmt(value)}
                </span>
            </div>
            <SliderWithTicks min={min} max={max} step={step} value={value} onChange={onChange} showCenter={showCenter} />
        </div>
    );
}

// ── Toggle Switch ─────────────────────────────────────────────────────────────

function ToggleSwitch({ enabled, onToggle }: {
    enabled: boolean; onToggle: (v: boolean) => void;
}) {
    return (
        <div className="flex items-center gap-2">
            <span className="text-[9px] font-mono uppercase font-semibold"
                style={{ color: !enabled ? 'var(--accent)' : 'var(--text-secondary)' }}>Auto</span>
            <button
                type="button"
                onClick={() => onToggle(!enabled)}
                className="relative w-10 h-5 rounded-full transition-all duration-300 cursor-pointer"
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
            <span className="text-[9px] font-mono uppercase font-semibold"
                style={{ color: enabled ? 'var(--accent)' : 'var(--text-secondary)' }}>Set</span>
        </div>
    );
}

function NullableRow({ label, tip, enabled, onToggle, children }: {
    label: string; tip?: string; enabled: boolean; onToggle: (v: boolean) => void; children: React.ReactNode;
}) {
    return (
        <div className="py-2.5" style={{ borderBottom: '1px solid var(--border)', overflow: 'visible' }}>
            <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1">
                    <span className="text-[11px] font-sans font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                    {tip && <span className="text-xs opacity-80 ml-1">ⓘ</span>}
                </div>
                <ToggleSwitch enabled={enabled} onToggle={onToggle} />
            </div>
            {enabled && <div className="mt-2 fade-in">{children}</div>}
        </div>
    );
}

// ── Inline Slider with Value ──────────────────────────────────────────────────

function InlineSlider({ value, min, max, step, format, onChange, showCenter = false }: {
    value: number; min: number; max: number; step: number;
    format?: (v: number) => string; onChange: (v: number) => void; showCenter?: boolean;
}) {
    const fmt = format ?? ((v: number) => String(v));
    return (
        <div className="flex items-center gap-4 w-full">
            <div className="flex-1">
                <SliderWithTicks min={min} max={max} step={step} value={value} onChange={onChange} showCenter={showCenter} />
            </div>
            <span className="font-mono text-[10px] w-12 text-right shrink-0 font-bold"
                style={{ color: 'var(--accent)' }}>
                {fmt(value)}
            </span>
        </div>
    );
}

// ── Dual Slider ───────────────────────────────────────────────────────────────

function DualSlider({ label, left, right, value, onChange, disabled = false }: {
    label: string; left: string; right: string; value: number; onChange: (v: number) => void;
    disabled?: boolean;
}) {
    return (
        <div className="py-3" style={{ borderBottom: '1px solid var(--border)' }}>
            {label && (
                <div className="flex items-center gap-1 mb-2">
                    <span className="text-[11px] font-sans font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                </div>
            )}
            <div className={`flex items-center gap-2 ${disabled ? 'opacity-40 grayscale pointer-events-none' : ''}`}>
                <span className="text-[10px] font-mono w-16 text-right shrink-0 font-bold opacity-60" style={{ color: 'var(--win)' }}>{left}</span>
                <div className="flex-1">
                    <SliderWithTicks min={0} max={100} step={5} value={value * 100} onChange={v => onChange(v / 100)} showCenter={true} dual={true} disabled={disabled} />
                </div>
                <span className="text-[10px] font-mono w-16 shrink-0 font-bold opacity-60" style={{ color: 'var(--accent)' }}>{right}</span>
            </div>
        </div>
    );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

export default function BuilderPanel({ cfg, onChange }: Props) {
    const up = <K extends keyof BuilderConfig>(k: K, v: BuilderConfig[K]) => onChange(set(cfg, k, v));

    const allSelected = !cfg.included_markets ||
        ALL_MARKETS.every(m => cfg.included_markets!.includes(m));

    function toggleMarket(m: string) {
        const cur = cfg.included_markets ?? ALL_MARKETS;
        const next = cur.includes(m) ? cur.filter(x => x !== m) : [...cur, m];
        onChange(set(cfg, 'included_markets', next.length === ALL_MARKETS.length ? null : next));
    }

    return (
        <div className="space-y-3">
            {/* ── Bet Shape ──────────────────────────────────────────── */}
            <AccordionSection title="Bet Shape" icon="🎲" defaultOpen={true}>
                <Row label="Target Odds"
                    tip="Desired cumulative odds for the entire slip.">
                    <input className="field w-20" type="number" min={1.1} max={1000} step={0.1}
                        value={cfg.target_odds}
                        onChange={e => up('target_odds', +e.target.value)} />
                </Row>
                <Row label="Target Legs" tip="Desired number of selections (1–100).">
                    <input className="field w-20" type="number" min={1} max={100} step={1}
                        value={cfg.target_legs}
                        onChange={e => up('target_legs', +e.target.value)} />
                </Row>
                <NullableRow label="Max Overflow"
                    tip="Extra legs allowed beyond target. Auto = +1 for 2-4 legs, +2 for 5+."
                    enabled={cfg.max_legs_overflow !== null}
                    onToggle={v => up('max_legs_overflow', v ? 1 : null)}>
                    <input className="field w-20" type="number" min={0} max={5} step={1}
                        value={cfg.max_legs_overflow ?? 1}
                        onChange={e => up('max_legs_overflow', +e.target.value)} />
                </NullableRow>
            </AccordionSection>

            {/* ── Quality Gate ──────────────────────────────────────── */}
            <AccordionSection title="Quality Gate" icon="🛡️" defaultOpen={true}>
                <SliderRow label="Consensus Floor"
                    tip="Minimum source agreement %. Picks below this are discarded."
                    value={cfg.consensus_floor} min={50} max={100} step={1}
                    format={v => `${v}%`} onChange={v => up('consensus_floor', v)} />
                <Row label="Min Odds" tip="Minimum bookmaker odds. Filters near-certain outcomes.">
                    <input className="field w-20" type="number" min={1.01} max={10} step={0.01}
                        value={cfg.min_odds} onChange={e => up('min_odds', +e.target.value)} />
                </Row>
            </AccordionSection>

            {/* ── Markets ──────────────────────────────────────────── */}
            <AccordionSection title="Markets" icon="🏷️" defaultOpen={true}>
                <div className="grid grid-cols-2 gap-2.5 py-2">
                    {ALL_MARKETS.map(m => {
                        const active = allSelected || (cfg.included_markets ?? []).includes(m);
                        return (
                            <button
                                key={m}
                                type="button"
                                onClick={() => toggleMarket(m)}
                                className="px-3 py-2.5 rounded-xl text-[10px] font-sans font-bold uppercase
                                           transition-all duration-200 text-center"
                                style={{
                                    background: active
                                        ? 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)'
                                        : 'var(--bg-raised)',
                                    color: active ? 'var(--text-bright)' : 'var(--text-secondary)',
                                    border: active
                                        ? '1px solid var(--border-accent)'
                                        : '1px solid var(--border)',
                                    boxShadow: active
                                        ? '0 4px 12px var(--accent-glow)'
                                        : 'none',
                                }}
                            >
                                {m}
                            </button>
                        );
                    })}
                </div>
            </AccordionSection>

            {/* ── Tolerance & Stop ──────────────────────────────────── */}
            <AccordionSection title="Tolerance & Stop" icon="⚡" defaultOpen={false}>
                <NullableRow label="Tolerance Factor"
                    tip="±% band around ideal per-leg odds. Tier 1 picks sit within this band."
                    enabled={cfg.tolerance_factor !== null}
                    onToggle={v => up('tolerance_factor', v ? 0.25 : null)}>
                    <InlineSlider
                        value={Math.round((cfg.tolerance_factor ?? 0.25) * 100)}
                        min={5} max={80} step={1}
                        format={v => `${v}%`}
                        onChange={v => up('tolerance_factor', v / 100)} />
                </NullableRow>
                <NullableRow label="Stop Threshold"
                    tip="Stop building when odds ≥ target × threshold AND enough legs are filled."
                    enabled={cfg.stop_threshold !== null}
                    onToggle={v => up('stop_threshold', v ? 0.91 : null)}>
                    <InlineSlider
                        value={Math.round((cfg.stop_threshold ?? 0.91) * 100)}
                        min={50} max={100} step={1}
                        format={v => `${v}%`}
                        onChange={v => up('stop_threshold', v / 100)} />
                </NullableRow>
                <SliderRow label="Min Legs Fill Ratio"
                    tip="Min fraction of legs before early stop is allowed."
                    value={Math.round(cfg.min_legs_fill_ratio * 100)}
                    min={50} max={100} step={5}
                    format={v => `${v}%`}
                    onChange={v => up('min_legs_fill_ratio', v / 100)} />
            </AccordionSection>

            {/* ── Scoring ──────────────────────────────────────────── */}
            <AccordionSection title="Scoring" icon="📐" defaultOpen={false}>
                <DualSlider
                    label="Distribution Logic"
                    left="Balance" right="Quality"
                    value={cfg.quality_vs_balance}
                    onChange={v => up('quality_vs_balance', v)} />
                <DualSlider
                    label="Agreement Logic"
                    left="Sources" right="Consensus"
                    value={cfg.consensus_floor === 100 ? 0 : cfg.consensus_vs_sources}
                    disabled={cfg.consensus_floor === 100}
                    onChange={v => up('consensus_vs_sources', v)} />
            </AccordionSection>

            {/* ── Advanced ──────────────────────────────────────────── */}
            <AccordionSection title="Advanced" icon="⚙️" defaultOpen={false}>
                <NullableRow label="Shrinkage k"
                    tip="Weight factor for source-weighted consensus adjustment. Auto = 3.0."
                    enabled={cfg.consensus_shrinkage_k !== null}
                    onToggle={v => up('consensus_shrinkage_k', v ? 3.0 : null)}>
                    <InlineSlider
                        value={cfg.consensus_shrinkage_k ?? 3}
                        min={1} max={10} step={0.5}
                        format={v => v.toFixed(1)}
                        onChange={v => up('consensus_shrinkage_k', v)} />
                </NullableRow>
                <NullableRow label="Min Source Edge"
                    tip="Minimum edge over implied probability (hard filter). Auto = 0.0."
                    enabled={cfg.min_source_edge !== null}
                    onToggle={v => up('min_source_edge', v ? 0.05 : null)}>
                    <InlineSlider
                        value={Math.round((cfg.min_source_edge ?? 0.05) * 100)}
                        min={0} max={50} step={1}
                        format={v => `${v}%`}
                        onChange={v => up('min_source_edge', v / 100)} />
                </NullableRow>
                <NullableRow label="Max Leg Odds"
                    tip="Maximum odds for any single leg. Auto = 3.5."
                    enabled={cfg.max_single_leg_odds !== null}
                    onToggle={v => up('max_single_leg_odds', v ? 3.5 : null)}>
                    <InlineSlider
                        value={(cfg.max_single_leg_odds ?? 3.5) * 10}
                        min={10} max={100} step={5}
                        format={v => (v / 10).toFixed(1)}
                        onChange={v => up('max_single_leg_odds', v / 10)} />
                </NullableRow>
                <Row label="Balance Decay">
                    <select className="field w-28" value={cfg.balance_decay}
                        onChange={e => up('balance_decay', e.target.value as 'linear' | 'gaussian')}>
                        <option value="linear">Linear</option>
                        <option value="gaussian">Gaussian</option>
                    </select>
                </Row>
                <NullableRow label="Min Quality"
                    tip="Minimum quality score to accept a pick. Auto = 0.20."
                    enabled={cfg.min_pick_quality !== null}
                    onToggle={v => up('min_pick_quality', v ? 0.2 : null)}>
                    <InlineSlider
                        value={Math.round((cfg.min_pick_quality ?? 0.2) * 100)}
                        min={0} max={100} step={5}
                        format={v => (v / 100).toFixed(2)}
                        onChange={v => up('min_pick_quality', v / 100)} />
                </NullableRow>
                <NullableRow label="Lower Tolerance"
                    tip="Max % drift allowed BELOW ideal per-leg odds. Overrides global factor."
                    enabled={cfg.tol_lower !== null}
                    onToggle={v => up('tol_lower', v ? 0.2 : null)}>
                    <InlineSlider
                        value={Math.round((cfg.tol_lower ?? 0.2) * 100)}
                        min={1} max={100} step={1}
                        format={v => `${v}%`}
                        onChange={v => up('tol_lower', v / 100)} />
                </NullableRow>
                <NullableRow label="Upper Tolerance"
                    tip="Max % drift allowed ABOVE ideal per-leg odds. Overrides global factor."
                    enabled={cfg.tol_upper !== null}
                    onToggle={v => up('tol_upper', v ? 0.15 : null)}>
                    <InlineSlider
                        value={Math.round((cfg.tol_upper ?? 0.15) * 100)}
                        min={1} max={100} step={1}
                        format={v => `${v}%`}
                        onChange={v => up('tol_upper', v / 100)} />
                </NullableRow>
            </AccordionSection>
        </div>
    );
}
