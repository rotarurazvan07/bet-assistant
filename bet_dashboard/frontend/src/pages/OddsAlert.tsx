import { useEffect, useState } from 'react';
import { getAllMovements } from '../api/oddsHistory';
import { fetchMatches } from '../api/matches';
import { OddsMovementIndicator } from '../components/OddsMovementIndicator';
import type { OddsMovementSummary, OddsMovementDirection, Match } from '../types';
import { MARKET_COLUMNS } from '../config/marketConfig';

interface MovementMatch {
    match_id: string;
    home: string;
    away: string;
    datetime: string | null;
    movement: OddsMovementSummary;
    significantMovements: number;
}

const PAGE_SIZE = 40;

// Derive market labels from centralized configuration
const MARKET_LABELS: Record<string, string> = {};
MARKET_COLUMNS.forEach(col => {
  const key = col.oddsKey.replace('odds_', '');
  MARKET_LABELS[key] = col.label;
});

function countSignificantMovements(m: OddsMovementSummary): number {
    return Object.values(m).filter((d) => d === 'up' || d === 'down').length;
}

function getDirectionLabel(d: OddsMovementDirection): string {
    if (d === 'up') return 'Rising';
    if (d === 'down') return 'Falling';
    return 'Stable';
}

function categorizeMatches(matches: MovementMatch[]) {
    const hot: MovementMatch[] = [];
    const drifting: MovementMatch[] = [];
    const shortening: MovementMatch[] = [];
    for (const m of matches) {
        if (m.significantMovements === 0) continue;
        if (m.significantMovements >= 3) { hot.push(m); continue; }
        const dirs = Object.values(m.movement).filter(Boolean) as OddsMovementDirection[];
        const up = dirs.filter((d) => d === 'up').length;
        const down = dirs.filter((d) => d === 'down').length;
        if (up > down) { drifting.push(m); continue; }
        if (down > up) { shortening.push(m); continue; }
        hot.push(m); // equal up/down with movements = hot
    }
    return { hot, drifting, shortening };
}

const CATEGORY_META: Record<string, { title: string; color: string; desc: string }> = {
    hot: { title: '🔥 Hot — Multiple Market Movements', color: 'border-amber-500/40 bg-amber-500/5', desc: '3+ markets moving — heavy betting activity detected.' },
    drifting: { title: '📈 Drifting — Odds Rising', color: 'border-blue-500/40 bg-blue-500/5', desc: 'Odds lengthening — less money backing this outcome.' },
    shortening: { title: '📉 Shortening — Odds Falling', color: 'border-emerald-500/40 bg-emerald-500/5', desc: 'Odds tightening — market confidence increasing.' },
};

export default function OddsAlert() {
    const [matches, setMatches] = useState<MovementMatch[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                // Fetch movements + first page in parallel
                const [movements, firstPage] = await Promise.all([
                    getAllMovements(),
                    fetchMatches({ page: 1, page_size: PAGE_SIZE }),
                ]);
                if (cancelled) return;

                // Collect all matches across pages (parallel)
                const allMatches: Match[] = [...firstPage.matches];
                const totalPages = firstPage.total_pages;
                if (totalPages > 1) {
                    const remaining = await Promise.all(
                        Array.from({ length: totalPages - 1 }, (_, i) =>
                            fetchMatches({ page: i + 2, page_size: PAGE_SIZE })
                        )
                    );
                    for (const pg of remaining) allMatches.push(...pg.matches);
                }
                if (cancelled) return;

                // Merge with movement data
                const merged: MovementMatch[] = [];
                for (const m of allMatches) {
                    const mv = movements[m.match_id];
                    if (!mv) continue;
                    merged.push({
                        match_id: m.match_id,
                        home: m.home,
                        away: m.away,
                        datetime: m.datetime ?? null,
                        movement: mv,
                        significantMovements: countSignificantMovements(mv),
                    });
                }
                merged.sort((a, b) => b.significantMovements - a.significantMovements);
                setMatches(merged);
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const cats = categorizeMatches(matches);

    return (
        <div className="space-y-6">
            {/* Educational header */}
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
                <h1 className="text-xl font-bold text-[var(--color-text)]">Odds Alert</h1>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)] leading-relaxed max-w-3xl">
                    Track how bookmaker odds move across all upcoming matches.{' '}
                    <strong>Rising odds (drifting)</strong> mean less money is being placed on that outcome — the market sees it as less likely.{' '}
                    <strong>Falling odds (shortening)</strong> indicate growing confidence and heavier betting.{' '}
                    Matches with <strong>3+ moving markets</strong> are flagged as "hot" — they signal significant sentiment shifts worth watching.
                </p>
            </div>

            {loading && (
                <div className="flex items-center justify-center py-16 text-[var(--color-text-secondary)]">
                    Loading movements…
                </div>
            )}

            {!loading && matches.length === 0 && (
                <div className="flex items-center justify-center py-16 text-[var(--color-text-secondary)]">
                    No odds movement data available yet.
                </div>
            )}

            {!loading && matches.length > 0 && (
                <>
                    {(['hot', 'drifting', 'shortening'] as const).map((key) => {
                        const list = cats[key];
                        if (list.length === 0) return null;
                        const meta = CATEGORY_META[key];
                        return (
                            <section key={key}>
                                <div className={`rounded-xl border ${meta.color} p-4`}>
                                    <h2 className="text-base font-semibold text-[var(--color-text)]">{meta.title}</h2>
                                    <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">{meta.desc}</p>
                                    <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                                        {list.map((m) => (
                                            <div key={m.match_id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-sm font-medium text-[var(--color-text)] truncate">
                                                        {m.home} vs {m.away}
                                                    </span>
                                                    {m.datetime && (
                                                        <span className="text-[10px] text-[var(--color-text-secondary)] ml-2 whitespace-nowrap">
                                                            {new Date(m.datetime).toLocaleDateString()}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    {Object.entries(m.movement).map(([mkt, dir]) => (
                                                        dir && dir !== 'stable' && (
                                                            <span key={mkt} className="inline-flex items-center gap-1 text-xs text-[var(--color-text-secondary)]">
                                                                <OddsMovementIndicator direction={dir} size="sm" />
                                                                <span>{MARKET_LABELS[mkt] ?? mkt}</span>
                                                                <span className="text-[10px]">({getDirectionLabel(dir)})</span>
                                                            </span>
                                                        )
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </section>
                        );
                    })}
                </>
            )}
        </div>
    );
}