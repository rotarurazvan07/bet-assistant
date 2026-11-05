import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchSlips, deleteSlip, validateSlips, generateSlips } from '../api/data';
import EmptyState, { TrackEmptyIcon } from '../components/EmptyState';
import { SlipCard, SlipDetailModal } from '../components/BetComponents';
import { Toggle } from '../components/ui';
import { ProfileSelector } from '../components/ui/ProfileSelector';
import type { GlobalFilters } from '../components/Layout';
import type { SlipsPage, LiveData, BetSlip } from '../types';
import { useProfileSelection } from '../hooks/useProfileSelection';
import { Box, Button, Drawer, SwipeableDrawer, Typography, useMediaQuery } from '@mui/material';

const FILTERS_STORAGE_KEY = 'slips_filters_state';
const PAGE_SIZE = 20;

interface Props { filters: GlobalFilters; refreshKey: number; liveData?: LiveData }

type SortOption = 'net_profit_desc' | 'net_profit_asc' | 'date_desc' | 'date_asc' | 'odds_desc' | 'odds_asc' | 'stake_desc' | 'stake_asc';

export default function Slips({ filters, refreshKey, liveData: externalLiveData }: Props) {
    const navigate = useNavigate();
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
        } catch {
            // Invalid localStorage, use default
        }
        return 'net_profit_desc';
    });
    // Use external liveData from WebSocket if provided, otherwise use local state
    const [localLiveData, setLocalLiveData] = useState<LiveData>({});
    const liveData = externalLiveData ?? localLiveData;
    const [loading, setLoading] = useState(false);
    const [loadMoreError, setLoadMoreError] = useState(false);
    const loadingMoreRef = useRef(false);
    const requestIdRef = useRef(0);
    const loadMoreRef = useRef<HTMLDivElement>(null);
    const [status, setStatus] = useState('');
    const [selectedSlip, setSelectedSlip] = useState<BetSlip | null>(null);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const filtersBtnRef = useRef<HTMLButtonElement>(null);
    const isMobile = useMediaQuery('(max-width:767.95px)');


    // Persist filters to Slips-specific storage
    useEffect(() => {
        localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify({ hideSettled, liveOnly, sortBy }));
    }, [hideSettled, liveOnly, sortBy]);

    const load = useCallback(async (page = 1, append = false) => {
        void refreshKey; // deliberate signal: WS event triggers refetch (test-pinned wiring)
        if (append && loadingMoreRef.current) return;
        const requestId = append ? requestIdRef.current : requestIdRef.current + 1;
        requestIdRef.current = requestId;
        if (append) loadingMoreRef.current = true;
        else {
            setData(null);
            setLoadMoreError(false);
        }
        setLoading(true);
        try {
            // If no profiles selected, pass undefined to get all profiles
            // Otherwise pass the selected profiles array
            const params: Parameters<typeof fetchSlips>[0] = {
                date_from: filters.dateFrom || undefined,
                date_to: filters.dateTo || undefined,
                hide_settled: hideSettled,
                live_only: liveOnly,
                page,
                page_size: PAGE_SIZE,
                sort_by: sortBy,
            };
            if (selectedProfiles.length > 0) {
                params.profiles = selectedProfiles;
            }

            const d = await fetchSlips(params);
            if (requestId !== requestIdRef.current) return;
            setLoadMoreError(false);
            setData(previous => append && previous
                ? { ...d, slips: [...previous.slips, ...d.slips], profiles: previous.profiles }
                : d);
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
            setLocalLiveData(previous => append ? { ...previous, ...ld } : ld);
        } catch (error) {
            if (requestId !== requestIdRef.current) return;
            console.error('Failed to fetch slips:', error);
            setStatus('Failed to load slips. Please try again.');
            if (append) setLoadMoreError(true);
            if (!append) {
                setData({ slips: [], profiles: [], page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 1 });
            }
        } finally {
            if (requestId === requestIdRef.current) setLoading(false);
            if (append) loadingMoreRef.current = false;
        }
    }, [selectedProfiles, filters, hideSettled, liveOnly, sortBy, refreshKey]);

    useEffect(() => { load(); }, [load]);

    useEffect(() => {
        const target = loadMoreRef.current;
        if (!target || loading || loadMoreError || !data || data.page >= data.total_pages) return;

        const observer = new IntersectionObserver(entries => {
            if (entries[0]?.isIntersecting) {
                void load(data.page + 1, true);
            }
        });
        observer.observe(target);
        return () => observer.disconnect();
    }, [data, loading, loadMoreError, load]);

    function closeFilters() {
        setFiltersOpen(false);
        queueMicrotask(() => filtersBtnRef.current?.focus());
    }

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

    return (
        <>
            {/* Header */}
            <div className="flex items-center justify-between">
                {status && (
                    <span className="text-[11px] font-mono" style={{ color: 'var(--accent)' }}>{status}</span>
                )}
            </div>

            {/* Slip actions and filters */}
            <div className="flex items-center justify-between gap-3 flex-wrap mb-5">
                <div className="flex items-center gap-3 flex-wrap">
                    <button className="btn-ghost" data-tour="track-validate" onClick={handleValidate}>✓ Validate Results</button>
                    <button className="btn-success" data-tour="track-generate" onClick={handleGenerate}>✦ Generate Slips</button>
                </div>
                <Button
                    ref={filtersBtnRef}
                    variant="outlined"
                    size="small"
                    onClick={() => setFiltersOpen(open => !open)}
                    aria-expanded={filtersOpen}
                    aria-controls="slips-filters-drawer"
                >
                    Filters
                </Button>
            </div>

            {(() => {
                const drawerBody = (
                    <Box
                        id="slips-filters-drawer"
                        role="document"
                        sx={{ p: 2, width: isMobile ? '100%' : 360, maxHeight: isMobile ? '85vh' : '100%', overflow: 'auto' }}
                    >
                        <Typography id="slips-filters-title" variant="h6" sx={{ color: 'var(--text-bright)', mb: 2 }}>
                            Filters
                        </Typography>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <ProfileSelector
                                profiles={data?.profiles ?? []}
                                selectedProfiles={selectedProfiles}
                                onChange={setSelectedProfiles}
                            />
                            <select
                                className="field w-full"
                                data-tour="track-list"
                                value={sortBy}
                                onChange={e => setSortBy(e.target.value as SortOption)}
                            >
                                <option value="net_profit_desc">Sort: Net Profit (High → Low)</option>
                                <option value="net_profit_asc">Sort: Net Profit (Low → High)</option>
                                <option value="date_desc">Sort: Date (Newest)</option>
                                <option value="date_asc">Sort: Date (Oldest)</option>
                                <option value="odds_desc">Sort: Total Odds (High → Low)</option>
                                <option value="odds_asc">Sort: Total Odds (Low → High)</option>
                                <option value="stake_desc">Sort: Stake (High → Low)</option>
                                <option value="stake_asc">Sort: Stake (Low → High)</option>
                            </select>
                            <Toggle checked={hideSettled} onChange={setHideSettled} label="Hide settled" />
                            <Toggle checked={liveOnly} onChange={setLiveOnly} label="Live only" />
                        </Box>
                    </Box>
                );
                const paperSx = { background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-primary)' };
                return isMobile ? (
                    <SwipeableDrawer
                        anchor="bottom"
                        open={filtersOpen}
                        onOpen={() => setFiltersOpen(true)}
                        onClose={closeFilters}
                        aria-labelledby="slips-filters-title"
                        slotProps={{ paper: { sx: paperSx } }}
                    >
                        {drawerBody}
                    </SwipeableDrawer>
                ) : (
                    <Drawer
                        anchor="right"
                        open={filtersOpen}
                        onClose={closeFilters}
                        aria-labelledby="slips-filters-title"
                        slotProps={{ paper: { sx: paperSx } }}
                    >
                        {drawerBody}
                    </Drawer>
                );
            })()}

            {/* Empty state */}
            {/*Track empty when no slips (incl. fetch-error fallback) */}
            {!loading && data && (!data.slips || data.slips.length === 0) && (
                <EmptyState
                    icon={<TrackEmptyIcon />}
                    title="No slips yet"
                    steps={['Go to Build', 'Generate Slips', 'Validate']}
                    primary={{ label: 'Generate Slips', onClick: () => { void handleGenerate(); } }}
                    secondary={{ label: 'Go to Build', onClick: () => navigate('/builder') }}
                />
            )}

            {/* Slips Grid */}
            {data && data.slips.length > 0 && (
                <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .2s' }}>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                        {data.slips.map(slip => (
                            <SlipCard
                                key={slip.slip_id}
                                slip={slip}
                                liveData={liveData}
                                onDelete={handleDelete}
                                onCardClick={() => setSelectedSlip(slip)}
                            />
                        ))}
                    </div>
                    {data.page < data.total_pages && (
                        <div ref={loadMoreRef} className="py-6 text-center text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {loading ? 'Loading more slips…' : loadMoreError
                                ? <button className="btn-ghost" onClick={() => void load(data.page + 1, true)}>Retry loading more</button>
                                : 'Scroll to load more'}
                        </div>
                    )}
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
