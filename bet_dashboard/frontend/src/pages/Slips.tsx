import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchSlips, deleteSlip, validateSlips, cancelValidation, generateSlips } from '../api/data';
import EmptyState, { TrackEmptyIcon } from '../components/EmptyState';
import { SlipCard, SlipDetailModal } from '../components/BetComponents';
import SlipCalendar from '../components/SlipCalendar';
import { Toggle } from '../components/ui';
import { ProfileSelector } from '../components/ui/ProfileSelector';
import type { GlobalFilters } from '../components/Layout';
import type { SlipsPage, LiveData, BetSlip, ValidationCompletion, ValidationProgress } from '../types';
import { useProfileSelection } from '../hooks/useProfileSelection';
import { Box, Button, Drawer, SwipeableDrawer, Typography, useMediaQuery } from '@mui/material';

const FILTERS_STORAGE_KEY = 'slips_filters_state';
const PAGE_SIZE = 20;

interface Props {
    filters: GlobalFilters;
    refreshKey: number;
    liveData?: LiveData;
    validationProgress?: ValidationProgress;
    validationCompletion?: ValidationCompletion;
}

type SortOption = 'net_profit_desc' | 'net_profit_asc' | 'date_desc' | 'date_asc' | 'odds_desc' | 'odds_asc' | 'stake_desc' | 'stake_asc';

