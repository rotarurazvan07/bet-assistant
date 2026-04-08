import type { Match } from '../types';

// Consensus cell coloring
function consCell(pct: number, odds: number) {
  if (pct <= 0) return null;
  const bg  = pct >= 80 ? 'var(--cons-high)'
            : pct >= 60 ? 'var(--cons-mid)'
            : 'var(--cons-low)';
  const col = pct >= 80 ? 'var(--cons-high-txt)'
            : pct >= 60 ? 'var(--cons-mid-txt)'
            : 'var(--cons-low-txt)';
  return { bg, col, pct, odds };
}

function Cell({ pct, odds }: { pct: number; odds: number }) {
  const c = consCell(pct, odds);
  if (!c) return <td className="px-2 py-2 text-center">
    <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>
  </td>;
  return (
    <td className="px-1 py-1.5 text-center" style={{ minWidth: 52 }}>
      <div className="rounded px-1 py-0.5 inline-flex flex-col items-center gap-px leading-none"
           style={{ background: c.bg }}>
        <span className="font-mono font-bold text-[11px]" style={{ color: c.col }}>
          {c.pct.toFixed(0)}%
        </span>
        {c.odds > 1 && (
          <span className="font-mono text-[10px]" style={{ color: c.col, opacity: .8 }}>
            @{c.odds.toFixed(2)}
          </span>
        )}
      </div>
    </td>
  );
}

interface Props { match: Match; index: number }

export default function MatchRow({ match, index }: Props) {
  const dt = match.datetime
    ? new Date(match.datetime).toLocaleString('en-GB', {
        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
      }).replace(',', '')
    : '—';

  return (
    <tr className="border-b transition-colors duration-100 group"
        style={{ borderColor: 'var(--border)' }}
        onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>

      <td className="px-3 py-2 font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>
        {index}
      </td>
      <td className="px-3 py-2 font-mono text-[11px]" style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
        {dt}
      </td>
      <td className="px-3 py-2">
        <span className="font-sans text-[13px]" style={{ color: 'var(--text-primary)' }}>
          {match.home}
        </span>
      </td>
      <td className="px-3 py-2">
        <span className="font-sans text-[13px]" style={{ color: 'var(--text-primary)' }}>
          {match.away}
        </span>
      </td>
      <td className="px-3 py-2 text-center">
        <span className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
          {match.sources}
        </span>
      </td>

      <Cell pct={match.cons_home}     odds={match.odds_home} />
      <Cell pct={match.cons_draw}     odds={match.odds_draw} />
      <Cell pct={match.cons_away}     odds={match.odds_away} />
      <Cell pct={match.cons_over}     odds={match.odds_over} />
      <Cell pct={match.cons_under}    odds={match.odds_under} />
      <Cell pct={match.cons_btts_yes} odds={match.odds_btts_yes} />
      <Cell pct={match.cons_btts_no}  odds={match.odds_btts_no} />

    </tr>
  );
}
