import { useEffect, useState, useCallback, useMemo } from 'react';
import { fetchSlips, deleteSlip, validateSlips, generateSlips } from '../api/data';
import { SlipCard, SlipDetailModal } from '../components/BetComponents';
import { StatCard, Toggle } from '../components/ui';
import { ProfileSelector } from '../components/ui/ProfileSelector';
import type { GlobalFilters } from '../components/Layout';
import type { SlipsPage, LiveData, BetSlip } from '../types';
import { useProfileSelection } from '../hooks/useProfileSelection';

const FILTERS_STORAGE_KEY = 'slips_filters_state';

interface Props { filters: GlobalFilters; refreshKey: number; liveData?: LiveData }

type SortOption = 'net_profit_desc' | 'net_profit_asc' | 'date_desc' | 'date_asc' | 'odds_desc' | 'odds_asc' | 'stake_desc' | 'stake_asc';

export default function Slips({ filters, refreshKey, liveData: externalLiveData }: Props) {
    const [data, setData] = useState<SlipsPage | null>(null);

    // Initialize selectedProfiles from shared storage (persists across Slips/Analytics)
    const { selectedProfiles, setSelectedProfiles } = useProfileSelection({
        page: 'slips',
        allProfiles: data?.profiles ?? []
    });

    // Initialize filters from Slips-specific storage (persists only for Slips page)
    const [hideSettled, setHideSettled] = useState(() => {
        const saved = localStorage.getItem(FILTERS_STORAGE_KEY);
        return saved ? JSON.parse(saved).hideSettled : false;
    });
    const [liveOnly, setLiveOnly] = useState(() => {
        const saved = localStorage.getItem(FILTERS_STORAGE_KEY);
        return saved ? JSON.parse(saved).liveOnly : false;
    });
    const [sortBy, setSortBy] = useState<SortOption>(() => {
        try {
            const saved = localStorage.getItem(FILTERS_STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (parsed.sortBy && typeof parsed.sortBy === 'string') {
                    return parsed.sortBy as SortOption;
                }
            }
        } catch (e) {
            // Invalid localStorage, use default
        }
        return 'net_profit_desc';
    });
    // Use external liveData from WebSocket if provided, otherwise use local state
    const [localLiveData, setLocalLiveData] = useState<LiveData>({});
    const liveData = externalLiveData ?? localLiveData;
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState('');
    const [selectedSlip, setSelectedSlip] = useState<BetSlip | null>(null);


    // Persist filters to Slips-specific storage
    useEffect(() => {
        localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify({ hideSettled, liveOnly, sortBy }));
    }, [hideSettled, liveOnly, sortBy]);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            // If no profiles selected, pass undefined to get all profiles
            // Otherwise pass the selected profiles array
            const params: any = {
                date_from: filters.dateFrom || undefined,
                date_to: filters.dateTo || undefined,
                hide_settled: hideSettled,
                live_only: liveOnly,
            };
            if (selectedProfiles.length > 0) {
                params.profiles = selectedProfiles;
            }

            const d = await fetchSlips(params);
            setData(d);
            // Update local live data from the slip legs that have live status
            const ld: LiveData = {};
            d.slips.forEach(slip => {
                slip.legs.forEach(leg => {
                    if (leg.status === 'Live' && leg.match_name) {
                        // Initialize with empty live data, will be updated by validation
                        ld[leg.match_name] = { score: '', minute: '' };
                    }
                });
            });
            setLocalLiveData(ld);
        } catch {
            // Set empty state on error
            setData({ slips: [], stats: { total_settled: 0, total_won_count: 0, win_rate: 0, implied_win_rate: 0, edge: 0, total_units_bet: 0, gross_return: 0, net_profit: 0, roi_percentage: 0, avg_odds: 0, avg_units: 0, units_std: 0, pending_count: 0, sharpe_ratio: null , kelly_suggested_units: 0, edge_trend: "neutral", recent_edge_value: 0.0, biggest_win_units: null, biggest_loss_units: null, best_day_pnl: null, worst_day_pnl: null, current_streak: 0, longest_win_streak: 0, longest_loss_streak: 0, profit_factor: 0 }, profiles: [] });
        } finally { setLoading(false); }
    }, [selectedProfiles, filters, hideSettled, liveOnly, refreshKey]);

    useEffect(() => { load(); }, [load]);

    // Update live data when WebSocket pushes new live_data
    useEffect(() => {
        if (externalLiveData && Object.keys(externalLiveData).length > 0) {
            setLocalLiveData(externalLiveData);
        }
    }, [externalLiveData]);

    async function handleValidate() {
        setStatus('Validating…');
        const result = await validateSlips();
        const ld: LiveData = {};
        result.live_data.forEach(item => {
            ld[item.match_name] = {
                score: item.score,
                minute: item.minute,
            };
        });
        setLocalLiveData(ld);
        setStatus(`✓ Checked ${result.checked} · Settled ${result.settled} · Live ${result.live}`);
        load();
    }

    async function handleGenerate() {
        setStatus('Generating…');
        const result = await generateSlips();
        setStatus(`✓ Generated ${result.generated} slip(s)`);
        load();
    }

    async function handleDelete(id: number) {
        await deleteSlip(id);
        load();
    }

    const stats = data?.stats;

    // Sort slips based on sortBy state
    const sortedSlips = useMemo(() => {
        if (!data?.slips) return [];

        const slipsToSort = [...data.slips];

        return slipsToSort.sort((a, b) => {
            switch (sortBy) {
                case 'net_profit_desc': {
                    const calcA = a.slip_status === 'Pending' ? -Infinity : (a.slip_status === 'Won' ? (a.total_odds * a.units) - a.units : a.slip_status === 'Lost' ? -a.units : 0);
                    const calcB = b.slip_status === 'Pending' ? -Infinity : (b.slip_status === 'Won' ? (b.total_odds * b.units) - b.units : b.slip_status === 'Lost' ? -b.units : 0);
                    return calcB - calcA;
                }
                case 'net_profit_asc': {
                    const calcA = a.slip_status === 'Pending' ? Infinity : (a.slip_status === 'Won' ? (a.total_odds * a.units) - a.units : a.slip_status === 'Lost' ? -a.units : 0);
                    const calcB = b.slip_status === 'Pending' ? Infinity : (b.slip_status === 'Won' ? (b.total_odds * b.units) - b.units : b.slip_status === 'Lost' ? -b.units : 0);
                    return calcA - calcB;
                }
                case 'date_desc':
                    return new Date(b.date_generated).getTime() - new Date(a.date_generated).getTime();
                case 'date_asc':
                    return new Date(a.date_generated).getTime() - new Date(b.date_generated).getTime();
                case 'odds_desc':
                    return b.total_odds - a.total_odds;
                case 'odds_asc':
                    return a.total_odds - b.total_odds;
                case 'stake_desc':
                    return b.units - a.units;
                case 'stake_asc':
                    return a.units - b.units;
                default:
                    return 0;
            }
        });
    }, [data?.slips, sortBy]);

    return (
        <>
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Slips
                </h1>
                {status && (
                    <span className="text-[11px] font-mono" style={{ color: 'var(--accent)' }}>{status}</span>
                )}
            </div>

            {/* Profile Selection */}
            <div className="mb-5">
                <ProfileSelector
                    profiles={data?.profiles ?? []}
                    selectedProfiles={selectedProfiles}
                    onChange={setSelectedProfiles}
                    profileData={data}
                />
            </div>

            {/* Controls: Sorting, Validation, Generation, Filters */}
            <div className="flex items-center gap-3 flex-wrap mb-5">
                {/* Sort by dropdown */}
                <select className="field w-56"
                    value={sortBy}
                    onChange={e => setSortBy(e.target.value as SortOption)}>
                    <option value="net_profit_desc">Sort: Net Profit (High → Low)</option>
                    <option value="net_profit_asc">Sort: Net Profit (Low → High)</option>
                    <option value="date_desc">Sort: Date (Newest)</option>
                    <option value="date_asc">Sort: Date (Oldest)</option>
                    <option value="odds_desc">Sort: Total Odds (High → Low)</option>
                    <option value="odds_asc">Sort: Total Odds (Low → High)</option>
                    <option value="stake_desc">Sort: Stake (High → Low)</option>
                    <option value="stake_asc">Sort: Stake (Low → High)</option>
                </select>

                <button className="btn-ghost" onClick={handleValidate}>✓ Validate Results</button>
                <button className="btn-success" onClick={handleGenerate}>✦ Generate Slips</button>

                <div className="flex items-center gap-3 ml-auto">
                    <Toggle checked={hideSettled} onChange={setHideSettled} label="Hide settled" />
                    <Toggle checked={liveOnly} onChange={setLiveOnly} label="Live only" />
                </div>
            </div>

            {/* Empty state */}
            {!loading && data && (!data.slips || data.slips.length === 0) && (
                <div className="card text-center py-16 fade-in">
                    <p className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                        No slips available.
                    </p>
                    <p className="font-mono text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                        Click "✦ Generate Slips" to create betting slips from your profiles.
                    </p>
                </div>
            )}

            {/* Stats row */}
            {stats && (
                <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
                    <StatCard label="Total Bet" value={`${stats.total_units_bet} U`} />
                    <StatCard label="Gross Return" value={`${stats.gross_return} U`} />
                    <StatCard label="Net Profit" value={`${stats.net_profit > 0 ? '+' : ''}${stats.net_profit} U`}
                        positive={stats.net_profit > 0} negative={stats.net_profit < 0} />
                    <StatCard label="Win Rate" value={`${stats.win_rate}%`} positive={stats.win_rate > 50} />
                    <StatCard label="ROI" value={`${stats.roi_percentage}%`}
                        positive={stats.roi_percentage > 0} negative={stats.roi_percentage < 0} />
                    <StatCard label="Settled" value={stats.total_settled} />
                </div>
            )}

            {/* Slips Grid */}
            {data && sortedSlips && sortedSlips.length > 0 && (
                <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .2s' }}>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                        {sortedSlips.map(slip => (
                            <SlipCard
                                key={slip.slip_id}
                                slip={slip}
                                liveData={liveData}
                                onDelete={handleDelete}
                                onCardClick={() => setSelectedSlip(slip)}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Slip Detail Modal */}
            {selectedSlip && (
                <SlipDetailModal
                    slip={selectedSlip}
                    liveData={liveData}
                    onClose={() => setSelectedSlip(null)}
                />
            )}
        </>
    );
}
