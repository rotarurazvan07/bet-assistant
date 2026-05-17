import { BaseCard } from './ui/BaseCard';
import { BaseBadge } from './ui/BaseBadge';
import type { ServiceInfo } from '../types';
import { LiveDot, TooltipIcon } from './ui';

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
        <div className="flex items-center gap-1.5">
          <p className="font-display font-bold text-[13px] uppercase tracking-wide"
            style={{ color: 'var(--text-bright)' }}>
            {info.name}
          </p>
          {getServiceTooltip(info.name)}
        </div>
        <p className="text-[11px] font-sans mt-0.5" style={{ color: 'var(--text-secondary)' }}>
          {info.description}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <LiveDot alive={info.alive} enabled={info.enabled} />
        <BaseBadge status={active ? 'success' : 'default'}>
          {active ? 'Running' : 'Stopped'}
        </BaseBadge>
      </div>
    </div>
  );

  // Card footer with last generated information (generator only)
  const footer = info.name === 'generator' ? (
    <div className="flex items-center justify-between px-3 py-2 rounded w-full"
      style={{ background: 'var(--bg-raised)', border: '1px solid var(--border)' }}>
      <span className="text-[10px] font-mono tracking-wide uppercase"
        style={{ color: 'var(--text-secondary)' }}>Last Generated</span>
      <span className="font-mono text-[11px]" style={{ color: 'var(--accent)' }}>
        {info.last_time_generated ? new Date(info.last_time_generated).toLocaleString('en-GB', {
          day: '2-digit',
          month: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        }) : 'Never'}
      </span>
    </div>
  ) : null;

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

function getServiceTooltip(name: string): React.ReactNode {
  const tooltips: Record<string, string> = {
    puller: 'Runs in the background, polling GitHub every 5 minutes. It checks the remote database ETag; if the release has changed, it automatically downloads and hot-swaps the active SQLite database.',
    generator: 'Polls every 5 minutes to check if the current time matches your scheduled hour. If the hour matches and the service hasn\'t run yet today, it automatically generates and saves betting slips for all active profiles.',
    verifier: 'Runs in the background, polling live match score APIs every 60 seconds. It checks the progress and status of active match legs, updates scores in real-time, and settles slips as Won or Lost once all legs complete.'
  };

  const text = tooltips[name] || 'Service description not available.';
  return <TooltipIcon text={text} align="right" />;
}
