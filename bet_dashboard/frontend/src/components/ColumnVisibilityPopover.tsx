import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { MarketColumn } from '../config/marketConfig';

interface Props {
    columns: MarketColumn[];
    visibleKeys: Set<string>;
    onToggle: (key: string) => void;
}

export default function ColumnVisibilityPopover({ columns, visibleKeys, onToggle }: Props) {
    const [open, setOpen] = useState(false);
    const btnRef = useRef<HTMLButtonElement>(null);
    const popRef = useRef<HTMLDivElement>(null);
    const [pos, setPos] = useState({ top: 0, left: 0 });

    const openPopover = () => {
        // Measure at click time — positioning in the effect was flagged by
        // react-hooks/set-state-in-effect; the rect is stable for the click
        // that opened it (no async gap, no cascading render).
        const rect = btnRef.current?.getBoundingClientRect();
        if (rect) setPos({ top: rect.bottom + 6, left: rect.right - 220 });
        setOpen(true);
    };

    useEffect(() => {
        if (!open) return;
        function onClickOutside(e: MouseEvent) {
            if (popRef.current && !popRef.current.contains(e.target as Node) &&
                btnRef.current && !btnRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        document.addEventListener('mousedown', onClickOutside);
        return () => document.removeEventListener('mousedown', onClickOutside);
    }, [open]);

    return (
        <>
            <button
                ref={btnRef}
                className="btn-icon"
                title="Toggle columns"
                onClick={() => (open ? setOpen(false) : openPopover())}
                style={{ fontSize: 22, width: 34, height: 34 }}
            >⚙</button>
            {open && createPortal(
                <div
                    ref={popRef}
                    className="col-visibility-popover fade-in"
                    style={{ top: pos.top, left: pos.left }}
                >
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
                        Market Columns
                    </div>
                    {columns.map(col => (
                        <label key={col.market} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}>
                            <input
                                type="checkbox"
                                checked={visibleKeys.has(col.market)}
                                onChange={() => onToggle(col.market)}
                            />
                            {col.label}
                        </label>
                    ))}
                </div>,
                document.body,
            )}
        </>
    );
}