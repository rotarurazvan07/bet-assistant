/**
 * Number input with up/down steppers.
 *
 * Lives in `ui/` because the Services scheduler table and the Builder share it:
 * one stepper implementation, one look. Pair it with the `.field` +
 * `.num-step` classes from `index.css` (the spin buttons are hidden and drawn
 * manually so the arrows can sit inside the input's right edge).
 */

export interface NumberFieldProps {
    value: number;
    onChange: (v: number) => void;
    min?: number;
    max?: number;
    /** Step size; the decimals shown are inferred from it (1 → ints, 0.1 → 1dp). */
    step?: number;
    className?: string;
    /** Accessible name — required wherever the input has no visible <label>. */
    label?: string;
    disabled?: boolean;
}

const CHEVRON = {
    up: 'M1 4L4 1L7 4',
    down: 'M1 1L4 4L7 1',
};

export function NumberField({
    value,
    onChange,
    min,
    max,
    step = 1,
    className = 'w-20',
    label,
    disabled = false,
}: NumberFieldProps) {
    const decimals = (String(step).split('.')[1] ?? '').length;
    const clamp = (n: number) => Math.min(max ?? Infinity, Math.max(min ?? -Infinity, n));
    const bump = (dir: 1 | -1) => onChange(clamp(+(value + dir * step).toFixed(decimals)));

    const chevron = (d: string) => (
        <svg
            width="8"
            height="5"
            viewBox="0 0 8 5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            <path d={d} />
        </svg>
    );

    return (
        <div className={`relative ${className}`} style={{ opacity: disabled ? 0.5 : 1 }}>
            <input
                className="field w-full"
                type="number"
                min={min}
                max={max}
                step={step}
                aria-label={label}
                disabled={disabled}
                style={{ paddingRight: 16, cursor: disabled ? 'not-allowed' : 'text' }}
                value={value}
                onChange={(e) => {
                    const raw = e.target.value;
                    // Typed text is authoritative: '' keeps the last value out of
                    // view rather than silently writing 0 over it.
                    if (raw === '') return;
                    onChange(clamp(+raw));
                }}
            />
            {/* Steppers: tabIndex -1 keeps a single tab stop per field (keyboard
                users still get the native arrow keys on the number input). */}
            <div className="absolute right-0 inset-y-0 w-4 flex flex-col">
                <button type="button" tabIndex={-1} className="num-step" aria-hidden="true" onClick={() => bump(1)}>
                    {chevron(CHEVRON.up)}
                </button>
                <button type="button" tabIndex={-1} className="num-step" aria-hidden="true" onClick={() => bump(-1)}>
                    {chevron(CHEVRON.down)}
                </button>
            </div>
        </div>
    );
}
