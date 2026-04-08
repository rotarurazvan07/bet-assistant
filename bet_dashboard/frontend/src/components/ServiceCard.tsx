import { LiveDot } from './ui';
import type { ServiceInfo } from '../types';

interface Props {
  info: ServiceInfo;
  onToggle: () => void;
}

const ICONS: Record<string, string> = {
  puller:    '⬇',
  generator: '✦',
  verifier:  '⟳',
};

export default function ServiceCard({ info, onToggle }: Props) {
  const active = info.alive && info.enabled;

  return (
    <div className="card p-4 flex flex-col gap-3 fade-in">
      {/* Top row: icon + name + status */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-lg flex items-center justify-center text-base shrink-0"
                style={{ background: active ? 'rgba(16,185,129,.12)' : 'var(--bg-raised)',
                         border: `1px solid ${active ? 'rgba(16,185,129,.3)' : 'var(--border)'}` }}>
            {ICONS[info.name] ?? '●'}
          </span>
          <div>
            <p className="font-display font-bold text-[13px] uppercase tracking-wide"
               style={{ color: 'var(--text-bright)' }}>
              {info.name}
            </p>
            <p className="text-[11px] font-sans mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {info.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <LiveDot alive={info.alive} enabled={info.enabled} />
          <span className="font-mono text-[10px]"
                style={{ color: active ? 'var(--win)' : 'var(--text-muted)' }}>
            {active ? 'Running' : 'Stopped'}
          </span>
        </div>
      </div>

      {/* Next run */}
      {info.next_run && (
        <div className="flex items-center gap-2 px-3 py-2 rounded"
             style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
          <span className="text-[10px] font-mono tracking-wide uppercase"
                style={{ color: 'var(--text-muted)' }}>Next run</span>
          <span className="font-mono text-[11px]" style={{ color: 'var(--accent)' }}>
            {info.next_run}
          </span>
        </div>
      )}

      {/* Toggle */}
      <button
        className={active ? 'btn-danger' : 'btn-success'}
        style={{ justifyContent: 'center' }}
        onClick={onToggle}
      >
        {active ? 'Stop Service' : 'Start Service'}
      </button>
    </div>
  );
}
