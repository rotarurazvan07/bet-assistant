import { useEffect, useState } from 'react';
import { getSignificantMovements } from '../api/oddsHistory';
import { fetchMatches } from '../api/matches';
import { OddsMovementIndicator } from '../components/OddsMovementIndicator';
import type { MarketMovementDetail, Match } from '../types';
import { MARKET_COLUMNS } from '../config/marketConfig';

interface MovementMatch {
    match_id: string;
    home: string;
    away: string;
    datetime: string | null;
    markets: Record<string, MarketMovementDetail>;
    significantCount: number;
}

interface CategorizedMatch {
    match_id: string;
    home: string;
    away: string;
    datetime: string | null;
    picks: [string, MarketMovementDetail][];
}

const PAGE_SIZE = 40;

const MARKET_LABELS: Record<string, string> = {};
MARKET_COLUMNS.forEach(col => {
    const key = col.oddsKey.replace('odds_', '');
    MARKET_LABELS[key] = col.label;
});

function categorizeMatches(matches: MovementMatch[]) {
    const rising: CategorizedMatch[] = [];
    const falling: CategorizedMatch[] = [];
    for (const m of matches) {
        const sigMarkets = Object.entries(m.markets).filter(([, v]) => v.significant);
        const upPicks = sigMarkets.filter(([, v]) => v.direction === 'up');
        const downPicks = sigMarkets.filter(([, v]) => v.direction === 'down');
        if (upPicks.length > 0) {
            rising.push({ match_id: m.match_id, home: m.home, away: m.away, datetime: m.datetime, picks: upPicks });
        }
        if (downPicks.length > 0) {
            falling.push({ match_id: m.match_id, home: m.home, away: m.away, datetime: m.datetime, picks: downPicks });
        }
    }
    return { rising, falling };
}

const CATEGORY_META: Record<string, { title: string; color: string; desc: string; text: string }> = {
    rising: {
        title: '📈 Rising Odds — Market Disagrees',
        color: 'border-red-500/40 bg-red-500/10',
        desc: 'Odds lengthening (≥5% change) — less money backing this outcome, market moving against prediction.',
        text: 'text-red-100',
    },
    falling: {
        title: '📉 Falling Odds — Market Agrees',
        color: 'border-emerald-500/40 bg-emerald-500/10',
        desc: 'Odds tightening (≥5% change) — market confidence increasing, money backing the prediction.',
        text: 'text-emerald-100',
    },
};

export default function OddsAlert() {
    const [matches, setMatches] = useState<MovementMatch[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const [movements, firstPage] = await Promise.all([
                    getSignificantMovements(),
                    fetchMatches({ page: 1, page_size: PAGE_SIZE }),
                ]);
                if (cancelled) return;
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
                const merged: MovementMatch[] = [];
                for (const m of allMatches) {
                    const mv = movements[m.match_id];
                    if (!mv) continue;
                    const sigCount = Object.values(mv).filter(
                        (v): v is MarketMovementDetail => typeof v === 'object' && v !== null && v.significant
                    ).length;
                    if (sigCount === 0) continue;
                    merged.push({
                        match_id: m.match_id, home: m.home, away: m.away,
                        datetime: m.datetime ?? null, markets: mv, significantCount: sigCount,
                    });
                }
                merged.sort((a, b) => b.significantCount - a.significantCount);
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
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
                <h1 className="text-xl font-bold text-[var(--color-text)]">Odds Alert</h1>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)] leading-relaxed max-w-3xl">
                    Only matches with <strong>significant</strong> odds movements are shown (≥5% change or ≥0.10 for low odds).
                    {' '}<strong>Rising odds</strong> mean the market disagrees with the prediction.
                    {' '}<strong>Falling odds</strong> mean the market agrees — growing confidence.
                </p>
            </div>
            {loading && <div className="flex items-center justify-center py-16 text-[var(--color-text-secondary)]">Loading movements…</div>}
            {!loading && matches.length === 0 && (
                <div className="flex items-center justify-center py-16 text-[var(--color-text-secondary)]">
                    No significant odds movements detected. Movements need ≥5% change to appear here.
                </div>
            )}
            {!loading && matches.length > 0 && (['falling', 'rising'] as const).map((key) => {
                const list = cats[key];
                if (list.length === 0) return null;
                const meta = CATEGORY_META[key];
                return (
                    <section key={key}>
                        <div className={`rounded-xl border ${meta.color} p-4`}>
                            <h2 className={`text-base font-semibold ${meta.text}`}>{meta.title}</h2>
                            <p className={`text-xs mt-0.5 ${meta.text} opacity-70`}>{meta.desc}</p>
                            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                                {list.map((m) => (
                                    <div key={m.match_id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3">
                                        <div className="flex items-center justify-between">
                                            <span className="text-sm font-medium text-[var(--color-text)] truncate">{m.home} vs {m.away}</span>
                                            {m.datetime && <span className="text-[10px] text-[var(--color-text-secondary)] ml-2 whitespace-nowrap">{new Date(m.datetime).toLocaleDateString()}</span>}
                                        </div>
                                        <div className="mt-2 flex flex-wrap gap-2">
                                            {m.picks.map(([mkt, detail]) => (
                                                <span key={mkt} className="inline-flex items-center gap-1 text-xs text-[var(--color-text-secondary)]">
                                                    <OddsMovementIndicator direction={detail.direction} size="sm" />
                                                    <span>{MARKET_LABELS[mkt] ?? mkt}</span>
                                                    <span className={`text-[10px] font-medium ${detail.direction === 'down' ? 'text-emerald-500' : 'text-red-400'}`}>
                                                        {detail.change_pct > 0 ? '+' : ''}{detail.change_pct}%
                                                    </span>
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </section>
                );
            })}
        </div>
    );
}