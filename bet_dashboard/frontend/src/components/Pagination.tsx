interface Props {
  page: number; totalPages: number;
  onPageChange: (p: number) => void;
}

export default function Pagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null;

  const pages: (number | '…')[] = [];
  const add = (n: number) => {
    if (n >= 1 && n <= totalPages && !pages.includes(n)) pages.push(n);
  };
  add(1);
  for (let i = page - 2; i <= page + 2; i++) add(i);
  add(totalPages);
  pages.sort((a, b) => (a as number) - (b as number));

  const withGaps: (number | '…')[] = [];
  for (let i = 0; i < pages.length; i++) {
    if (i > 0 && (pages[i] as number) - (pages[i - 1] as number) > 1) withGaps.push('…');
    withGaps.push(pages[i]);
  }

  return (
    <div className="flex items-center justify-center gap-1 py-6">
      <button className="btn-ghost px-3 py-1.5 text-xs"
              disabled={page === 1} onClick={() => onPageChange(page - 1)}>‹</button>

      {withGaps.map((p, i) =>
        p === '…'
          ? <span key={`g${i}`} className="w-7 text-center text-xs"
                  style={{ color: 'var(--text-muted)' }}>…</span>
          : <button
              key={p}
              onClick={() => onPageChange(p as number)}
              className="w-7 h-7 rounded text-[11px] font-mono transition-colors duration-100"
              style={p === page
                ? { background: 'var(--accent)', color: '#fff' }
                : { color: 'var(--text-secondary)' }
              }
            >{p}</button>
      )}

      <button className="btn-ghost px-3 py-1.5 text-xs"
              disabled={page === totalPages} onClick={() => onPageChange(page + 1)}>›</button>
    </div>
  );
}
