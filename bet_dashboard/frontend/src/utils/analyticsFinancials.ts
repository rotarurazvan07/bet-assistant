import type { AnalyticsData, HistoryRecord } from '../types';

export interface PeriodSummary {
    period: string;
    net_profit: number;
    turnover: number;
    roi_percentage: number;
    bets_count: number;
}

export interface FinancialsMetrics {
    // Headline / Highlight
    net_profit: number;
    net_profit_30d_change: number | null;
    annualized_return: number | null;
    history_days: number;
    is_early_estimate: boolean;
    roi_percentage: number;

    // Capital
    initial_bankroll: number | null;
    bankroll: number | null;
    turnover: number;
    open_exposure: number;

    // Risk
    max_drawdown: number;
    current_drawdown: number;
    current_streak: number;
    longest_loss_streak: number;
    longest_win_streak: number;
    sharpe_ratio: number | null;

    // Quality of returns
    profit_factor: number | null;
    rolling_roi: number | null;
    biggest_win: number | null;
    biggest_loss: number | null;

    // Footer
    sample_size: number;
    days_covered: number;
    roi_ci: [number, number] | null;
    this_month_pnl: number | null;
    best_month: PeriodSummary | null;
    worst_month: PeriodSummary | null;
    best_day_pnl: number | null;
    worst_day_pnl: number | null;

    // Detail
    underwater: {
        longest_days: number;
        current_days: number;
    };
    daily_periods: PeriodSummary[];
    weekly_periods: PeriodSummary[];
    monthly_periods: PeriodSummary[];
    rolling_roi_series: { date: string; rolling_roi: number }[];
    pnl_by_weekday: { day: string; net_profit: number; bets_count: number }[];
    pnl_by_month: { month: string; net_profit: number; bets_count: number }[];
    concentration: {
        biggest_win_share: number | null;
        biggest_loss_share: number | null;
    };
}

/**
 * Deterministic seeded random number generator (Mulberry32).
 */
