import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Button, Drawer, SwipeableDrawer, Typography, useMediaQuery } from '@mui/material';
import { fetchAnalytics } from '../api/data';
import EmptyState, { AnalyticsEmptyIcon } from '../components/EmptyState';
import DateRangeFields from '../components/DateRangeFields';
import { ProfileSelector } from '../components/ui/ProfileSelector';
import { useProfileSelection } from '../hooks/useProfileSelection';
import { usePageDateRange } from '../hooks/usePageDateRange';
import FinancialsSection from '../components/analytics/FinancialsSection';
import StrategySection from '../components/analytics/StrategySection';
import RetrospectionSection from '../components/analytics/RetrospectionSection';
import { computeFinancials } from '../utils/analyticsFinancials';
import { computeStrategy } from '../utils/analyticsStrategy';
import type { AnalyticsData } from '../types';

interface Props {
    refreshKey: number;
}

export default function Analytics({ refreshKey }: Props) {
    const { dateFrom, setDateFrom, dateTo, setDateTo } = usePageDateRange('analytics');
    const navigate = useNavigate();
    const [data, setData] = useState<AnalyticsData | null>(null);
    const { selectedProfiles, setSelectedProfiles } = useProfileSelection({
        page: 'analytics',
        allProfiles: data?.profiles ?? [],
    });
    const [loading, setLoading] = useState(false);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const filtersBtnRef = useRef<HTMLButtonElement>(null);
    const isMobile = useMediaQuery('(max-width:767.95px)');

    const load = useCallback(async () => {
        void refreshKey; // deliberate signal: WS event triggers refetch (test-pinned wiring)
        setLoading(true);
        try {
            const params: Parameters<typeof fetchAnalytics>[0] = {
                date_from: dateFrom || undefined,
                date_to: dateTo || undefined,
            };
            if (selectedProfiles.length > 0) params.profiles = selectedProfiles;
            const d = await fetchAnalytics(params);
            setData(d);
        } catch {
            setData({
                stats: {
                    total_settled: 0,
                    total_won_count: 0,
                    win_rate: 0,
                    implied_win_rate: 0,
                    edge: 0,
                    total_units_bet: 0,
                    gross_return: 0,
                    net_profit: 0,
                    roi_percentage: 0,
                    avg_odds: 0,
                    avg_units: 0,
                    units_std: 0,
                    pending_count: 0,
                    open_exposure: 0,
                    sharpe_ratio: null,
                    kelly_suggested_units: 0,
                    edge_trend: 'neutral',
                    recent_edge_value: 0,
                    biggest_win_units: null,
                    biggest_loss_units: null,
                    best_day_pnl: null,
                    worst_day_pnl: null,
                    current_streak: 0,
                    longest_win_streak: 0,
                    longest_loss_streak: 0,
                    profit_factor: 0,
                },
                history: [],
                odds_distribution: [],
                pnl_by_market: [],
                market_accuracy: [],
                correlation: [],
                profile_scatter: [],
                profiles: [],
                market_breakdown: [],
                league_breakdown: [],
                rolling_edge: [],
                drawdown: [],
                return_distribution: null,
                time_patterns: null,
                source_breakdown: [],
            });
        } finally {
            setLoading(false);
        }
    }, [selectedProfiles, dateFrom, dateTo, refreshKey]);

    useEffect(() => {
        load();
    }, [load]);

    function closeFilters() {
        setFiltersOpen(false);
        queueMicrotask(() => filtersBtnRef.current?.focus());
    }

    const profilesShowing = (selectedProfiles.length > 0 ? selectedProfiles : data?.profiles ?? [])
        .filter(profile => data?.profiles.includes(profile));

    const dateSummary = dateFrom && dateTo
        ? `${dateFrom} – ${dateTo}`
        : dateFrom
            ? `From ${dateFrom}`
            : dateTo
                ? `Until ${dateTo}`
                : null;

    const filterControls = (
        <>
            <div className="flex items-center justify-between gap-3 mb-5">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {dateSummary && <span>{dateSummary}</span>}
                    {profilesShowing.length > 0 && (
                        <span className="font-medium" style={{ color: 'var(--accent)' }}>
                            {profilesShowing.length} profile{profilesShowing.length === 1 ? '' : 's'} showing: {profilesShowing.join(', ')}
                        </span>
                    )}
                </div>
                <Button
                    ref={filtersBtnRef}
                    variant="outlined"
                    size="small"
                    onClick={() => setFiltersOpen(true)}
                    aria-expanded={filtersOpen}
                    aria-controls="analytics-filters-drawer"
                >
                    Filters
                </Button>
            </div>
            {(() => {
                const drawerBody = (
                    <Box
                        id="analytics-filters-drawer"
                        role="document"
                        sx={{ p: 2, width: isMobile ? '100%' : 360, maxHeight: isMobile ? '85vh' : '100%', overflow: 'auto' }}
                    >
                        <Typography id="analytics-filters-title" variant="h6" sx={{ color: 'var(--text-bright)', mb: 2 }}>
                            Filters
                        </Typography>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                            <ProfileSelector
                                profiles={data?.profiles ?? []}
                                selectedProfiles={selectedProfiles}
                                onChange={setSelectedProfiles}
                            />
                            <DateRangeFields
                                dateFrom={dateFrom}
                                dateTo={dateTo}
                                onDateFromChange={setDateFrom}
                                onDateToChange={setDateTo}
                            />
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
                        aria-labelledby="analytics-filters-title"
                        slotProps={{ paper: { sx: paperSx } }}
                    >
                        {drawerBody}
                    </SwipeableDrawer>
                ) : (
                    <Drawer
                        anchor="right"
                        open={filtersOpen}
                        onClose={closeFilters}
                        aria-labelledby="analytics-filters-title"
                        slotProps={{ paper: { sx: paperSx } }}
                    >
                        {drawerBody}
                    </Drawer>
                );
            })()}
        </>
    );

    // Compute derived metrics using pure functions
    const financialsMetrics = useMemo(() => computeFinancials(data), [data]);
    const strategyMetrics = useMemo(() => computeStrategy(data), [data]);

    // Empty state when stats missing (null payload). Fetch-error catch sets zeroed stats.
    if (!data?.stats) {
        return (
            <div>
                {filterControls}
                <div className="mt-5">
                    <EmptyState
                        icon={<AnalyticsEmptyIcon />}
                        title="No analytics yet"
                        steps={['Generate slips in Track', 'Wait for settlement', 'Return here']}
                        primary={{ label: 'Go to Track', onClick: () => navigate('/slips') }}
                        secondary={{ label: 'Go to Build', onClick: () => navigate('/builder') }}
                    />
                </div>
            </div>
        );
    }

    return (
        <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .2s' }}>
            {filterControls}

            {/* ── 1. Financials: WHAT HAPPENED ───────────────────────────── */}
            <FinancialsSection
                metrics={financialsMetrics}
                history={data.history ?? []}
                drawdown={data.drawdown ?? []}
            />

            {/* ── 2. Strategy: WAS IT JUSTIFIED ──────────────────────────── */}
            <StrategySection
                metrics={strategyMetrics}
            />

            {/* ── 3. Retrospection: WHERE DID IT COME FROM ────────────────── */}
            <RetrospectionSection
                marketBreakdown={data.market_breakdown ?? []}
                leagueBreakdown={data.league_breakdown ?? []}
                sourceBreakdown={data.source_breakdown ?? []}
                correlationMatrix={data.correlation_matrix}
                sourceMarketCorrelation={data.source_market_correlation}
            />
        </div>
    );
}
