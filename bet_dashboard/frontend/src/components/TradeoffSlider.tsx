// TradeoffSlider (issue #41). Visual trade-off diagram replacing BuilderPanel's
// abstract DualSlider: each end states the behavioural consequence, the label
// between them names the current position, and a tooltip explains the
// algorithmic impact. Native range input keeps it keyboard operable; the
// tooltip trigger (ui.tsx Tooltip) is focus-reachable.

import { TooltipIcon } from './ui';

export interface TradeoffSliderProps {
    leftLabel: string;
    rightLabel: string;
    centerLabel?: string;
    /** Short position names shown instead of the end labels once the slider
     * leaves the midpoint (AC-41a: e.g. "Balance-focused" / "Quality-focused"). */
    leftMode?: string;
    rightMode?: string;
    label: string;
    tip: string;
    value: number; // 0..1
    onChange: (v: number) => void;
    disabled?: boolean;
}

export function TradeoffSlider({
    leftLabel, rightLabel, centerLabel = 'Balanced', leftMode, rightMode, label, tip, value, onChange, disabled = false,
}: TradeoffSliderProps) {
    // Away from the midpoint the visible label names the dominant position;
    // the descriptive end labels stay visible as the axis captions.
    const pct = value * 100;
    const active = pct > 50 ? (rightMode ?? rightLabel) : pct < 50 ? (leftMode ?? leftLabel) : centerLabel;

    return (
        <div style={{ opacity: disabled ? 0.4 : 1, pointerEvents: disabled ? 'none' : 'auto' }}>
            <div className="flex items-center gap-1 mb-2">
                <span className="text-[11px] font-sans font-medium" style={{ color: 'var(--text-secondary)' }}>
                    {label}
                </span>
                <TooltipIcon text={tip} align="right" />
            </div>
            <input
                type="range"
                min={0} max={100} step={5}
                value={pct}
                disabled={disabled}
                aria-label={label}
                aria-valuetext={active}
                onChange={(e) => onChange(Number(e.target.value) / 100)}
                className="w-full"
            />
            <div className="flex justify-between mt-1.5 gap-2">
                <span className="text-[10px] font-mono font-bold text-left"
                    style={{ color: pct < 50 ? 'var(--accent)' : 'var(--text-secondary)' }}>
                    {leftLabel}
                </span>
                <span className="text-[10px] font-mono font-bold text-center" style={{ color: 'var(--accent)' }}>
                    {active}
                </span>
                <span className="text-[10px] font-mono font-bold text-right"
                    style={{ color: pct > 50 ? 'var(--accent)' : 'var(--text-secondary)' }}>
                    {rightLabel}
                </span>
            </div>
        </div>
    );
}

// Default export alongside the named export: consumers use both styles
// (`import TradeoffSlider from` and `import { TradeoffSlider } from`). A missing
// default export breaks the default import at module scope — React renders it as
// "Element type is invalid ... got: undefined".
export default TradeoffSlider;