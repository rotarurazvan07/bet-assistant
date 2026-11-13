import { useState } from 'react';
import AnalyticsSection from './AnalyticsSection';
import QuickviewContainer, { type QuickviewTile } from './QuickviewContainer';
import MiniSparkline from './charts/MiniSparkline';
import EquityDrawdownChart from './charts/EquityDrawdownChart';
import RollingLineChart from './charts/RollingLineChart';
import type { FinancialsMetrics } from '../../utils/analyticsFinancials';
import type { HistoryRecord, DrawdownPoint } from '../../types';

interface FinancialsSectionProps {
    metrics: FinancialsMetrics;
    history: HistoryRecord[];
    drawdown: DrawdownPoint[];
    defaultExpanded?: boolean;
}

export default function FinancialsSection({
    metrics,
    history,
    drawdown,
    defaultExpanded = false,
}: FinancialsSectionProps) {
    const [periodTab, setPeriodTab] = useState<'daily' | 'weekly' | 'monthly'>('monthly');

    // Streaks display
    const currentStreak = metrics.current_streak ?? 0;
    const streakDir = currentStreak > 0 ? 'win' : currentStreak < 0 ? 'loss' : null;
    const streakAbs = Math.abs(currentStreak);
    const streakColor = streakDir === 'win' ? 'var(--win)' : streakDir === 'loss' ? 'var(--loss)' : 'var(--text-secondary)';
    const streakLabel = streakDir === 'win' ? 'W' : streakDir === 'loss' ? 'L' : '';

    // Profit factor color & grade
    const pf = metrics.profit_factor;
    const pfColor = pf == null ? 'var(--text-secondary)'
        : pf >= 2 ? 'var(--win)'
        : pf >= 1.2 ? 'var(--pending)'
        : pf >= 1 ? 'var(--text-bright)'
        : 'var(--loss)';
    const pfGrade = pf == null ? 'n/a'
        : pf >= 2 ? 'Strong' : pf >= 1.2 ? 'Good' : pf >= 1 ? 'Breakeven' : 'Negative';

    // Sharpe color
    const sharpe = metrics.sharpe_ratio;
    const sharpeColor = sharpe == null ? 'var(--text-secondary)'
        : sharpe > 1.5 ? 'var(--win)'
        : sharpe > 0.5 ? 'var(--pending)'
        : 'var(--loss)';

    // Cumulative equity series for sparkline
    const sparklineData = (history ?? [])
        .map(h => h.bankroll ?? (metrics.initial_bankroll !== null ? metrics.initial_bankroll + h.cumulative_profit : null))
        .filter((value): value is number => value !== null);

    // Tiles for Quickview
    const tiles: QuickviewTile[] = [
        // 1. Net Profit
        {
            label: 'Net Profit',
            value: typeof metrics.net_profit === 'number'
                ? `${metrics.net_profit > 0 ? '+' : ''}${metrics.net_profit}U`
                : 'n/a',
            sub: typeof metrics.net_profit_30d_change === 'number'
                ? `${metrics.net_profit_30d_change >= 0 ? '+' : ''}${metrics.net_profit_30d_change.toFixed(2)}U (last 30d)`
                : `${metrics.sample_size ?? 0} settled slips`,
            color: (metrics.net_profit ?? 0) > 0 ? 'var(--win)' : (metrics.net_profit ?? 0) < 0 ? 'var(--loss)' : 'var(--text-bright)',
            tip: 'Total net profit across all settled bets in units.',
            highlight: true,
        },
        // 2. Annualized Return
        {
            label: 'Annualized',
            value: typeof metrics.annualized_return === 'number'
                ? `${metrics.annualized_return >= 0 ? '+' : ''}${metrics.annualized_return.toFixed(1)}%`
                : 'n/a',
            badge: metrics.history_days > 0 ? {
                text: `${metrics.history_days}d${metrics.is_early_estimate ? ' • early' : ''}`,
                color: metrics.is_early_estimate ? 'var(--pending)' : 'var(--text-secondary)',
            } : undefined,
            sub: metrics.initial_bankroll !== null
                ? `Opening stake: ${metrics.initial_bankroll.toFixed(1)}U`
                : 'No settled stakes yet',
            color: typeof metrics.annualized_return === 'number' && metrics.annualized_return >= 0 ? 'var(--win)' : 'var(--text-bright)',
            tip: 'Annualized compound return using the first settled stake as the inferred opening bankroll. This is an estimate, not an externally funded account balance.',
        },
        // 3. ROI on turnover
        {
            label: 'ROI',
            value: typeof metrics.roi_percentage === 'number'
                ? `${metrics.roi_percentage >= 0 ? '+' : ''}${metrics.roi_percentage.toFixed(1)}%`
                : 'n/a',
            sub: `${(metrics.turnover ?? 0).toFixed(1)}U staked`,
            color: (metrics.roi_percentage ?? 0) > 0 ? 'var(--win)' : (metrics.roi_percentage ?? 0) < 0 ? 'var(--loss)' : 'var(--text-bright)',
            tip: 'Return on investment as a percentage of total turnover staked.',
        },
        // 4. Bankroll
        {
            label: 'Bankroll',
            value: typeof metrics.bankroll === 'number' ? `${metrics.bankroll.toFixed(1)}U` : 'n/a',
            sub: `Exposure: ${(metrics.open_exposure ?? 0).toFixed(1)}U`,
            color: typeof metrics.bankroll === 'number' && metrics.bankroll >= 0 ? 'var(--win)' : 'var(--loss)',
            tip: 'Inferred opening balance (the first settled stake) plus cumulative net profit. Pending stakes are shown separately as exposure.',
        },
        // 5. Max Drawdown
        {
            label: 'Max Drawdown',
            value: `${(metrics.max_drawdown ?? 0).toFixed(1)}U`,
            sub: `Current: ${(metrics.current_drawdown ?? 0).toFixed(2)}U`,
            color: (metrics.max_drawdown ?? 0) > -3 ? 'var(--win)' : (metrics.max_drawdown ?? 0) > -8 ? 'var(--pending)' : 'var(--loss)',
            tip: 'Maximum peak-to-trough decline and current distance from peak.',
        },
        // 6. Risk-Adjusted Return (Sharpe)
        {
            label: 'Sharpe Ratio',
            value: typeof sharpe === 'number' ? sharpe.toFixed(2) : 'n/a',
            sub: typeof sharpe === 'number' ? (sharpe > 1.5 ? 'Good' : sharpe > 0.5 ? 'Fair' : 'Poor') : undefined,
            color: sharpeColor,
            tip: 'Risk-adjusted return based on daily P&L volatility. >1.5 = good, >0.5 = fair.',
        },
        // 7. Profit Factor
        {
            label: 'Profit Factor',
            value: typeof pf === 'number' ? pf.toFixed(2) : 'n/a',
            sub: pfGrade,
            color: pfColor,
            tip: 'Gross wins ÷ gross losses. >1.0 = profitable, >2.0 = strong edge.',
        },
        // 8. Day Streak
        {
            label: 'Day Streak',
            value: streakAbs,
            badge: streakDir ? { text: streakLabel, color: streakColor } : undefined,
            sub: streakDir === 'win' ? 'consecutive win days' : streakDir === 'loss' ? 'consecutive loss days' : 'flat',
            color: streakColor,
            tip: 'Current consecutive run of winning or losing days.',
        },
        // 9. Rolling ROI
        {
            label: 'Rolling ROI',
            value: typeof metrics.rolling_roi === 'number' ? `${metrics.rolling_roi >= 0 ? '+' : ''}${metrics.rolling_roi.toFixed(1)}%` : 'n/a',
            sub: '14-day window',
            color: typeof metrics.rolling_roi === 'number' && metrics.rolling_roi >= 0 ? 'var(--win)' : 'var(--loss)',
            tip: 'Rolling return on investment over the last 14 days.',
        },
        // 10. Biggest Win
        {
            label: 'Biggest Win',
            value: typeof metrics.biggest_win === 'number' ? `+${metrics.biggest_win.toFixed(2)}U` : 'n/a',
            sub: typeof metrics.best_day_pnl === 'number' ? `Best day: +${metrics.best_day_pnl.toFixed(2)}U` : undefined,
            color: 'var(--win)',
            tip: 'Highest single-slip net win and highest single-day net profit.',
        },
        // 11. Biggest Loss
        {
            label: 'Biggest Loss',
            value: typeof metrics.biggest_loss === 'number' ? `${metrics.biggest_loss.toFixed(2)}U` : 'n/a',
            sub: typeof metrics.worst_day_pnl === 'number' ? `Worst day: ${metrics.worst_day_pnl.toFixed(2)}U` : undefined,
            color: 'var(--loss)',
            tip: 'Worst single-slip net loss and lowest single-day net profit.',
        },
        // 12. Open Exposure
        {
            label: 'Open Exposure',
            value: `${(metrics.open_exposure ?? 0).toFixed(1)}U`,
            sub: 'pending capital at risk',
            color: 'var(--pending)',
            tip: 'Total staked units committed to pending, unsettled slips.',
        },
    ];

    const quickviewFooter = (
        <>
            <div className="flex items-center gap-4 flex-wrap">
                <span>Sample: <strong className="text-[var(--text-bright)]">{metrics.sample_size ?? 0}</strong> bets ({metrics.history_days ?? 0} days)</span>
                {metrics.roi_ci && (
                    <span>
                        ROI 95% CI: <strong className="text-[var(--text-bright)]">[{metrics.roi_ci[0]}%, {metrics.roi_ci[1]}%]</strong>
                    </span>
                )}
            </div>
            <div className="flex items-center gap-4 flex-wrap">
                {typeof metrics.this_month_pnl === 'number' && (
                    <span>This month: <strong style={{ color: metrics.this_month_pnl >= 0 ? 'var(--win)' : 'var(--loss)' }}>{metrics.this_month_pnl >= 0 ? '+' : ''}{metrics.this_month_pnl.toFixed(1)}U</strong></span>
                )}
                {metrics.best_month && typeof metrics.best_month.net_profit === 'number' && (
                    <span>Best: <strong style={{ color: 'var(--win)' }}>+{metrics.best_month.net_profit.toFixed(1)}U</strong> ({metrics.best_month.period})</span>
                )}
                {metrics.worst_month && typeof metrics.worst_month.net_profit === 'number' && (
                    <span>Worst: <strong style={{ color: 'var(--loss)' }}>{metrics.worst_month.net_profit.toFixed(1)}U</strong> ({metrics.worst_month.period})</span>
                )}
            </div>
        </>
    );

    const activePeriods = periodTab === 'daily'
        ? (metrics.daily_periods ?? [])
        : periodTab === 'weekly'
            ? (metrics.weekly_periods ?? [])
            : (metrics.monthly_periods ?? []);

    const detailContent = (
        <div className="flex flex-col gap-6">
            {/* Full Equity Curve and Drawdown Charts */}
            <EquityDrawdownChart history={history} drawdown={drawdown} height={240} />

            {/* Underwater and Concentration Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="card p-3 flex flex-col gap-1">
                    <span className="text-[10px] font-mono tracking-widest uppercase text-[var(--text-secondary)]">Max Underwater</span>
                    <span className="font-display font-bold text-xl leading-none text-[var(--loss)]">{metrics.underwater?.longest_days ?? 0} days</span>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">Current: {metrics.underwater?.current_days ?? 0} days</span>
                </div>
                <div className="card p-3 flex flex-col gap-1">
                    <span className="text-[10px] font-mono tracking-widest uppercase text-[var(--text-secondary)]">Longest Win Streak</span>
                    <span className="font-display font-bold text-xl leading-none text-[var(--win)]">{metrics.longest_win_streak ?? 0} days</span>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">Consecutive winning days</span>
                </div>
                <div className="card p-3 flex flex-col gap-1">
                    <span className="text-[10px] font-mono tracking-widest uppercase text-[var(--text-secondary)]">Longest Loss Streak</span>
                    <span className="font-display font-bold text-xl leading-none text-[var(--loss)]">{metrics.longest_loss_streak ?? 0} days</span>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">Consecutive losing days</span>
                </div>
                <div className="card p-3 flex flex-col gap-1">
                    <span className="text-[10px] font-mono tracking-widest uppercase text-[var(--text-secondary)]">Win Concentration</span>
                    <span className="font-display font-bold text-xl leading-none text-[var(--win)]">
                        {metrics.concentration?.biggest_win_share != null ? `${metrics.concentration.biggest_win_share}%` : 'n/a'}
                    </span>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">Top win share of profit</span>
                </div>
            </div>

            {/* Rolling ROI Chart */}
            {(metrics.rolling_roi_series ?? []).length > 2 && (
                <div className="card p-4">
                    <div className="flex items-center justify-between mb-4">
                        <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                            Rolling ROI (14-day window)
                        </span>
                        <span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                            Turnover-weighted return trend
                        </span>
                    </div>
                    <RollingLineChart
                        data={metrics.rolling_roi_series.map(s => ({ date: s.date, value: s.rolling_roi }))}
                        valueKey="value"
                        valueLabel="Rolling ROI"
                        unit="%"
                        height={200}
                    />
                </div>
            )}

            {/* Period P&L Tables with Tabs */}
            <div className="card p-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                        Period Performance & Ledger
                    </span>
                    <div className="flex bg-black/20 p-1 rounded-lg border border-white/5">
                        <button
                            type="button"
                            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase transition-all ${periodTab === 'monthly' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                            onClick={() => setPeriodTab('monthly')}
                        >
                            Monthly
                        </button>
                        <button
                            type="button"
                            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase transition-all ${periodTab === 'weekly' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                            onClick={() => setPeriodTab('weekly')}
                        >
                            Weekly
                        </button>
                        <button
                            type="button"
                            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase transition-all ${periodTab === 'daily' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                            onClick={() => setPeriodTab('daily')}
                        >
                            Daily
                        </button>
                    </div>
                </div>

                <div className="overflow-x-auto rounded-xl border border-[var(--border)] max-h-72">
                    <table className="w-full text-left" style={{ borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-raised)' }}>
                                <th className="px-4 py-2 font-mono text-[10px] uppercase text-[var(--text-secondary)]">Period</th>
                                <th className="px-4 py-2 font-mono text-[10px] uppercase text-[var(--text-secondary)] text-right">Bets</th>
                                <th className="px-4 py-2 font-mono text-[10px] uppercase text-[var(--text-secondary)] text-right">Staked</th>
                                <th className="px-4 py-2 font-mono text-[10px] uppercase text-[var(--text-secondary)] text-right">Net Profit</th>
                                <th className="px-4 py-2 font-mono text-[10px] uppercase text-[var(--text-secondary)] text-right">ROI %</th>
                            </tr>
                        </thead>
                        <tbody>
                            {activePeriods.map((p, i) => (
                                <tr
                                    key={p.period}
                                    style={{
                                        borderBottom: '1px solid var(--border)',
                                        background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                                    }}
                                >
                                    <td className="px-4 py-2 font-mono text-xs font-bold text-[var(--text-bright)]">{p.period}</td>
                                    <td className="px-4 py-2 font-mono text-xs text-[var(--text-secondary)] text-right">{p.bets_count}</td>
                                    <td className="px-4 py-2 font-mono text-xs text-[var(--text-secondary)] text-right">{(p.turnover ?? 0).toFixed(1)}U</td>
                                    <td
                                        className="px-4 py-2 font-mono text-xs font-bold text-right"
                                        style={{ color: p.net_profit >= 0 ? 'var(--win)' : 'var(--loss)' }}
                                    >
                                        {p.net_profit >= 0 ? '+' : ''}{(p.net_profit ?? 0).toFixed(2)}U
                                    </td>
                                    <td
                                        className="px-4 py-2 font-mono text-xs font-bold text-right"
                                        style={{ color: p.roi_percentage >= 0 ? 'var(--win)' : 'var(--loss)' }}
                                    >
                                        {p.roi_percentage >= 0 ? '+' : ''}{(p.roi_percentage ?? 0).toFixed(1)}%
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* P&L Breakdown by Weekday and Month */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="card p-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase mb-3 block text-[var(--text-secondary)]">
                        P&L by Weekday
                    </span>
                    <div className="grid grid-cols-7 gap-1 text-center font-mono">
                        {(metrics.pnl_by_weekday ?? []).map(w => (
                            <div key={w.day} className="rounded p-2" style={{ background: 'var(--bg-raised)' }}>
                                <span className="text-[10px] block text-[var(--text-secondary)]">{w.day}</span>
                                <span
                                    className="text-xs font-bold block mt-1"
                                    style={{ color: w.net_profit >= 0 ? 'var(--win)' : 'var(--loss)' }}
                                >
                                    {w.net_profit >= 0 ? '+' : ''}{(w.net_profit ?? 0).toFixed(1)}
                                </span>
                                <span className="text-[9px] text-gray-500 mt-0.5 block">{w.bets_count}b</span>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="card p-4">
                    <span className="font-mono text-[11px] tracking-widest uppercase mb-3 block text-[var(--text-secondary)]">
                        P&L by Calendar Month
                    </span>
                    <div className="grid grid-cols-6 sm:grid-cols-6 gap-1 text-center font-mono">
                        {(metrics.pnl_by_month ?? []).slice(0, 12).map(m => (
                            <div key={m.month} className="rounded p-1.5" style={{ background: 'var(--bg-raised)' }}>
                                <span className="text-[9px] block text-[var(--text-secondary)]">{m.month}</span>
                                <span
                                    className="text-[11px] font-bold block mt-0.5"
                                    style={{ color: m.net_profit >= 0 ? 'var(--win)' : 'var(--loss)' }}
                                >
                                    {m.net_profit >= 0 ? '+' : ''}{(m.net_profit ?? 0).toFixed(0)}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );

    return (
        <AnalyticsSection
            title="Financials"
            icon="₿"
            quickview={
                <QuickviewContainer
                    tiles={tiles}
                    sparkline={                    <MiniSparkline data={sparklineData} height={108} />}
                    footer={quickviewFooter}
                />
            }
            detail={detailContent}
            defaultExpanded={defaultExpanded}
        />
    );
}
