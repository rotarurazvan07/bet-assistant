import { TooltipIcon } from './ui';
import type { BuilderConfig } from '../types';
import { ALL_MARKETS } from '../types';

interface Props {
    cfg: BuilderConfig;
    onChange: (c: BuilderConfig) => void;
}

function set<K extends keyof BuilderConfig>(
    cfg: BuilderConfig, k: K, v: BuilderConfig[K]
): BuilderConfig { return { ...cfg, [k]: v }; }

function Row({ label, tip, children }: { label: string; tip?: string; children: React.ReactNode }) {
    return (
        <div className="flex items-center gap-3 py-1.5">
            <div className="flex items-center gap-0.5 w-44 shrink-0">
                <span className="text-[11px] font-sans" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                {tip && <TooltipIcon text={tip} />}
            </div>
            <div className="flex-1">{children}</div>
        </div>
    );
}

function SliderRow({ label, tip, value, min, max, step, format, onChange }: {
    label: string; tip?: string; value: number; min: number; max: number; step: number;
    format?: (v: number) => string; onChange: (v: number) => void;
}) {
    const pct = ((value - min) / (max - min)) * 100;
    const fmt = format ?? ((v: number) => String(v));
    return (
        <div className="py-2">
            <div className="flex items-center gap-0.5 mb-1.5">
                <span className="text-[11px] font-sans" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                {tip && <TooltipIcon text={tip} />}
            </div>
            <div className="flex items-center gap-3">
                <input type="range" className="flex-1" min={min} max={max} step={step}
                    value={value}
                    style={{ background: `linear-gradient(to right, var(--accent) ${pct}%, var(--bg-raised) ${pct}%)` }}
                    onChange={e => onChange(+e.target.value)} />
                <span className="font-mono text-[11px] w-12 text-right shrink-0"
                    style={{ color: 'var(--accent)' }}>
                    {fmt(value)}
                </span>
            </div>
        </div>
    );
}

function NullableRow({ label, tip, enabled, onToggle, children }: {
    label: string; tip?: string; enabled: boolean; onToggle: (v: boolean) => void; children: React.ReactNode;
}) {
    return (
        <div className="py-2">
            <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-0.5">
                    <span className="text-[11px] font-sans" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                    {tip && <TooltipIcon text={tip} />}
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono" style={{ color: !enabled ? 'var(--accent)' : 'var(--text-secondary)' }}>Auto</span>
                    <label className="relative inline-block w-8 h-4 cursor-pointer">
                        <input type="checkbox" className="sr-only" checked={enabled} onChange={e => onToggle(e.target.checked)} />
                        <span className="block w-full h-full rounded-full transition-colors duration-200"
                            style={{ background: enabled ? 'var(--accent)' : 'var(--bg-raised)', border: '1px solid var(--border-strong)' }} />
                        <span className="absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200"
                            style={{ transform: enabled ? 'translateX(16px)' : 'translateX(0)' }} />
                    </label>
                    <span className="text-[10px] font-mono" style={{ color: enabled ? 'var(--accent)' : 'var(--text-secondary)' }}>Manual</span>
                </div>
            </div>
            {enabled && <div className="mt-2">{children}</div>}
        </div>
    );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
    return (
        <div className="mt-4 mb-1 pb-1 border-b" style={{ borderColor: 'var(--border)' }}>
            <span className="text-[10px] font-mono tracking-widest uppercase"
                style={{ color: 'var(--text-secondary)' }}>{children}</span>
        </div>
    );
}