export default function Slips({
    filters,
    refreshKey,
    liveData: externalLiveData,
    validationProgress,
    validationCompletion,
}: Props) {
    const navigate = useNavigate();
    const { dateFrom, dateTo } = filters;
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
    const [statusVisible, setStatusVisible] = useState(false);
    const statusTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
    const [validationNotice, setValidationNotice] = useState('');
    const [validationNoticeVisible, setValidationNoticeVisible] = useState(false);
    const validationNoticeTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
    const [validationJobId, setValidationJobId] = useState<string | null>(null);
    const [cancelRequested, setCancelRequested] = useState(false);
    const [selectedSlip, setSelectedSlip] = useState<BetSlip | null>(null);
    const [view, setView] = useState<'grid' | 'calendar'>('grid');
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const filtersBtnRef = useRef<HTMLButtonElement>(null);
    const isMobile = useMediaQuery('(max-width:767.95px)');
    const completedJobIdRef = useRef<string | null>(null);

    const showStatus = useCallback((message: string) => {
        statusTimersRef.current.forEach(clearTimeout);
        statusTimersRef.current = [];
        setStatus(message);
        setStatusVisible(true);
        statusTimersRef.current.push(setTimeout(() => setStatusVisible(false), 4700));
        statusTimersRef.current.push(setTimeout(() => setStatus(''), 5000));
    }, []);

    const showValidationNotice = useCallback((message: string) => {
        validationNoticeTimersRef.current.forEach(clearTimeout);
        validationNoticeTimersRef.current = [];
        setValidationNotice(message);
        setValidationNoticeVisible(true);
        validationNoticeTimersRef.current.push(setTimeout(() => setValidationNoticeVisible(false), 4700));
        validationNoticeTimersRef.current.push(setTimeout(() => setValidationNotice(''), 5000));
    }, []);

    useEffect(() => () => {
        statusTimersRef.current.forEach(clearTimeout);
        validationNoticeTimersRef.current.forEach(clearTimeout);
    }, []);

    useEffect(() => {
        if (!validationCompletion || completedJobIdRef.current === validationCompletion.job_id) return;
        completedJobIdRef.current = validationCompletion.job_id;
        if (validationCompletion.failed) {
            showValidationNotice('Could not validate results. Please try again.');
        } else if (validationCompletion.cancelled) {
            showValidationNotice('Validation stopped.');
        } else if (validationCompletion.errors) {
            showValidationNotice(`Validation finished with ${validationCompletion.errors} page error(s).`);
        } else if (validationCompletion.checked === 0) {
            showValidationNotice('No active matches to check.');
        } else {
            const settled = validationCompletion.settled ?? 0;
            showValidationNotice(
                settled > 0
                    ? `Results checked · ${validationCompletion.checked} match(es) · ${settled} settled`
                    : `Results checked · ${validationCompletion.checked} match(es)`,
            );
        }
    }, [validationCompletion, showValidationNotice]);


    // Persist filters to Slips-specific storage
    useEffect(() => {
        localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify({ hideSettled, liveOnly, sortBy }));
    }, [hideSettled, liveOnly, sortBy]);

    useEffect(() => {
        if (selectedDate && (
            (filters.dateFrom && selectedDate < filters.dateFrom)
            || (filters.dateTo && selectedDate > filters.dateTo)
        )) {
            setSelectedDate(null);
        }
    }, [filters.dateFrom, filters.dateTo, selectedDate]);

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
                date_from: selectedDate || dateFrom || undefined,
                date_to: selectedDate || dateTo || undefined,
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
            showStatus('Failed to load slips. Please try again.');
            if (append) setLoadMoreError(true);
            if (!append) {
                setData({ slips: [], profiles: [], page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 1 });
            }
        } finally {
            if (requestId === requestIdRef.current) setLoading(false);
            if (append) loadingMoreRef.current = false;
        }
    }, [selectedProfiles, dateFrom, dateTo, hideSettled, liveOnly, selectedDate, sortBy, refreshKey, showStatus]);

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
        if (validationJobId) {
            setCancelRequested(true);
            try {
                await cancelValidation(validationJobId);
            } catch (error) {
                console.error('Failed to cancel slip validation:', error);
                setCancelRequested(false);
                showValidationNotice('Could not cancel validation. Please try again.');
            }
            return;
        }

        const jobId = crypto.randomUUID();
        setValidationJobId(jobId);
        setCancelRequested(false);
        try {
            const result = await validateSlips(jobId);
            completedJobIdRef.current = jobId;
            const ld: LiveData = {};
            result.live_data.forEach(item => {
                ld[item.match_name] = {
                    score: item.score,
                    minute: item.minute,
                };
            });
            setLocalLiveData(ld);
            if (result.cancelled) {
                showValidationNotice('Validation stopped.');
            } else if (result.checked === 0) {
                showValidationNotice('No active matches to check.');
            } else if (result.errors > 0) {
                showValidationNotice(`Validation finished with ${result.errors} page error(s).`);
            } else {
                showValidationNotice(
                    result.settled > 0
                        ? `Results checked · ${result.checked} match(es) · ${result.settled} settled`
                        : `Results checked · ${result.checked} match(es)`,
                );
            }
            load();
        } catch (error) {
            console.error('Failed to validate slips:', error);
            showValidationNotice('Could not validate results. Please try again.');
        } finally {
            setValidationJobId(null);
            setCancelRequested(false);
        }
    }

    async function handleGenerate() {
        showStatus('Generating…');
        const result = await generateSlips();
        showStatus(`Generated ${result.generated} slip(s)`);
        load();
    }

    async function handleDelete(id: number) {
        await deleteSlip(id);
        load();
    }

    return (
        <>
            {/* Slip actions and filters */}
            <div className="flex items-center justify-between gap-3 flex-wrap mb-5">
                <div className="w-full max-w-[520px]">
                    {(() => {
                        const progress = validationProgress?.job_id === completedJobIdRef.current
                            || (validationJobId && validationProgress?.job_id !== validationJobId)
                            ? undefined
                            : validationProgress;
                        const isValidating = validationJobId !== null || progress !== undefined;
                        const canCancel = validationJobId !== null;
                        const percent = progress && progress.total > 0
                            ? Math.min((progress.checked / progress.total) * 100, 100)
                            : 0;
                        const progressText = cancelRequested
                            ? 'Stopping…'
                            : progress?.current_match
                                ? `Checking ${progress.current_match}`
                                : isValidating
                                    ? 'Checking active matches…'
                                    : '';

                        return (
                            <div className="grid min-w-0 grid-cols-[150px_minmax(0,1fr)] items-center gap-3">
                                <button
                                    type="button"
                                    data-tour="track-validate"
                                    onClick={handleValidate}
                                    aria-label={canCancel ? 'Cancel slip validation' : 'Validate Results'}
                                    disabled={cancelRequested || (isValidating && !canCancel)}
                                    className="btn-primary w-full justify-center"
                                >
                                    {canCancel ? 'Stop checking' : isValidating ? 'Checking results…' : 'Validate results'}
                                </button>
                                {isValidating && (
                                    <div className="flex min-w-0 items-center gap-2">
                                        <span
                                            className="h-2 w-2 shrink-0 animate-pulse rounded-full"
                                            style={{ background: 'var(--accent)' }}
                                            aria-hidden="true"
                                        />
                                        <span className="min-w-0 truncate text-xs" style={{ color: 'var(--text-secondary)' }}>
                                            {progressText}
                                        </span>
                                        {progress && (
                                            <>
                                                <span className="shrink-0 text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
                                                    {progress.checked}/{progress.total}
                                                </span>
                                                <span
                                                    className="h-1 w-16 shrink-0 overflow-hidden rounded-full"
                                                    style={{ background: 'var(--bg-raised)' }}
                                                    role="progressbar"
                                                    aria-label="Validation progress"
                                                    aria-valuemin={0}
                                                    aria-valuemax={progress.total}
                                                    aria-valuenow={progress.checked}
                                                >
                                                    <span
                                                        className="block h-full transition-[width] duration-300"
                                                        style={{ width: `${percent}%`, background: 'var(--accent)' }}
                                                    />
                                                </span>
                                            </>
                                        )}
                                    </div>
                                )}
                                {!isValidating && validationNotice && (
                                    <span
                                        role="status"
                                        aria-live="polite"
                                        className="min-w-0 truncate text-xs transition-opacity duration-300"
                                        style={{
                                            color: 'var(--text-secondary)',
                                            opacity: validationNoticeVisible ? 1 : 0,
                                        }}
                                    >
                                        {validationNotice}
                                    </span>
                                )}
                            </div>
                        );
                    })()}
                    <div className="mt-2 grid grid-cols-[150px_minmax(0,1fr)] items-center gap-3">
                        <button className="btn-success w-full justify-center" data-tour="track-generate" onClick={handleGenerate}>Generate Slips</button>
                        {status && (
                            <span
                                role="status"
                                aria-live="polite"
                                className="min-w-0 truncate text-xs transition-opacity duration-300"
                                style={{ color: 'var(--text-secondary)', opacity: statusVisible ? 1 : 0 }}
                            >
                                {status}
                            </span>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <div
                        className="flex items-center rounded-xl border p-1"
                        style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
                        role="group"
                        aria-label="Slips view"
                    >
                        <button
                            type="button"
                            className="rounded-lg px-3 py-1.5 text-sm transition-all"
                            aria-label="Grid view"
                            aria-pressed={view === 'grid'}
                            onClick={() => setView('grid')}
                            style={{
                                color: view === 'grid' ? 'var(--text-bright)' : 'var(--text-secondary)',
                                background: view === 'grid' ? 'var(--bg-card)' : 'transparent',
                                boxShadow: view === 'grid' ? '0 1px 3px rgba(0,0,0,.18)' : 'none',
                            }}
                        >
                            Grid
                        </button>
                        <button
                            type="button"
                            className="rounded-lg px-3 py-1.5 text-sm transition-all"
                            aria-label="Calendar view"
                            aria-pressed={view === 'calendar'}
                            onClick={() => setView('calendar')}
                            style={{
                                color: view === 'calendar' ? 'var(--text-bright)' : 'var(--text-secondary)',
                                background: view === 'calendar' ? 'var(--bg-card)' : 'transparent',
                                boxShadow: view === 'calendar' ? '0 1px 3px rgba(0,0,0,.18)' : 'none',
                            }}
                        >
                            Calendar
                        </button>
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
                            {view === 'grid' && (
                                <>
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
                                </>
                            )}
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

            {view === 'calendar' && (
                <SlipCalendar
                    profiles={selectedProfiles}
                    dateFrom={filters.dateFrom}
                    dateTo={filters.dateTo}
                    selectedDate={selectedDate}
                    onSelectDate={day => {
                        setSelectedDate(day);
                        setView('grid');
                    }}
                />
            )}

            {view === 'grid' && (
                <>
                    {selectedDate && (
                        <div
                            className="flex items-center justify-between gap-3 flex-wrap rounded-xl border px-4 py-3 mb-4 text-sm"
                            style={{
                                color: 'var(--text-secondary)',
                                borderColor: 'var(--border)',
                                background: 'var(--bg-card)',
                            }}
                        >
                            <span>Showing slips for <strong style={{ color: 'var(--text-bright)' }}>{selectedDate}</strong></span>
                            <div className="flex items-center gap-2">
                                <button className="btn-ghost" onClick={() => setSelectedDate(null)}>Clear day filter</button>
                                <button className="btn-ghost" onClick={() => setView('calendar')}>Back to calendar</button>
                            </div>
                        </div>
                    )}

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
                </>
            )}

            {/* Slip Detail Modal */}
            {view === 'grid' && selectedSlip && (
                <SlipDetailModal
                    slip={selectedSlip}
                    liveData={liveData}
                    onClose={() => setSelectedSlip(null)}
                />
            )}
        </>
    );
}
