import { BaseCard } from './ui/BaseCard';
import { BaseBadge } from './ui/BaseBadge';
import type { ServiceInfo } from '../types';
import { LiveDot } from './ui';

interface Props {
  info: ServiceInfo;
  onToggle: () => void;
}

const ICONS: Record<string, string> = {
  puller: '⬇',
  generator: '✦',
  verifier: '⟳',
};

export default function ServiceCard({ info, onToggle }: Props) {
  const active = info.alive && info.enabled;

  // Card header with icon, name, description and status
  const header = (
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-2.5">
        <span className="w-8 h-8 rounded-lg flex items-center justify-center text-base shrink-0"
          style={{
            background: active ? 'var(--win-bg)' : 'var(--bg-raised)',
            border: `1px solid ${active ? 'var(--win-border)' : 'var(--border)'}`
          }}>
          {ICONS[info.name] ?? '●'}
        </span>
        <div>
          <p className="font-display font-bold text-[13px] uppercase tracking-wide"
            style={{ color: 'var(--text-bright)' }}>
            {info.name}
          </p>
          <p className="text-[11px] font-sans mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            {info.description}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <LiveDot alive={info.alive} enabled={info.enabled} />
        <BaseBadge status={active ? 'success' : 'default'}>
          {active ? 'Running' : 'Stopped'}
        </BaseBadge>
      </div>
    </div>
  );

  // Card footer with next run information
  const footer = info.next_run && (
    <div className="flex items-center gap-2 px-3 py-2 rounded"
      style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
      <span className="text-[10px] font-mono tracking-wide uppercase"
        style={{ color: 'var(--text-secondary)' }}>Next run</span>
      <span className="font-mono text-[11px]" style={{ color: 'var(--accent)' }}>
        {info.next_run}
      </span>
    </div>
  );

  return (
    <BaseCard
      header={header}
      footer={footer}
      status={active ? 'success' : 'default'}
    >
      <button
        className={active ? 'btn-danger' : 'btn-success'}
        style={{ justifyContent: 'center', width: '100%' }}
        onClick={onToggle}
      >
        {active ? 'Stop Service' : 'Start Service'}
      </button>
    </BaseCard>
  );
}
