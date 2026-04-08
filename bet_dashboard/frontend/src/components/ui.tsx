import { useState, useRef, useEffect } from 'react';

// ── Tooltip ──────────────────────────────────────────────────────────────────

export function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);
  return (
    <span className="relative inline-flex items-center" style={{ cursor: 'default' }}
          onMouseEnter={() => setVisible(true)}
          onMouseLeave={() => setVisible(false)}>
      {children}
      {visible && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50
                         text-[11px] font-sans leading-snug rounded px-2 py-1.5
                         pointer-events-none whitespace-pre-wrap max-w-[240px]"
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-strong)',
                color: 'var(--text-secondary)',
                boxShadow: '0 4px 12px rgba(0,0,0,.6)',
              }}>
          {text}
        </span>
      )}
    </span>
  );
}

export function TooltipIcon({ text }: { text: string }) {
  return (
    <Tooltip text={text}>
      <span className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full
                       text-[9px] font-bold ml-1 cursor-help"
            style={{ border: '1px solid var(--text-muted)', color: 'var(--text-muted)' }}>
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
              style={{ background: 'var(--win)' }} />
      )}
      <span className="relative block w-2 h-2 rounded-full"
            style={{ background: active ? 'var(--win)' : 'var(--text-muted)' }} />
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
  if (accent)   color = 'var(--accent)';

  return (
    <div className="card px-4 py-3 flex flex-col gap-1">
      <span className="text-[10px] font-mono tracking-widest uppercase"
            style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span className="font-display font-bold text-2xl leading-none" style={{ color }}>
        {value}
      </span>
      {sub && <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>{sub}</span>}
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
              style={{ background: checked ? 'var(--accent)' : 'var(--bg-raised)',
                       border: '1px solid var(--border-strong)' }} />
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
      {sub && <span className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>{sub}</span>}
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
