import { useEffect, useRef, useState } from 'react';
import { fetchMatches } from '../api/matches';
import { addSlip } from '../api/data';
import type { CandidateLeg, ManualLegIn } from '../types';
import MatchRow from '../components/MatchRow';
import Pagination from '../components/Pagination';
import SlipBuilderPanel from '../components/SlipBuilderPanel';
import type { GlobalFilters } from '../components/Layout';
import type { MatchesPage } from '../types';

const COLS = [
    { key: 'datetime', label: 'Date' },
    { key: 'home', label: 'Home', wide: true },
    { key: 'away', label: 'Away', wide: true },
    { key: 'sources', label: 'Sources' },
    { key: 'cons_home', label: '1' },
    { key: 'cons_draw', label: 'X' },
    { key: 'cons_away', label: '2' },
    { key: 'cons_over', label: 'O2.5' },
    { key: 'cons_under', label: 'U2.5' },
    { key: 'cons_btts_yes', label: 'BTTS Y' },
    { key: 'cons_btts_no', label: 'BTTS N' },
];

const PAGE_SIZE = 40;

interface Props { filters: GlobalFilters; refreshKey: number }

export default function BettingTips({ filters, refreshKey }: Props) {
    const { minConsensus } = filters;
    const [data, setData] = useState<MatchesPage | null>(null);
    const [page, setPage] = useState(1);
    const [sortBy, setSortBy] = useState('datetime');
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
    const [loading, setLoading] = useState(false);
    const topRef = useRef<HTMLDivElement>(null);

    // Slip builder state
    const [pendingLegs, setPendingLegs] = useState<CandidateLeg[]>([]);

    // Reset to page 1 on filter / sort / external refresh change
    useEffect(() => { setPage(1); }, [filters.search, filters.dateFrom, filters.dateTo, minConsensus, sortBy, sortDir, refreshKey]);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        fetchMatches({
            page, page_size: PAGE_SIZE,
            search: filters.search || undefined,
            date_from: filters.dateFrom || undefined,
            date_to: filters.dateTo || undefined,
            sort_by: sortBy,
            sort_dir: sortDir,
            min_consensus: minConsensus,
        })
            .then(d => { if (!cancelled) { setData(d); setLoading(false); } })
            .catch(() => {
                if (!cancelled) {
                    setData({ total: 0, page: 1, page_size: PAGE_SIZE, total_pages: 1, matches: [] });
                    setLoading(false);
                }
            });
        return () => { cancelled = true; };
    }, [page, filters, minConsensus, sortBy, sortDir, refreshKey]);

    function handleSort(key: string) {
        if (key === sortBy) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setSortBy(key); setSortDir('asc'); }
    }

    function handlePageChange(p: number) {
        setPage(p);
        topRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    // Popup handlers
    function handleCellClick(leg: CandidateLeg) {
        // Validate leg before adding
        if (leg.odds == null || leg.odds <= 0) {
            console.warn('Invalid odds for leg:', leg);
            return;
        }
        if (leg.consensus == null || leg.consensus <= 0) {
            console.warn('Invalid consensus for leg:', leg);
            return;
        }
        if (!leg.result_url || leg.result_url.trim() === '') {
            console.warn('Leg missing result_url:', leg);
            alert('Cannot add leg: Missing result URL for validation');
            return;
        }
        setPendingLegs(prev => [...prev, leg]);
    }

    function handleRemoveLeg(index: number) {
        setPendingLegs(prev => prev.filter((_, i) => i !== index));
    }

    async function handleAddSlip(units: number) {
        // Check if all legs have result_url (required for validation)
        const legsMissingResultUrl = pendingLegs.filter(leg => !leg.result_url || leg.result_url.trim() === '');
        if (legsMissingResultUrl.length > 0) {
            alert('Cannot add slip: All selections must have a result URL for validation');
            return;
        }

        // Transform legs to match backend ManualLegIn schema
        const manualLegs: ManualLegIn[] = pendingLegs
            .filter(leg => leg.odds != null && leg.odds > 0 && leg.consensus != null && leg.consensus > 0)
            .map(leg => ({
                match_name: leg.match_name,
                market: leg.market,
                odds: leg.odds,
                result_url: leg.result_url,
                datetime: leg.datetime,
            }));
        try {
            await addSlip('manual', manualLegs, units);
            setPendingLegs([]);
        } catch (error: any) {
            console.error('Failed to add slip:', error.response?.data || error.message);
            alert(`Failed to add slip: ${error.response?.data?.detail || 'Unknown error'}`);
        }
    }

    return (
        <div ref={topRef} className="flex gap-4">
            {/* Main content - Table */}
            <div className="flex-1">
                {/* Header */}
                <div className="flex items-baseline justify-between mb-4">
                    <div>
                        <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                            Betting Tips
                        </h1>
                        {data && data.total != null && (
                            <p className="text-[11px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>
                                {data.total.toLocaleString()} matches · page {page} of {data.total_pages}
                            </p>
                        )}
                    </div>
                    {loading && (
                        <span className="text-[11px] font-mono animate-pulse" style={{ color: 'var(--text-muted)' }}>
                            Loading…
                        </span>
                    )}
                </div>

                {/* Empty state */}
                {!loading && data && data.total === 0 && (
                    <div className="card text-center py-16 fade-in">
                        <p className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
                            No matches available.
                        </p>
                        <p className="font-mono text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                            Click "↓ Pull Update" to fetch new data from the server.
                        </p>
                    </div>
                )}

                {/* Table */}
                {data && data.total > 0 && (
                    <>
                        <div className="card overflow-x-auto">
                            <table className="w-full" style={{ borderCollapse: 'collapse' }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                        <th className="px-3 py-2.5 text-left font-mono text-[10px] tracking-widest uppercase w-8"
                                            style={{ color: 'var(--text-muted)', background: 'var(--bg-raised)' }}>#</th>
                                        {COLS.map(col => (
                                            <th key={col.key}
                                                className="px-3 py-2.5 font-mono text-[10px] tracking-widest uppercase cursor-pointer select-none"
                                                style={{
                                                    color: sortBy === col.key ? 'var(--accent)' : 'var(--text-muted)',
                                                    background: 'var(--bg-raised)',
                                                    textAlign: col.wide ? 'left' : 'center'
                                                }}
                                                onClick={() => handleSort(col.key)}>
                                                {col.label}
                                                {sortBy === col.key && (
                                                    <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
                                                )}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.matches.map((m, i) => (
                                        <MatchRow
                                            key={m.match_id ?? i}
                                            match={m}
                                            index={(page - 1) * PAGE_SIZE + i + 1}
                                            onCellClick={handleCellClick}
                                        />
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <Pagination page={page} totalPages={data.total_pages} onPageChange={handlePageChange} />
                    </>
                )}
            </div>

            {/* Slip Builder Panel - Permanent side panel */}
            <div className="sticky top-4 h-fit" style={{ width: 300 }}>
                <SlipBuilderPanel
                    legs={pendingLegs}
                    onRemoveLeg={handleRemoveLeg}
                    onSubmit={handleAddSlip}
                />
            </div>
        </div>
    );
}
