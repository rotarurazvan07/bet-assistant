import {useCallback,  useEffect, useRef, useState } from 'react';
import { fetchMatches } from '../api/matches';
import { getAllMovements } from '../api/oddsHistory';
import { addSlip, fetchSlips, fetchSourcesConfig } from '../api/data';
import type { CandidateLeg, ManualLegIn, BetLeg, OddsMovementSummary, BetSlip} from '../types';
import MatchRow from '../components/MatchRow';
import Pagination from '../components/Pagination';
import FloatingSlipBuilder from '../components/FloatingSlipBuilder';
import type { GlobalFilters } from '../components/Layout';
import type { MatchesPage } from '../types';
import { TooltipIcon } from '../components/ui';
import { getTableColumns, MARKET_COLUMNS, ALL_MARKETS } from '../config/marketConfig';
import { Checkbox, FormControlLabel, Button, Box, Typography, Divider, Drawer, SwipeableDrawer, useMediaQuery } from '@mui/material';

// Derive columns from centralized config (fixed columns only - market columns filtered dynamically)
const ALL_COLS = getTableColumns();

const PAGE_SIZE = 40;
const STORAGE_KEY = 'betting_tips_state';

interface Props { filters: GlobalFilters; refreshKey: number }

export default function BettingTips({ filters, refreshKey }: Props) {
    const [data, setData] = useState<MatchesPage | null>(null);
    const [loading, setLoading] = useState(false);
    const topRef = useRef<HTMLDivElement>(null);

    // Slip builder state - persist pending legs
    const [pendingLegs, setPendingLegs] = useState<CandidateLeg[]>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            return parsed.pendingLegs || [];
        }
        return [];
    });

    // Fetch slips from backend to highlight cells already in slips
    const [slipSelections, setSlipSelections] = useState<Set<string>>(new Set());
    const [movements, setMovements] = useState<Record<string, OddsMovementSummary>>({});

    useEffect(() => {
        let cancelled = false;
        const loadSlips = async () => {
            try {
                const slipsData = await fetchSlips({ hide_settled: true });
                const selections = new Set<string>();
                slipsData.slips.forEach((slip: BetSlip) => {
                    // Only consider pending or live slips
                    if (slip.slip_status === 'Pending' || slip.slip_status === 'Live') {
                        slip.legs.forEach((leg: BetLeg) => {
                            if (leg.result_url && leg.market) {
                                selections.add(`${leg.result_url}|${leg.market}`);
                            }
                        });
                    }
                });
                if (!cancelled) {
                    setSlipSelections(selections);
                }
            } catch (error) {
                console.error('Failed to fetch slips:', error);
            }
        };
        loadSlips();
        return () => { cancelled = true; };
    }, [refreshKey]); // Refetch when refreshKey changes

    // Local filter state with localStorage persistence
    const [search, setSearch] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).search : '';
    });
    const [minConsensus, setMinConsensus] = useState<number | null>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).minConsensus : null;
    });
    const [minOdds, setMinOdds] = useState<number | null>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).minOdds ?? null : null;
    });
    const [onlySignificantMovement, setOnlySignificantMovement] = useState<boolean>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).onlySignificantMovement ?? false : false;
    });
    const [page, setPage] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).page : 1;
    });
    const [sortBy, setSortBy] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).sortBy : 'datetime';
    });
    const [sortDir, setSortDir] = useState<'asc' | 'desc'>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).sortDir : 'asc';
    });

    // Column visibility state (persisted)
    const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
        try {
            const raw = localStorage.getItem('col-visibility');
            return raw ? new Set(JSON.parse(raw)) : new Set(ALL_MARKETS);
        } catch { return new Set(ALL_MARKETS); }
    });
    useEffect(() => {
        localStorage.setItem('col-visibility', JSON.stringify([...visibleColumns]));
    }, [visibleColumns]);
    const toggleColumn = (key: string) => {
        setVisibleColumns(prev => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key); else next.add(key);
            return next;
        });
    };

    // Slip minimized state (persisted)
    const [isSlipMinimized, setIsSlipMinimized] = useState<boolean>(() => {
        try { return localStorage.getItem('slip-minimized') === 'true'; }
        catch { return false; }
    });
    useEffect(() => {
        localStorage.setItem('slip-minimized', String(isSlipMinimized));
    }, [isSlipMinimized]);

    // Sources filter state
    const [allSources, setAllSources] = useState<string[]>([]);
    const [excludedSources, setExcludedSources] = useState<Set<string>>(() => {
        try {
            const saved = localStorage.getItem('betting_tips_excluded_sources');
            return saved ? new Set(JSON.parse(saved)) : new Set<string>();
        } catch { return new Set<string>(); }
    });
    const [sourcesLoading, setSourcesLoading] = useState(true);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const filtersBtnRef = useRef<HTMLButtonElement>(null);
    // AC-07 (#39): last market cell that interacted with the slip builder.
    const lastSlipTriggerRef = useRef<HTMLElement | null>(null);
    const isMobile = useMediaQuery('(max-width:767.95px)');

    // Fetch sources config on mount
    useEffect(() => {
        let cancelled = false;
        fetchSourcesConfig()
            .then(config => {
                if (!cancelled) {
                    setAllSources(config.sources);
                    setSourcesLoading(false);
                }
            })
            .catch(() => {
                if (!cancelled) setSourcesLoading(false);
            });
        return () => { cancelled = true; };
    }, []);

    // Persist excluded sources
    useEffect(() => {
        localStorage.setItem('betting_tips_excluded_sources', JSON.stringify([...excludedSources]));
    }, [excludedSources]);

    // Persist state to localStorage
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
            search,
            minConsensus,
            minOdds,
            onlySignificantMovement,
            page,
            sortBy,
            sortDir,
            pendingLegs
        }));
    }, [search, minConsensus, minOdds, onlySignificantMovement, page, sortBy, sortDir, pendingLegs]);

    // Reset to page 1 when any filter changes — render-time adjustment
    // (React-documented "adjust state when a prop changes" pattern;
    // replaces setState-in-effect flagged by react-hooks/set-state-in-effect).
    const resetKey = `${filters.dateFrom}|${filters.dateTo}|${refreshKey}|${search}|${minConsensus}|${minOdds}|${onlySignificantMovement}|${Array.from(excludedSources).join(',')}`;
    const [prevResetKey, setPrevResetKey] = useState(resetKey);
    if (resetKey !== prevResetKey) {
        setPrevResetKey(resetKey);
        setPage(1);
    }

    // Fetch odds movements
    useEffect(() => {
        let cancelled = false;
        getAllMovements()
            .then(d => { if (!cancelled) setMovements(d); })
            .catch(() => {});
        return () => { cancelled = true; };
    }, [refreshKey]);

    const load = useCallback(async () => {
        void refreshKey; // deliberate signal: WS matches_updated triggers refetch (test-pinned wiring)
        // Always send excluded_sources array (empty = include all, non-empty = exclude those)
        const excludedSourcesArray = Array.from(excludedSources);
        fetchMatches({
            page, page_size: PAGE_SIZE,
            search: search || undefined,
            date_from: filters.dateFrom || undefined,
            date_to: filters.dateTo || undefined,
            sort_by: sortBy,
            sort_dir: sortDir,
            min_consensus: minConsensus,
            min_odds: minOdds,
            only_significant_movement: onlySignificantMovement || undefined,
            excluded_sources: excludedSourcesArray,
        })
            .then(d => { setData(d); setLoading(false); })
            .catch(() => {
                setData({ total: 0, page: 1, page_size: PAGE_SIZE, total_pages: 1, matches: [] });
                setLoading(false);
            });
    }, [page, filters.dateFrom, filters.dateTo, search, minConsensus, minOdds, onlySignificantMovement, sortBy, sortDir, refreshKey, excludedSources]);

    useEffect(() => { load(); }, [load]);

    function handleSort(key: string) {
        if (key === sortBy) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setSortBy(key); setSortDir('asc'); }
    }

    function resetDiscoverFilters() {
        setSearch('');
        setMinConsensus(null);
        setMinOdds(null);
        setOnlySignificantMovement(false);
        setSortBy('datetime');
        setSortDir('asc');
        setExcludedSources(new Set());
        setVisibleColumns(new Set(ALL_MARKETS));
    }

    function closeFilters() {
        setFiltersOpen(false);
        queueMicrotask(() => filtersBtnRef.current?.focus());
    }

    // #39 AC-07: mirror closeFilters — on minimize, restore focus to the
    // triggering market cell; fall back to the re-mounted minimized pill
    // when the cell is gone (pagination/unmount).
    function handleToggleSlip() {
        const minimizing = !isSlipMinimized;
        // AC-07 (#39): expanding from the pill records it so Esc can return there
        // when no market cell was used.
        if (!minimizing && !lastSlipTriggerRef.current) {
            lastSlipTriggerRef.current = document.querySelector<HTMLElement>('.floating-slip-minimized');
        }
        setIsSlipMinimized(minimizing);
        if (!minimizing) return;
        queueMicrotask(() => {
            const el = lastSlipTriggerRef.current;
            if (el && el.isConnected) el.focus();
            else document.querySelector<HTMLElement>('.floating-slip-minimized')?.focus();
        });
    }

    function handlePageChange(p: number) {
        setPage(p);
        topRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    // Popup handlers
    function handleCellClick(leg: CandidateLeg, element?: HTMLElement) {
        // AC-07 (#39): remember the trigger so minimize can restore focus.
        if (element) lastSlipTriggerRef.current = element;
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
        setPendingLegs(prev => {
            // Check if this leg (by result_url + market) already exists
            const exists = prev.some(l => l.result_url === leg.result_url && l.market === leg.market);
            if (exists) {
                // Remove it (toggle off)
                return prev.filter(l => !(l.result_url === leg.result_url && l.market === leg.market));
            } else {
                // Add it
                return [...prev, leg];
            }
        });
    }

    function handleRemoveLeg(index: number) {
        setPendingLegs(prev => prev.filter((_, i) => i !== index));
    }

    // Refetch slips after successfully adding a slip
    async function handleAddSlip(units: number) {
        // Check if all legs have result_url (required for validation)
        const legsMissingResultUrl = pendingLegs.filter(leg => !leg.result_url || leg.result_url.trim() === '');
        if (legsMissingResultUrl.length > 0) {
            alert('Cannot add slip: All selections must have a result URL for validation');
            return;
        }

        // Transform legs to match backend ManualLegIn schema
        const manualLegs: ManualLegIn[] = pendingLegs
            .filter(leg =>
                leg.odds != null && leg.odds > 0 &&
                leg.consensus != null && leg.consensus > 0 &&
                leg.sources != null && leg.sources >= 0 &&
                leg.datetime != null &&
                leg.match_name &&
                leg.market &&
                leg.market_type &&
                leg.result_url
            )
            .map(leg => ({
                match_name: leg.match_name,
                market: leg.market,
                market_type: leg.market_type,
                odds: leg.odds,
                result_url: leg.result_url!,
                datetime: leg.datetime!,
                consensus: leg.consensus,
                sources: leg.sources,
                league: leg.league ?? null,
                predictions: leg.predictions || [],
            }));
        try {
            await addSlip('manual', manualLegs, units);
            setPendingLegs([]);
            // Refresh slip selections after adding
            try {
                const slipsData = await fetchSlips({ hide_settled: true });
                const selections = new Set<string>();
                slipsData.slips.forEach((slip: BetSlip) => {
                    if (slip.slip_status === 'Pending' || slip.slip_status === 'Live') {
                        slip.legs.forEach((leg: BetLeg) => {
                            if (leg.result_url && leg.market) {
                                selections.add(`${leg.result_url}|${leg.market}`);
                            }
                        });
                    }
                });
                setSlipSelections(selections);
            } catch (err) {
                console.error('Failed to refresh slips after add:', err);
            }
        } catch (error: unknown) {
            const e = error as { response?: { data?: { detail?: string } }; message?: string };
            console.error('Failed to add slip:', e.response?.data || e.message);
            alert(`Failed to add slip: ${e.response?.data?.detail || 'Unknown error'}`);
        }
    }

    return (
        <>
        <div ref={topRef} style={{
            height: 'calc(100vh - 178px)',
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
        }}>
                    {/* Header with filters */}
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '0px'
                    }}>
                        <div style={{
                            display: 'flex',
                            flexDirection: 'column'
                        }}>
                            <h2 style={{
                                margin: 0,
                                color: 'var(--text-bright)',
                                fontSize: '1.75rem',
                                fontWeight: 'bold'
                            }}>Betting Tips</h2>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                                {data && data.total != null && (
                                    <span style={{
                                        fontSize: '14px',
                                        color: 'var(--text-secondary)',
                                    }}>
                                        {data.total.toLocaleString()} matches · page {page} of {data.total_pages}
                                    </span>
                                )}
                            </div>
                        </div>

                        <Button
                            ref={filtersBtnRef}
                            variant="outlined"
                            size="small"
                            onClick={() => setFiltersOpen(open => !open)}
                            aria-expanded={filtersOpen}
                            aria-controls="discover-filters-drawer"
                        >
                            Filters
                        </Button>
                    </div>

                    {(() => {
                        const drawerBody = (
                            <Box
                                id="discover-filters-drawer"
                                role="document"
                                sx={{ p: 2, width: isMobile ? '100%' : 360, maxHeight: isMobile ? '85vh' : '100%', overflow: 'auto' }}
                            >
                                <Typography id="discover-filters-title" variant="h6" sx={{ color: 'var(--text-bright)', mb: 2 }}>
                                    Filters
                                </Typography>
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                    <input
                                        type="text"
                                        placeholder="Filter by team..."
                                        className="field w-full"
                                        value={search}
                                        onChange={e => setSearch(e.target.value)}
                                    />
                                    <div>
                                        <label style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 500 }}>
                                            Min Consensus
                                            <TooltipIcon text="Minimum agreement percentage required from sources. Only matches with consensus at or above this threshold will be shown." align="right" />
                                        </label>
                                        <div className="flex items-center gap-2 mt-1">
                                            <input
                                                type="range"
                                                min={0}
                                                max={100}
                                                step={5}
                                                value={minConsensus ?? 0}
                                                onChange={e => setMinConsensus(e.target.value === '0' ? null : Number(e.target.value))}
                                                className="w-32"
                                                aria-label="Min Consensus"
                                            />
                                            <span className="text-sm font-mono font-bold" style={{ color: 'var(--text-bright)' }}>
                                                {minConsensus !== null ? `${minConsensus}%` : 'Any'}
                                            </span>
                                        </div>
                                    </div>
                                    <div>
                                        <label style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 500 }}>
                                            Min Odds
                                            <TooltipIcon text="Minimum odds required. A market cell must have both the min consensus AND min odds to count. If any cell passes both filters, the row is shown." align="right" />
                                        </label>
                                        <div className="flex items-center gap-2 mt-1">
                                            <input
                                                type="range"
                                                min={1.0}
                                                max={5.0}
                                                step={0.1}
                                                value={minOdds ?? 1.0}
                                                onChange={e => setMinOdds(Number(e.target.value) <= 1.0 ? null : Number(e.target.value))}
                                                className="w-32"
                                                aria-label="Min Odds"
                                            />
                                            <span className="text-sm font-mono font-bold" style={{ color: 'var(--text-bright)' }}>
                                                {minOdds !== null ? minOdds.toFixed(1) : 'Any'}
                                            </span>
                                        </div>
                                    </div>
                                </Box>
                                <Button
                                    type="button"
                                    onClick={() => setAdvancedOpen(v => !v)}
                                    aria-expanded={advancedOpen}
                                    sx={{ mt: 2, color: 'var(--text-secondary)', textTransform: 'none' }}
                                >
                                    {advancedOpen ? '▾' : '▸'} Advanced
                                </Button>
                                {advancedOpen && (
                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
                                        <div className="flex items-center gap-2">
                                            <label style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 500 }}>
                                                Sig. Movement
                                                <TooltipIcon text="Show only matches with significant odds movement (≥5% change). Chained with min consensus and min odds filters." align="right" />
                                            </label>
                                            <button
                                                type="button"
                                                onClick={() => setOnlySignificantMovement(v => !v)}
                                                aria-pressed={onlySignificantMovement}
                                                className="relative w-10 h-5 rounded-full transition-all duration-300 cursor-pointer"
                                                style={{
                                                    background: onlySignificantMovement
                                                        ? 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark, var(--accent)) 100%)'
                                                        : 'var(--bg-raised)',
                                                    border: `1px solid ${onlySignificantMovement ? 'var(--accent)' : 'var(--border)'}`,
                                                }}
                                            >
                                                <span
                                                    className="absolute top-[2px] w-4 h-4 rounded-full bg-white transition-all duration-300"
                                                    style={{ left: onlySignificantMovement ? 'calc(100% - 18px)' : '2px' }}
                                                />
                                            </button>
                                        </div>
                                        <div>
                                            <Typography variant="subtitle2" sx={{ color: 'var(--text-bright)', mb: 1 }}>Sources</Typography>
                                            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                                <Button size="small" variant="outlined" onClick={() => setExcludedSources(new Set())} disabled={excludedSources.size === 0 || sourcesLoading}>Select All</Button>
                                                <Button size="small" variant="outlined" onClick={() => setExcludedSources(new Set(allSources))} disabled={excludedSources.size === allSources.length || sourcesLoading}>Deselect All</Button>
                                            </Box>
                                            {sourcesLoading ? (
                                                <Typography variant="body2" sx={{ color: 'var(--text-secondary)' }}>Loading sources...</Typography>
                                            ) : (
                                                <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                                                    {allSources.map(source => (
                                                        <FormControlLabel
                                                            key={source}
                                                            control={
                                                                <Checkbox
                                                                    checked={!excludedSources.has(source)}
                                                                    onChange={(event) => {
                                                                        const checked = event.target.checked;
                                                                        setExcludedSources(prev => {
                                                                            const next = new Set(prev);
                                                                            if (checked) next.delete(source);
                                                                            else next.add(source);
                                                                            return next;
                                                                        });
                                                                    }}
                                                                    color="primary"
                                                                    disabled={sourcesLoading}
                                                                />
                                                            }
                                                            label={
                                                                <Typography variant="body2" sx={{
                                                                    color: excludedSources.has(source) ? 'var(--text-secondary)' : 'var(--text-primary)',
                                                                    textDecoration: excludedSources.has(source) ? 'line-through' : 'none',
                                                                }}>
                                                                    {source}
                                                                </Typography>
                                                            }
                                                        />
                                                    ))}
                                                </Box>
                                            )}
                                        </div>
                                        <div>
                                            <Typography variant="subtitle2" sx={{ color: 'var(--text-bright)', mb: 1 }}>Columns</Typography>
                                            <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                                <Button size="small" variant="outlined" onClick={() => setVisibleColumns(new Set(MARKET_COLUMNS.map(c => c.market)))} disabled={visibleColumns.size === MARKET_COLUMNS.length}>Select All</Button>
                                                <Button size="small" variant="outlined" onClick={() => setVisibleColumns(new Set())} disabled={visibleColumns.size === 0}>Deselect All</Button>
                                            </Box>
                                            <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                                                {MARKET_COLUMNS.map(col => (
                                                    <FormControlLabel
                                                        key={col.market}
                                                        control={
                                                            <Checkbox
                                                                checked={visibleColumns.has(col.market)}
                                                                onChange={() => toggleColumn(col.market)}
                                                                color="primary"
                                                            />
                                                        }
                                                        label={<Typography variant="body2" sx={{ color: 'var(--text-primary)' }}>{col.label}</Typography>}
                                                    />
                                                ))}
                                            </Box>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <label style={{ fontSize: '14px', color: 'var(--text-primary)' }}>Sort</label>
                                            <select className="field" value={sortBy} onChange={e => setSortBy(e.target.value)}>
                                                {ALL_COLS.map(col => (
                                                    <option key={col.key} value={col.key}>{col.label}</option>
                                                ))}
                                            </select>
                                            <select className="field" value={sortDir} onChange={e => setSortDir(e.target.value as 'asc' | 'desc')}>
                                                <option value="asc">Asc</option>
                                                <option value="desc">Desc</option>
                                            </select>
                                        </div>
                                    </Box>
                                )}
                                <Divider sx={{ my: 2, borderColor: 'var(--border)' }} />
                                <Button
                                    variant="outlined"
                                    onClick={resetDiscoverFilters}
                                    sx={{ color: 'var(--text-secondary)', borderColor: 'var(--border-strong)' }}
                                >
                                    Reset to defaults
                                </Button>
                            </Box>
                        );
                        const paperSx = { background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text-primary)' };
                        return isMobile ? (
                            <SwipeableDrawer
                                anchor="bottom"
                                open={filtersOpen}
                                onOpen={() => setFiltersOpen(true)}
                                onClose={closeFilters}
                                aria-labelledby="discover-filters-title"
                                slotProps={{ paper: { sx: paperSx } }}
                            >
                                {drawerBody}
                            </SwipeableDrawer>
                        ) : (
                            <Drawer
                                anchor="right"
                                open={filtersOpen}
                                onClose={closeFilters}
                                aria-labelledby="discover-filters-title"
                                slotProps={{ paper: { sx: paperSx } }}
                            >
                                {drawerBody}
                            </Drawer>
                        );
                    })()}

                    {/* Table container */}
                    <div style={{
                        flex: 1,
                        overflowY: 'auto',
                        background: 'var(--bg-card)',
                        borderRadius: 'var(--radius-lg)'
                    }}>
                        {!loading && data && data.total === 0 && (
                            <div className="card text-center py-16 fade-in">
                                <p className="font-mono text-base" style={{ color: 'var(--text-secondary)' }}>
                                    No matches available.
                                </p>
                                <p className="font-mono text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>
                                    Click "↓ Pull Update" to fetch new data from the server.
                                </p>
                            </div>
                        )}

                        {data && data.total > 0 && (
                            <div className="card overflow-hidden min-w-0" style={{ height: '100%' }}>
                                <div className="overflow-auto" style={{ height: '100%' }}>
                                    <table className="w-full" style={{ borderCollapse: 'collapse' }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                                <th className="px-4 py-3 text-left font-mono text-xs tracking-widest uppercase w-8 sticky top-0 z-10"
                                                    style={{ color: 'var(--text-secondary)', background: 'var(--bg-raised)' }}>#</th>
                                                {ALL_COLS
                                                    .filter(col => {
                                                        // Fixed columns always visible; market columns filtered by visibility
                                                        const mc = MARKET_COLUMNS.find(m => m.consKey === col.key);
                                                        return !mc || visibleColumns.has(mc.market);
                                                    })
                                                    .map(col => {
                                                        const isHome = col.key === 'home';
                                                        const isAway = col.key === 'away';
                                                        const stickyClass = (isHome || isAway) ? ' sticky-col' : '';
                                                        const stickyStyle = isHome ? { left: 0, minWidth: 140, maxWidth: 180 } : isAway ? { left: 140, minWidth: 140, maxWidth: 180 } : {};
                                                        return (
                                                            <th key={col.key}
                                                                className={`px-4 py-3 font-mono text-xs tracking-widest uppercase cursor-pointer select-none sticky top-0 z-10${stickyClass}`}
                                                                style={{
                                                                    color: sortBy === col.key ? 'var(--accent)' : 'var(--text-secondary)',
                                                                    background: 'var(--bg-raised)',
                                                                    textAlign: col.wide ? 'left' : 'center',
                                                                    ...stickyStyle,
                                                                }}
                                                                onClick={() => handleSort(col.key)}>
                                                                {col.label}
                                                                {sortBy === col.key && (
                                                                    <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
                                                                )}
                                                            </th>
                                                        );
                                                    })}
                                            </tr>
                                        </thead>
                                        <tbody>
                                        {data.matches.map((m, i) => {
                                                const activeMarkets = new Set<string>(
                                                    pendingLegs
                                                        .filter(leg => leg.result_url === m.result_url)
                                                        .map(leg => leg.market)
                                                );
                                                const inSlipMarkets = new Set<string>();
                                                if (m.result_url) {
                                                    slipSelections.forEach(selection => {
                                                        const [url, market] = selection.split('|');
                                                        if (url === m.result_url) {
                                                            inSlipMarkets.add(market);
                                                        }
                                                    });
                                                }
                                                return (
                                                    <MatchRow
                                                        key={m.match_id ?? i}
                                                        match={m}
                                                        index={(page - 1) * PAGE_SIZE + i + 1}
                                                        onCellClick={handleCellClick}
                                                        activeMarkets={activeMarkets}
                                                        inSlipMarkets={inSlipMarkets}
                                                        movement={m.match_id != null ? movements[m.match_id] : undefined}
                                                        visibleColumns={visibleColumns}
                                                    />
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Pagination - outside table */}
                    {data && data.total > 0 && (
                        <div style={{ flexShrink: 0 }}>
                            <Pagination page={page} totalPages={data.total_pages} onPageChange={handlePageChange} />
                        </div>
                    )}

        </div>

        {/* Floating Slip Builder - outside overflow container so fixed positioning works */}
        <FloatingSlipBuilder
                legs={pendingLegs}
                onRemoveLeg={handleRemoveLeg}
                onSubmit={handleAddSlip}
                isMinimized={isSlipMinimized}
                onToggleMinimize={handleToggleSlip}
            />
        </>
    );
}