function createSeededRng(seed = 42): () => number {
    let s = seed >>> 0;
    return () => {
        s = (s + 0x6D2B79F5) >>> 0;
        let t = Math.imul(s ^ (s >>> 15), 1 | s);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

/**
 * Deterministic bootstrap confidence interval on ROI.
 * Resamples daily history rows with replacement to build empirical distribution.
 */
export function computeBootstrapRoiCi(
    history: HistoryRecord[],
    iterations = 1000,
    seed = 42
): [number, number] | null {
    const valid = history.filter(h => h.units_bet > 0);
    if (valid.length < 2) return null;

    const totalTurnover = valid.reduce((sum, h) => sum + h.units_bet, 0);
    if (totalTurnover <= 0) return null;

    const rng = createSeededRng(seed);
    const n = valid.length;
    const rois: number[] = new Array(iterations);

    for (let b = 0; b < iterations; b++) {
        let sampleProfit = 0;
        let sampleBet = 0;
        for (let i = 0; i < n; i++) {
            const idx = Math.floor(rng() * n);
            const row = valid[idx];
            sampleProfit += row.net_profit;
            sampleBet += row.units_bet;
        }
        rois[b] = sampleBet > 0 ? (sampleProfit / sampleBet) * 100 : 0;
    }

    rois.sort((a, b) => a - b);
    const lowerIdx = Math.floor(0.025 * iterations);
    const upperIdx = Math.min(iterations - 1, Math.floor(0.975 * iterations));
    return [
        Math.round(rois[lowerIdx] * 10) / 10,
        Math.round(rois[upperIdx] * 10) / 10,
    ];
}

/**
 * Computes all Financials metrics according to Section 3 of the specification.
 * Pure function: no I/O, no DOM rendering, deterministic output.
 */
export function computeFinancials(data: Partial<AnalyticsData> | null | undefined): FinancialsMetrics {
    const stats = data?.stats;
    const history = [...(data?.history ?? [])].sort((a, b) => a.date.localeCompare(b.date));
    const drawdown = data?.drawdown ?? [];

    const netProfit = stats?.net_profit ?? 0;
    const turnover = stats?.total_units_bet ?? 0;
    const sampleSize = stats?.total_settled ?? 0;
    const roiPercentage = stats?.roi_percentage ?? (turnover > 0 ? (netProfit / turnover) * 100 : 0);

    // Days covered
    let daysCovered = 0;
    if (history.length > 0) {
        const first = new Date(history[0].date).getTime();
        const last = new Date(history[history.length - 1].date).getTime();
        daysCovered = Math.max(1, Math.round((last - first) / (24 * 3600 * 1000)) + 1);
    }

    // 30-day profit change
    let netProfit30dChange: number | null = null;
    if (history.length > 0) {
        const lastDate = new Date(history[history.length - 1].date);
        const cutoffDate = new Date(lastDate);
        cutoffDate.setDate(cutoffDate.getDate() - 30);
        const recent = history.filter(h => new Date(h.date) >= cutoffDate);
        netProfit30dChange = recent.reduce((sum, h) => sum + h.net_profit, 0);
        netProfit30dChange = Math.round(netProfit30dChange * 100) / 100;
    }

    const initialBankroll = stats?.initial_bankroll ?? null;
    const bankroll = stats?.bankroll ?? null;
    let annualizedReturn: number | null = null;
    if (initialBankroll !== null && initialBankroll > 0 && bankroll !== null && bankroll > 0 && daysCovered > 0) {
        const annualizedFraction = Math.pow(bankroll / initialBankroll, 365 / daysCovered) - 1;
        if (Number.isFinite(annualizedFraction)) {
            annualizedReturn = Math.round(annualizedFraction * 1000) / 10;
        }
    }
    const isEarlyEstimate = daysCovered > 0 && daysCovered < 90;

    // Drawdowns
    const maxDrawdown = drawdown.length > 0 ? Math.min(...drawdown.map(d => d.drawdown)) : 0;
    const currentDrawdown = drawdown.length > 0 ? drawdown[drawdown.length - 1].drawdown : 0;

    // Underwater analysis (days continuously below peak)
    let longestUnderwaterDays = 0;
    let currentUnderwaterDays = 0;
    let tempUnderwaterDays = 0;
    for (let i = 0; i < drawdown.length; i++) {
        if (drawdown[i].drawdown < 0) {
            tempUnderwaterDays++;
            longestUnderwaterDays = Math.max(longestUnderwaterDays, tempUnderwaterDays);
        } else {
            tempUnderwaterDays = 0;
        }
    }
    currentUnderwaterDays = tempUnderwaterDays;

    // Periods breakdown: Daily, Weekly, Monthly
    const dailyPeriods: PeriodSummary[] = history.map(h => ({
        period: h.date,
        net_profit: h.net_profit,
        turnover: h.units_bet,
        roi_percentage: h.units_bet > 0 ? Math.round((h.net_profit / h.units_bet) * 1000) / 10 : 0,
        bets_count: h.slips_count,
    }));

    // Weekly grouping
    const weeklyMap: Record<string, { net_profit: number; turnover: number; bets_count: number }> = {};
    for (const h of history) {
        const d = new Date(h.date);
        // Start of week (Monday)
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1);
        const monday = new Date(d.setDate(diff));
        const weekKey = monday.toISOString().slice(0, 10);
        if (!weeklyMap[weekKey]) {
            weeklyMap[weekKey] = { net_profit: 0, turnover: 0, bets_count: 0 };
        }
        weeklyMap[weekKey].net_profit += h.net_profit;
        weeklyMap[weekKey].turnover += h.units_bet;
        weeklyMap[weekKey].bets_count += h.slips_count;
    }
    const weeklyPeriods: PeriodSummary[] = Object.entries(weeklyMap)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([period, v]) => ({
            period,
            net_profit: Math.round(v.net_profit * 100) / 100,
            turnover: Math.round(v.turnover * 100) / 100,
            roi_percentage: v.turnover > 0 ? Math.round((v.net_profit / v.turnover) * 1000) / 10 : 0,
            bets_count: v.bets_count,
        }));

    // Monthly grouping
    const monthlyMap: Record<string, { net_profit: number; turnover: number; bets_count: number }> = {};
    for (const h of history) {
        const monthKey = h.date.slice(0, 7); // YYYY-MM
        if (!monthlyMap[monthKey]) {
            monthlyMap[monthKey] = { net_profit: 0, turnover: 0, bets_count: 0 };
        }
        monthlyMap[monthKey].net_profit += h.net_profit;
        monthlyMap[monthKey].turnover += h.units_bet;
        monthlyMap[monthKey].bets_count += h.slips_count;
    }
    const monthlyPeriods: PeriodSummary[] = Object.entries(monthlyMap)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([period, v]) => ({
            period,
            net_profit: Math.round(v.net_profit * 100) / 100,
            turnover: Math.round(v.turnover * 100) / 100,
            roi_percentage: v.turnover > 0 ? Math.round((v.net_profit / v.turnover) * 1000) / 10 : 0,
            bets_count: v.bets_count,
        }));

    // This month / best month / worst month
    const currentMonthKey = new Date().toISOString().slice(0, 7);
    const thisMonthEntry = monthlyPeriods.find(m => m.period === currentMonthKey) ??
        (monthlyPeriods.length > 0 ? monthlyPeriods[monthlyPeriods.length - 1] : null);
    const thisMonthPnl = thisMonthEntry ? thisMonthEntry.net_profit : null;

    let bestMonth: PeriodSummary | null = null;
    let worstMonth: PeriodSummary | null = null;
    if (monthlyPeriods.length > 0) {
        bestMonth = monthlyPeriods.reduce((best, m) => m.net_profit > best.net_profit ? m : best, monthlyPeriods[0]);
        worstMonth = monthlyPeriods.reduce((worst, m) => m.net_profit < worst.net_profit ? m : worst, monthlyPeriods[0]);
    }

    // Rolling ROI series (14-day rolling window)
    const rollingRoiSeries: { date: string; rolling_roi: number }[] = [];
    const windowDays = 14;
    for (let i = 0; i < history.length; i++) {
        const curDate = new Date(history[i].date);
        const winStart = new Date(curDate);
        winStart.setDate(winStart.getDate() - windowDays);
        let winProfit = 0;
        let winTurnover = 0;
        for (let j = 0; j <= i; j++) {
            const d = new Date(history[j].date);
            if (d >= winStart && d <= curDate) {
                winProfit += history[j].net_profit;
                winTurnover += history[j].units_bet;
            }
        }
        if (winTurnover > 0) {
            rollingRoiSeries.push({
                date: history[i].date,
                rolling_roi: Math.round((winProfit / winTurnover) * 1000) / 10,
            });
        }
    }
    const rollingRoi = rollingRoiSeries.length > 0
        ? rollingRoiSeries[rollingRoiSeries.length - 1].rolling_roi
        : null;

    // P&L by weekday
    const weekdayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const weekdayMap = weekdayNames.map(day => ({ day, net_profit: 0, bets_count: 0 }));
    for (const h of history) {
        const dayIdx = new Date(h.date).getDay();
        weekdayMap[dayIdx].net_profit += h.net_profit;
        weekdayMap[dayIdx].bets_count += h.slips_count;
    }
    const pnlByWeekday = weekdayMap.map(w => ({
        day: w.day,
        net_profit: Math.round(w.net_profit * 100) / 100,
        bets_count: w.bets_count,
    }));

    // P&L by calendar month
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const calMonthMap = monthNames.map(month => ({ month, net_profit: 0, bets_count: 0 }));
    for (const h of history) {
        const mIdx = new Date(h.date).getMonth();
        calMonthMap[mIdx].net_profit += h.net_profit;
        calMonthMap[mIdx].bets_count += h.slips_count;
    }
    const pnlByMonth = calMonthMap.map(m => ({
        month: m.month,
        net_profit: Math.round(m.net_profit * 100) / 100,
        bets_count: m.bets_count,
    }));

    // Concentration
    const biggestWin = stats?.biggest_win_units ?? null;
    const biggestLoss = stats?.biggest_loss_units ?? null;
    const biggestWinShare = (biggestWin !== null && netProfit > 0)
        ? Math.round((biggestWin / netProfit) * 1000) / 10
        : null;
    const biggestLossShare = (biggestLoss !== null && netProfit > 0)
        ? Math.round((Math.abs(biggestLoss) / netProfit) * 1000) / 10
        : null;

    // ROI Confidence interval
    const roiCi = computeBootstrapRoiCi(history);

    const openExposure = stats?.open_exposure ?? 0;

    return {
        net_profit: netProfit,
        net_profit_30d_change: netProfit30dChange,
        annualized_return: annualizedReturn,
        history_days: daysCovered,
        is_early_estimate: isEarlyEstimate,
        roi_percentage: roiPercentage,
        initial_bankroll: initialBankroll,
        bankroll,
        turnover,
        open_exposure: openExposure,
        max_drawdown: maxDrawdown,
        current_drawdown: currentDrawdown,
        current_streak: stats?.current_streak ?? 0,
        longest_loss_streak: stats?.longest_loss_streak ?? 0,
        longest_win_streak: stats?.longest_win_streak ?? 0,
        sharpe_ratio: stats?.sharpe_ratio ?? null,
        profit_factor: stats?.profit_factor ?? null,
        rolling_roi: rollingRoi,
        biggest_win: biggestWin,
        biggest_loss: biggestLoss,
        sample_size: sampleSize,
        days_covered: daysCovered,
        roi_ci: roiCi,
        this_month_pnl: thisMonthPnl,
        best_month: bestMonth,
        worst_month: worstMonth,
        best_day_pnl: stats?.best_day_pnl ?? null,
        worst_day_pnl: stats?.worst_day_pnl ?? null,
        underwater: {
            longest_days: longestUnderwaterDays,
            current_days: currentUnderwaterDays,
        },
        daily_periods: dailyPeriods,
        weekly_periods: weeklyPeriods,
        monthly_periods: monthlyPeriods,
        rolling_roi_series: rollingRoiSeries,
        pnl_by_weekday: pnlByWeekday,
        pnl_by_month: pnlByMonth,
        concentration: {
            biggest_win_share: biggestWinShare,
            biggest_loss_share: biggestLossShare,
        },
    };
}
