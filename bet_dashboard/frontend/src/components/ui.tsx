import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';

// ── Tooltip with Portal (Ignores parent overflow) ─────────────────────────────

interface TooltipProps {
  text: string;
  children: React.ReactNode;
  align?: 'left' | 'right' | 'center';
}

export function Tooltip({ text, align = 'center', children }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const [coords, setCoords] = useState({ top: 0, left: 0, width: 0 });

  // Update position when showing
  useEffect(() => {
    if (visible && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setCoords({
        top: rect.top + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width
      });
    }
  }, [visible]);

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex items-center"
      style={{ cursor: 'default' }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}

      {visible && createPortal(
        <div
          className="fixed z-[9999] pointer-events-none fade-in"
          style={{
            top: coords.top - 10, // 10px gap
            left: coords.left + (coords.width / 2),
            transform: `translate(-50%, -100%)`, // Position above center
          }}
        >
          <div className={`relative px-4 py-3 rounded-xl border shadow-2xl transition-all duration-200
                           w-max max-w-[340px] min-w-[200px] font-sans text-[12px] leading-relaxed`}
            style={{
              background: 'var(--bg-base)',
              backdropFilter: 'blur(16px)',
              borderColor: 'var(--border-strong)',
              color: 'var(--text-bright)',
              boxShadow: 'var(--shadow-lg)',
              textAlign: 'center',
              // Manual alignment shift within the portal relative to the center anchor
              marginLeft: align === 'right' ? '-140px' : align === 'left' ? '140px' : '0'
            }}>
            {text}

            {/* Pointer arrow */}
            <div className="absolute -bottom-1.5 w-3 h-3 rotate-45 border-b border-r"
              style={{
                left: align === 'right' ? 'calc(100% - 24px + 140px)' : align === 'left' ? 'calc(24px - 140px)' : '50%',
                marginLeft: '-6px',
                background: 'var(--bg-base)',
                borderColor: 'var(--border-strong)'
              }}
            />
          </div>
        </div>,
        document.body
      )}
    </span>
  );
}

export function TooltipIcon({ text, align = 'center' }: { text: string; align?: 'left' | 'right' | 'center' }) {
  return (
    <Tooltip text={text} align={align}>
      <span className="inline-flex items-center justify-center w-4 h-4 rounded-full
                       text-[10px] font-bold ml-1 cursor-help transition-all duration-150
                       hover:scale-110 active:scale-95"
        style={{
          border: '1px solid var(--border)',
          color: 'var(--text-secondary)',
          background: 'var(--bg-hover)'
        }}>
        ?
      </span>
    </Tooltip>
  );
}

// ── LiveDot ───────────────────────────────────────────────────────────────────

export function LiveDot({ alive, enabled }: { alive: boolean; enabled: boolean }) {
  const active = alive && enabled;
  return (
    <span className="relative inline-flex items-center justify-center w-2.5 h-2.5">
      {active && (
        <span className="absolute inset-0 rounded-full animate-ping opacity-60"
          style={{ background: 'var(--live)' }} />
      )}
      <span className="relative block w-2 h-2 rounded-full"
        style={{ background: active ? 'var(--live)' : 'var(--text-secondary)' }} />
    </span>
  );
}

// ── StatCard ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string; value: string | number; sub?: string;
  positive?: boolean; negative?: boolean; accent?: boolean;
}

export function StatCard({ label, value, sub, positive, negative, accent }: StatCardProps) {
  let color = 'var(--text-bright)';
  if (positive) color = 'var(--win)';
  if (negative) color = 'var(--loss)';
  if (accent) color = 'var(--accent)';

  return (
    <div className="card px-4 py-3 flex flex-col gap-1">
      <span className="text-[10px] font-mono tracking-widest uppercase"
        style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span className="font-display font-bold text-2xl leading-none" style={{ color }}>
        {value}
      </span>
      {sub && <span className="text-[11px]" style={{ color: 'var(--text-secondary)' }}>{sub}</span>}
    </div>
  );
}

// ── Toggle switch ─────────────────────────────────────────────────────────────

export function Toggle({ checked, onChange, label }: {
  checked: boolean; onChange: (v: boolean) => void; label?: string;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <span className="relative inline-block w-8 h-4">
        <input type="checkbox" className="sr-only" checked={checked}
          onChange={e => onChange(e.target.checked)} />
        <span className="block w-full h-full rounded-full transition-colors duration-200"
          style={{
            background: checked ? 'var(--accent)' : 'var(--bg-raised)',
            border: '1px solid var(--border-strong)'
          }} />
        <span className="absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white
                         transition-transform duration-200"
          style={{ transform: checked ? 'translateX(16px)' : 'translateX(0)' }} />
      </span>
      {label && (
        <span className="text-[11px] font-sans" style={{ color: 'var(--text-secondary)' }}>
          {label}
        </span>
      )}
    </label>
  );
}

// ── Section header ────────────────────────────────────────────────────────────

export function SectionHeader({ icon, title, sub }: { icon?: string; title: string; sub?: string }) {
  return (
    <div className="flex items-baseline gap-2 mb-4">
      {icon && <span className="text-base">{icon}</span>}
      <h2 className="font-display font-bold text-lg" style={{ color: 'var(--text-bright)' }}>
        {title}
      </h2>
      {sub && <span className="text-[11px] font-mono" style={{ color: 'var(--text-secondary)' }}>{sub}</span>}
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    Won: 'badge-won', Lost: 'badge-lost',
    Pending: 'badge-pending', Live: 'badge-live',
  };
  return <span className={`badge ${cls[status] ?? 'badge-pending'}`}>{status}</span>;
}
