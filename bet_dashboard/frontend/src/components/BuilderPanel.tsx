import { useState } from 'react';
import type { CSSProperties } from 'react';
import { BaseCard } from './ui/BaseCard';
import { BaseDataRow } from './ui/BaseDataRow';
import { TooltipIcon } from './ui';
import type { BuilderConfig } from '../types';
import { ALL_MARKETS } from '../types';
import { marketLabel } from '../config/marketConfig';

interface Props {
    cfg: BuilderConfig;
    availableLeagues: string[];
    availableSources: string[];
    onChange: (c: BuilderConfig) => void;
}

function set<K extends keyof BuilderConfig>(
    cfg: BuilderConfig, k: K, v: BuilderConfig[K]
): BuilderConfig { return { ...cfg, [k]: v }; }

// ── Accordion Section ─────────────────────────────────────────────────────────

function AccordionSection({ title, icon, tip, defaultOpen = false, children }: {
    title: string; icon: string; tip?: string; defaultOpen?: boolean; children: React.ReactNode;
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
                        <div className="flex items-center gap-2">
                            <span className="text-[11px] font-sans font-semibold tracking-wide uppercase"
                                style={{ color: open ? 'var(--text-bright)' : 'var(--text-secondary)' }}>
                                {title}
                            </span>
                            {tip && <TooltipIcon text={tip} align="right" />}
                        </div>
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

type NumberFieldProps = React.ComponentProps<typeof NumberField>;

function NumberField({ value, onChange, min, max, step = 1, className = 'w-20' }: {
    value: number;
    onChange: (v: number) => void;
    min?: number;
    max?: number;
    step?: number;
    className?: string;
}) {
    const decimals = (String(step).split('.')[1] ?? '').length;
    const bump = (dir: 1 | -1) => {
        const next = +(value + dir * step).toFixed(decimals);
        onChange(Math.min(max ?? Infinity, Math.max(min ?? -Infinity, next)));
    };
    const chevron = (d: string) => (
        <svg width="8" height="5" viewBox="0 0 8 5" fill="none" stroke="currentColor"
            strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
    );

    return (
        <div className={`relative ${className}`}>
            <input className="field w-full" type="number" min={min} max={max} step={step}
                style={{ paddingRight: 16 }}
                value={value} onChange={e => onChange(+e.target.value)} />
            <div className="absolute right-0 inset-y-0 w-4 flex flex-col">
                <button type="button" tabIndex={-1} className="num-step" onClick={() => bump(1)}>
                    {chevron('M1 4L4 1L7 4')}
                </button>
                <button type="button" tabIndex={-1} className="num-step" onClick={() => bump(-1)}>
                    {chevron('M1 1L4 4L7 1')}
                </button>
            </div>
        </div>
    );
}

function Row({ label, tip, children, num }: {
    label: string;
    tip?: string;
    children?: React.ReactNode;
    num?: NumberFieldProps;        // shortcut: renders a NumberField as the value
}) {
    return (
        <BaseDataRow
            label={label}
            value={num ? <NumberField {...num} /> : children}
            actions={tip && <TooltipIcon text={tip} align="right" />}
        />
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
                } as CSSProperties}
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
                    {tip && <TooltipIcon text={tip} align="right" />}
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

function NullableRow({ label, tip, enabled, onToggle, children, num }: {
    label: string;
    tip?: string;
    enabled: boolean;
    onToggle: (v: boolean) => void;
    children?: React.ReactNode;
    num?: NumberFieldProps;        // shortcut: renders a NumberField as the body
}) {
    return (
        <div className="py-2.5" style={{ borderBottom: '1px solid var(--border)', overflow: 'visible' }}>
            <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1">
                    <span className="text-[11px] font-sans font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                    {tip && <TooltipIcon text={tip} align="right" />}
                </div>
                <ToggleSwitch enabled={enabled} onToggle={onToggle} />
            </div>
            {enabled && <div className="mt-2 fade-in">{num ? <NumberField {...num} /> : children}</div>}
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

function DualSlider({ label, tip, left, right, value, onChange, disabled = false }: {
    label: string; tip?: string; left: string; right: string; value: number; onChange: (v: number) => void;
    disabled?: boolean;
}) {
    return (
        <div className="py-3" style={{ borderBottom: '1px solid var(--border)' }}>
            {label && (
                <div className="flex items-center gap-1 mb-2">
                    <span className="text-[11px] font-sans font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                    {tip && <TooltipIcon text={tip} align="right" />}
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

const CHIP_SIZE = {
    md: { cls: 'px-3 py-2.5 rounded-xl text-[10px]', glow: '0 4px 12px var(--accent-glow)', idle: 'var(--bg-raised)' },
    sm: { cls: 'px-2 py-2 rounded-lg text-[9px] leading-tight truncate', glow: '0 2px 8px var(--accent-glow)', idle: 'var(--bg-card)' },
} as const;

function ChipGrid({ items, selected, onChange, label = (s: string) => s, cols = 3, size = 'sm' }: {
    items: string[];
    selected: string[] | null;
    onChange: (next: string[] | null) => void;
    label?: (item: string) => string;
    cols?: 2 | 3;
    size?: keyof typeof CHIP_SIZE;
}) {
    const s = CHIP_SIZE[size];

    const toggle = (item: string) => {
        const cur = selected ?? items;
        const next = cur.includes(item) ? cur.filter(x => x !== item) : [...cur, item];
        onChange(next.length === 0 || next.length === items.length ? null : next);
    };

    return (
        <div className={`grid ${cols === 2 ? 'grid-cols-2 gap-2.5' : 'grid-cols-3 gap-1.5'} py-2`}>
            {items.map(item => {
                const active = selected == null || selected.includes(item);
                return (
                    <button
                        key={item}
                        type="button"
                        title={item}
                        onClick={() => toggle(item)}
                        className={`${s.cls} font-sans font-bold uppercase transition-all duration-200 text-center`}
                        style={{
                            background: active ? 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)' : s.idle,
                            color: active ? 'var(--text-bright)' : 'var(--text-secondary)',
                            border: `1px solid ${active ? 'var(--border-accent)' : 'var(--border)'}`,
                            boxShadow: active ? s.glow : 'none',
                        }}
                    >
                        {label(item)}
                    </button>
                );
            })}
        </div>
    );
}

type NullableNumKey = {
    [K in keyof BuilderConfig]: null extends BuilderConfig[K]
        ? (NonNullable<BuilderConfig[K]> extends number ? K : never)
        : never;
}[keyof BuilderConfig];

interface NullableSliderSpec {
    key: NullableNumKey;
    label: string;
    tip: string;
    auto: number;
    start?: number;
    min: number; max: number; step: number;
    scale?: number;
    format: (uiValue: number) => string;
}

const pct = (v: number) => `${v}%`;

const STOP_SLIDERS: NullableSliderSpec[] = [
    // { key: 'tolerance_factor', label: 'Tolerance Factor', auto: 0.25, min: 5, max: 80, step: 1, format: pct, tip: '±% band around ideal per-leg odds. Tier 1 picks sit within this band.' },
    { key: 'tol_lower', label: 'Lower Tolerance', auto: 0.2, min: 1, max: 100, step: 1, format: pct, tip: 'Max % drift allowed BELOW ideal per-leg odds. Overrides the global factor.' },
    { key: 'tol_upper', label: 'Upper Tolerance', auto: 0.15, min: 1, max: 100, step: 1, format: pct, tip: 'Max % drift allowed ABOVE ideal per-leg odds. Overrides the global factor.' },
    { key: 'stop_threshold', label: 'Stop Threshold', auto: 0.90, min: 50, max: 100, step: 1, format: pct, tip: 'Stop building when odds ≥ target × threshold AND enough legs are filled.' },
    { key: 'min_legs_fill_ratio', label: 'Min Legs Fill Ratio', auto: 0.90, min: 50, max: 100, step: 5, format: pct, tip: 'Min fraction of legs before early stop is allowed.' },
    { key: 'max_legs_overflow', label: 'Max Overflow', auto: 1, start: 1, min: 0, max: 5, step: 1, scale: 1, format: v => String(v), tip: 'Extra legs allowed beyond target. Auto = +1 for 2-4 legs, +2 for 5+.' },
];

const SCORING_SLIDERS: NullableSliderSpec[] = [
    { key: 'consensus_shrinkage_k', label: 'Shrinkage k', auto: 3, scale: 1, min: 1, max: 10, step: 0.5, format: v => v.toFixed(1), tip: 'Weight factor for source-weighted consensus adjustment.' },
    { key: 'min_source_edge', label: 'Min Source Edge', auto: 0, start: 0.05, min: 0, max: 50, step: 1, format: pct, tip: 'Minimum edge over implied probability (hard filter).' },
    { key: 'odds_movement_strength_min', label: 'Movement Min Strength', auto: 0.05, min: 5, max: 20, step: 1, format: pct, tip: 'Minimum odds change % required before movement scoring kicks in.' },
];

const MOVEMENT_WEIGHT: NullableSliderSpec = {
    key: 'odds_movement_weight', label: 'Odds Movement Weight', auto: 0.05, min: 0, max: 30, step: 1, format: pct,
    tip: 'How much odds movement influences the final score. Dropping odds boost a pick, rising odds penalise it.',
};

function CfgNullableSlider({ cfg, up, spec }: { cfg: BuilderConfig; up: <K extends keyof BuilderConfig>(k: K, v: BuilderConfig[K]) => void; spec: NullableSliderSpec }) {
    const scale = spec.scale ?? 100;
    const start = spec.start ?? spec.auto;
    const raw = cfg[spec.key] as number | null;
    return <NullableRow label={spec.label} tip={`${spec.tip} Auto = ${spec.format(spec.auto * scale)}.`}
        enabled={raw !== null} onToggle={v => up(spec.key, (v ? start : null) as BuilderConfig[typeof spec.key])}>
        <InlineSlider value={+((raw ?? start) * scale).toFixed(2)} min={spec.min} max={spec.max} step={spec.step}
            format={spec.format} onChange={v => up(spec.key, (v / scale) as BuilderConfig[typeof spec.key])} />
    </NullableRow>;
}

const SubHead = ({ children }: { children: React.ReactNode }) => (
    <div className="pt-3 pb-1 text-[10px] font-mono uppercase" style={{ color: 'var(--text-secondary)' }}>{children}</div>
);

export default function BuilderPanel({ cfg, availableLeagues, availableSources, onChange }: Props) {
    const up = <K extends keyof BuilderConfig>(k: K, v: BuilderConfig[K]) => onChange(set(cfg, k, v));
    const slider = (spec: NullableSliderSpec) => <CfgNullableSlider key={spec.key} cfg={cfg} up={up} spec={spec} />;
    const marketsOn = cfg.included_markets?.length ?? ALL_MARKETS.length;
    const leaguesOn = cfg.included_leagues?.length ?? availableLeagues.length;
    const sourcesOn = availableSources.length - (cfg.excluded_sources?.length ?? 0);

    return <div className="space-y-3">
        <AccordionSection title="Bet Shape" icon="🎲" defaultOpen={true}>
            <Row label="Target Odds" tip="Desired cumulative odds for the entire slip."
                num={{ value: cfg.target_odds, min: 1.1, max: 1000, step: 0.1, onChange: v => up('target_odds', v) }} />
            <Row label="Target Legs" tip="Desired number of selections (1–100)."
                num={{ value: cfg.target_legs, min: 1, max: 100, step: 1, onChange: v => up('target_legs', v) }} />
            <Row label="Min Leg Odds" tip="Minimum bookmaker odds for a single leg. Filters near-certain outcomes."
                num={{ value: cfg.min_leg_odds, min: 1.01, max: 10, step: 0.01, onChange: v => up('min_leg_odds', v) }} />
            <Row label="Max Leg Odds" tip="Maximum bookmaker odds for a single leg."
                num={{ value: cfg.max_leg_odds, min: 1.01, max: 10, step: 0.01, onChange: v => up('max_leg_odds', v) }} />
        </AccordionSection>

        <AccordionSection title="Filters" icon="🏷️" defaultOpen={true}>
            <div className="space-y-3">
                <AccordionSection title={`Markets (${marketsOn}/${ALL_MARKETS.length})`} icon="⚽" defaultOpen={false}>
                    <ChipGrid items={ALL_MARKETS} cols={2} size="md" label={marketLabel} selected={cfg.included_markets} onChange={v => up('included_markets', v)} />
                </AccordionSection>
                {availableLeagues.length > 0 && (
                    <AccordionSection title={`Leagues (${leaguesOn}/${availableLeagues.length})`} icon="🌍">
                        <ChipGrid items={availableLeagues} selected={cfg.included_leagues} onChange={v => up('included_leagues', v)} />
                    </AccordionSection>
                )}
                {availableSources.length > 0 && (
                    <AccordionSection title={`Sources (${sourcesOn}/${availableSources.length})`} icon="📡">
                        <ChipGrid items={availableSources} selected={cfg.excluded_sources ? availableSources.filter(s => !cfg.excluded_sources!.includes(s)) : null} onChange={v => up('excluded_sources', v ? availableSources.filter(s => !v.includes(s)) : null)} />
                    </AccordionSection>
                )}
            </div>
        </AccordionSection>

        <AccordionSection title="Quality" icon="🛡️" defaultOpen={true}>
            <SliderRow label="Consensus Floor" tip="Minimum source agreement %. Picks below this are discarded." value={cfg.consensus_floor} min={50} max={100} step={1} format={pct} onChange={v => up('consensus_floor', v)} />
            <NullableRow label="Min Quality" tip="Minimum quality score to accept a pick. Auto = 0.20." enabled={cfg.min_pick_quality !== null} onToggle={v => up('min_pick_quality', v ? 0.2 : null)}><InlineSlider value={Math.round((cfg.min_pick_quality ?? 0.2) * 100)} min={0} max={100} step={5} format={v => (v / 100).toFixed(2)} onChange={v => up('min_pick_quality', v / 100)} /></NullableRow>
        </AccordionSection>

        <AccordionSection title="Strategy" icon="📐" defaultOpen={false} tip="How the builder trades breadth against strength when it picks legs.">
            <DualSlider label="Distribution Logic" tip="Balances quality vs balance in selection. Left = prioritize balance, Right = prioritize quality." left="Balance" right="Quality" value={cfg.quality_vs_balance} onChange={v => up('quality_vs_balance', v)} />
            <DualSlider label="Agreement Logic" tip="Weights source agreement vs consensus. Left = prioritize source agreement, Right = prioritize consensus among sources." left="Sources" right="Consensus" value={cfg.consensus_floor === 100 ? 0 : cfg.consensus_vs_sources} disabled={cfg.consensus_floor === 100} onChange={v => up('consensus_vs_sources', v)} />
            {slider(MOVEMENT_WEIGHT)}
        </AccordionSection>

        <AccordionSection title="Advanced" icon="⚙️" defaultOpen={false}>
            <SubHead>Leg tolerance & stopping</SubHead>
            {STOP_SLIDERS.map(slider)}
            <SubHead>Scoring</SubHead>
            {SCORING_SLIDERS.map(slider)}
            <Row label="Balance Decay" tip="Decay method for balancing selections. Linear = steady decay, Gaussian = bell-shaped decay with stronger central weighting."><select className="field w-28" value={cfg.balance_decay} onChange={e => up('balance_decay', e.target.value as 'linear' | 'gaussian')}><option value="linear">Linear</option><option value="gaussian">Gaussian</option></select></Row>
        </AccordionSection>
    </div>;
}