function DualSlider({ label, left, right, value, onChange }: {
    label: string; left: string; right: string; value: number; onChange: (v: number) => void;
}) {
    const pct = value * 100;
    return (
        <div className="py-2">
            <div className="flex items-center gap-0.5 mb-1.5">
                <span className="text-[11px] font-sans" style={{ color: 'var(--text-secondary)' }}>{label}</span>
            </div>
            <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono w-14 text-right shrink-0" style={{ color: 'var(--win)' }}>{left}</span>
                <input type="range" className="flex-1" min={0} max={100} step={5}
                    value={pct}
                    style={{ background: `linear-gradient(to right, var(--win) ${pct}%, var(--accent) ${pct}%)` }}
                    onChange={e => onChange(+e.target.value / 100)} />
                <span className="text-[10px] font-mono w-14 shrink-0" style={{ color: 'var(--accent)' }}>{right}</span>
            </div>
        </div>
    );
}

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
        <div className="text-sm">
            <SectionLabel>Bet Shape</SectionLabel>
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
            <NullableRow label="Max Overflow Legs"
                tip="Extra legs allowed beyond target. Auto = +1 for 2-4 legs, +2 for 5+."
                enabled={cfg.max_legs_overflow !== null}
                onToggle={v => up('max_legs_overflow', v ? 1 : null)}>
                <input className="field w-20" type="number" min={0} max={5} step={1}
                    value={cfg.max_legs_overflow ?? 1}
                    onChange={e => up('max_legs_overflow', +e.target.value)} />
            </NullableRow>

            <SectionLabel>Quality Gate</SectionLabel>
            <SliderRow label="Consensus Floor"
                tip="Minimum source agreement %. Picks below this are discarded."
                value={cfg.consensus_floor} min={50} max={100} step={1}
                format={v => `${v}%`} onChange={v => up('consensus_floor', v)} />
            <Row label="Min Odds" tip="Minimum bookmaker odds. Filters near-certain outcomes.">
                <input className="field w-24" type="number" min={1.01} max={10} step={0.01}
                    value={cfg.min_odds} onChange={e => up('min_odds', +e.target.value)} />
            </Row>

            <SectionLabel>Markets</SectionLabel>
            <div className="grid grid-cols-4 gap-2 py-1">
                {ALL_MARKETS.map(m => {
                    const active = allSelected || (cfg.included_markets ?? []).includes(m);
                    return (
                        <button
                            key={m}
                            type="button"
                            onClick={() => toggleMarket(m)}
                            className="px-3 py-1.5 rounded-full text-[11px] font-mono uppercase transition-all duration-200"
                            style={{
                                background: active
                                    ? 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)'
                                    : 'var(--bg-raised)',
                                color: active ? '#ffffff' : 'var(--text-secondary)',
                                border: active
                                    ? '1px solid var(--accent)'
                                    : '1px solid var(--border)',
                                boxShadow: active
                                    ? '0 2px 8px rgba(var(--accent-rgb), 0.25)'
                                    : 'none',
                                transform: active ? 'scale(1.02)' : 'scale(1)',
                            }}
                        >
                            {m}
                        </button>
                    );
                })}
            </div>

            <SectionLabel>Tolerance & Stop</SectionLabel>
            <NullableRow label="Tolerance Factor"
                tip="±% band around ideal per-leg odds. Tier 1 picks sit within this band."
                enabled={cfg.tolerance_factor !== null}
                onToggle={v => up('tolerance_factor', v ? 0.25 : null)}>
                <div className="flex items-center gap-3">
                    <input type="range" className="flex-1" min={5} max={80} step={1}
                        value={Math.round((cfg.tolerance_factor ?? 0.25) * 100)}
                        onChange={e => up('tolerance_factor', +e.target.value / 100)} />
                    <span className="font-mono text-[11px] w-10 text-right" style={{ color: 'var(--accent)' }}>
                        {Math.round((cfg.tolerance_factor ?? 0.25) * 100)}%
                    </span>
                </div>
            </NullableRow>
            <NullableRow label="Stop Threshold"
                tip="Stop building when odds ≥ target × threshold AND enough legs are filled."
                enabled={cfg.stop_threshold !== null}
                onToggle={v => up('stop_threshold', v ? 0.91 : null)}>
                <div className="flex items-center gap-3">
                    <input type="range" className="flex-1" min={50} max={100} step={1}
                        value={Math.round((cfg.stop_threshold ?? 0.91) * 100)}
                        onChange={e => up('stop_threshold', +e.target.value / 100)} />
                    <span className="font-mono text-[11px] w-10 text-right" style={{ color: 'var(--accent)' }}>
                        {Math.round((cfg.stop_threshold ?? 0.91) * 100)}%
                    </span>
                </div>
            </NullableRow>
            <SliderRow label="Min Legs Fill Ratio"
                tip="Min fraction of legs before early stop is allowed."
                value={Math.round(cfg.min_legs_fill_ratio * 100)}
                min={50} max={100} step={5}
                format={v => `${v}%`}
                onChange={v => up('min_legs_fill_ratio', v / 100)} />

            <SectionLabel>Scoring</SectionLabel>
            <DualSlider label=""
                left="Balance" right="Quality"
                value={cfg.quality_vs_balance}
                onChange={v => up('quality_vs_balance', v)} />
            <DualSlider label=""
                left="Sources" right="Consensus"
                value={cfg.consensus_vs_sources}
                onChange={v => up('consensus_vs_sources', v)} />

            <SectionLabel>Advanced</SectionLabel>
            <NullableRow label="Consensus Shrinkage k"
                tip="Weight factor for source-weighted consensus adjustment. Auto = 3.0."
                enabled={cfg.consensus_shrinkage_k !== null}
                onToggle={v => up('consensus_shrinkage_k', v ? 3.0 : null)}>
                <div className="flex items-center gap-3">
                    <input type="range" className="flex-1" min={1} max={10} step={0.5}
                        value={cfg.consensus_shrinkage_k ?? 3}
                        onChange={e => up('consensus_shrinkage_k', +e.target.value)} />
                    <span className="font-mono text-[11px] w-10 text-right" style={{ color: 'var(--accent)' }}>
                        {cfg.consensus_shrinkage_k?.toFixed(1) ?? '3.0'}
                    </span>
                </div>
            </NullableRow>
            <Row label="Min Source Edge" tip="Minimum edge over implied probability (hard filter).">
                <div className="flex items-center gap-3">
                    <input type="range" className="flex-1" min={0} max={50} step={1}
                        value={cfg.min_source_edge * 100}
                        onChange={e => up('min_source_edge', +e.target.value / 100)} />
                    <span className="font-mono text-[11px] w-10 text-right" style={{ color: 'var(--accent)' }}>
                        {(cfg.min_source_edge * 100).toFixed(0)}%
                    </span>
                </div>
            </Row>
            <NullableRow label="Max Single Leg Odds"
                tip="Maximum odds for any single leg. Auto = 3.5."
                enabled={cfg.max_single_leg_odds !== null}
                onToggle={v => up('max_single_leg_odds', v ? 3.5 : null)}>
                <div className="flex items-center gap-3">
                    <input type="range" className="flex-1" min={10} max={100} step={5}
                        value={(cfg.max_single_leg_odds ?? 3.5) * 10}
                        onChange={e => up('max_single_leg_odds', +e.target.value / 10)} />
                    <span className="font-mono text-[11px] w-10 text-right" style={{ color: 'var(--accent)' }}>
                        {(cfg.max_single_leg_odds ?? 3.5).toFixed(1)}
                    </span>
                </div>
            </NullableRow>
            <Row label="Balance Decay">
                <select className="field w-32" value={cfg.balance_decay}
                    onChange={e => up('balance_decay', e.target.value as 'linear' | 'gaussian')}>
                    <option value="linear">Linear</option>
                    <option value="gaussian">Gaussian</option>
                </select>
            </Row>
            <NullableRow label="Min Pick Quality"
                tip="Minimum quality score to accept a pick. Auto = 0.20."
                enabled={cfg.min_pick_quality !== null}
                onToggle={v => up('min_pick_quality', v ? 0.2 : null)}>
                <div className="flex items-center gap-3">
                    <input type="range" className="flex-1" min={0} max={100} step={5}
                        value={Math.round((cfg.min_pick_quality ?? 0.2) * 100)}
                        onChange={e => up('min_pick_quality', +e.target.value / 100)} />
                    <span className="font-mono text-[11px] w-10 text-right" style={{ color: 'var(--accent)' }}>
                        {(cfg.min_pick_quality ?? 0.2).toFixed(2)}
                    </span>
                </div>
            </NullableRow>
        </div>
    );
}
