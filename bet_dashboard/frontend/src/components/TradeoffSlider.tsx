import { useId } from 'react';
import type { CSSProperties } from 'react';
import { TooltipIcon } from './ui';

interface Props {
    label: string;
    tip?: string;
    leftLabel: string;
    rightLabel: string;
    leftCaption: string;
    midCaption: string;
    rightCaption: string;
    value: number;
    onChange: (v: number) => void;
    disabled?: boolean;
}

/**
 * Narrated trade-off slider (issue #41 / Workstream B Part A).
 *
 * Renders the same range-input contract as the retired DualSlider
 * (input[type=range] min 0 max 100 step 5, value*100, /100 on change) so the
 * pinned BuilderPanel test keeps working, plus dynamic captions that narrate
 * which side of the trade-off the value currently favours and a hover tooltip
 * (native title + aria-describedby) explaining the algorithmic impact.
 */
export function TradeoffSlider({
    label, tip, leftLabel, rightLabel,
    leftCaption, midCaption, rightCaption,
    value, onChange, disabled = false,
}: Props) {
    const descId = useId();
    const pct = Math.round(value * 100);
    const band: 'left' | 'mid' | 'right' = value < 1 / 3 ? 'left' : value > 2 / 3 ? 'right' : 'mid';
    const caption = band === 'left' ? leftCaption : band === 'right' ? rightCaption : midCaption;
    const tipText = tip ?? caption;

    const isLeft = pct <= 50;
    const thumbColor = isLeft ? 'var(--win)' : 'var(--accent)';
    const background = 'linear-gradient(to right, var(--win) 0%, var(--win-bg) 50%, var(--accent-glow) 50%, var(--accent) 100%)';

    return (
        <div className="py-3" style={{ borderBottom: '1px solid var(--border)' }} data-band={band}>
            <div className="flex items-center gap-1 mb-2">
                <span className="text-[11px] font-sans font-medium" style={{ color: 'var(--text-secondary)' }}>{label}</span>
                <span title={tipText} aria-describedby={descId} className="inline-flex cursor-help">
                    <TooltipIcon text={tipText} align="right" />
                </span>
                <span id={descId} className="sr-only">{tipText}</span>
            </div>
            <div className={disabled ? 'opacity-40 grayscale pointer-events-none' : ''}>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono w-16 text-right shrink-0 font-bold opacity-60"
                        style={{ color: 'var(--win)' }}>{leftLabel}</span>
                    <div className="flex-1">
                        <input
                            type="range"
                            className={`w-full relative z-10 ${disabled ? 'opacity-30 cursor-not-allowed' : ''}`}
                            min={0} max={100} step={5}
                            value={pct}
                            disabled={disabled}
                            aria-label={label}
                            aria-valuetext={caption}
                            aria-describedby={descId}
                            title={tipText}
                            style={{
                                background: disabled ? 'var(--bg-raised)' : background,
                                '--thumb-color': disabled ? 'var(--text-secondary)' : thumbColor,
                                '--thumb-glow': disabled ? 'none' : (isLeft ? 'var(--win-bg)' : 'var(--accent-glow)'),
                            } as CSSProperties}
                            onChange={e => onChange(+e.target.value / 100)}
                        />
                    </div>
                    <span className="text-[10px] font-mono w-16 shrink-0 font-bold opacity-60"
                        style={{ color: 'var(--accent)' }}>{rightLabel}</span>
                </div>
                <p className="mt-1.5 text-[10px] font-sans" style={{ color: 'var(--text-secondary)' }} data-testid="tradeoff-caption">
                    {caption}
                </p>
            </div>
        </div>
    );
}
