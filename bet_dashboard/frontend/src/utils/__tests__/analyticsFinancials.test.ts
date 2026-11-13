import { describe, it, expect } from 'vitest';
import { computeFinancials, computeBootstrapRoiCi } from '../analyticsFinancials';
import type { AnalyticsData } from '../../types';

describe('computeFinancials', () => {
    // Hand-computed fixture
    const handComputedData: Partial<AnalyticsData> = {
        stats: {
            total_settled: 5,
            total_won_count: 3,
            win_rate: 60.0,
            implied_win_rate: 50.0,
            edge: 10.0,
            total_units_bet: 50.0, // 5 bets * 10U
            gross_return: 65.0,    // gross payout = 65U
            net_profit: 15.0,      // 65 - 50 = +15U
            initial_bankroll: 10.0,
            bankroll: 25.0,
            roi_percentage: 30.0,  // (15 / 50) * 100 = 30%
            avg_odds: 2.1,
            avg_units: 10.0,
            units_std: 0.0,
            pending_count: 2,
            open_exposure: 20.0,
            sharpe_ratio: 1.45,
            profit_factor: 2.5,
            biggest_win_units: 12.0,
            biggest_loss_units: -10.0,
            best_day_pnl: 12.0,
            worst_day_pnl: -10.0,
            current_streak: 2,
            longest_win_streak: 3,
            longest_loss_streak: 1,
            kelly_suggested_units: 8.5,
            edge_trend: 'growing',
            recent_edge_value: 12.5,
        },
        history: [
            {
                date: '2026-09-01',
                slips_count: 1,
                units_bet: 10,
                net_profit: 12,
                cumulative_profit: 12,
                cumulative_bet: 10,
                roi_percentage: 120,
                win_rate: 100,
            },
            {
                date: '2026-09-02',
                slips_count: 1,
                units_bet: 10,
                net_profit: -10,
                cumulative_profit: 2,
                cumulative_bet: 20,
                roi_percentage: 10,
                win_rate: 50,
            },
            {
                date: '2026-09-03',
                slips_count: 1,
                units_bet: 10,
                net_profit: 5,
                cumulative_profit: 7,
                cumulative_bet: 30,
                roi_percentage: 23.3,
                win_rate: 66.7,
            },
            {
                date: '2026-09-04',
                slips_count: 1,
                units_bet: 10,
                net_profit: -2,
                cumulative_profit: 5,
                cumulative_bet: 40,
                roi_percentage: 12.5,
                win_rate: 50,
            },
            {
                date: '2026-09-05',
                slips_count: 1,
                units_bet: 10,
                net_profit: 10,
                cumulative_profit: 15,
                cumulative_bet: 50,
                roi_percentage: 30,
                win_rate: 60,
            },
        ],
        drawdown: [
            { date: '2026-09-01', drawdown: 0, peak: 12, cumulative_profit: 12 },
            { date: '2026-09-02', drawdown: -10, peak: 12, cumulative_profit: 2 },
            { date: '2026-09-03', drawdown: -5, peak: 12, cumulative_profit: 7 },
            { date: '2026-09-04', drawdown: -7, peak: 12, cumulative_profit: 5 },
            { date: '2026-09-05', drawdown: 0, peak: 15, cumulative_profit: 15 },
        ],
    };

    it('computes exact headline financials from the hand-computed fixture', () => {
        const fin = computeFinancials(handComputedData);

        expect(fin.net_profit).toBe(15.0);
        expect(fin.initial_bankroll).toBe(10.0);
        expect(fin.bankroll).toBe(25.0);
        expect(fin.turnover).toBe(50.0);
        expect(fin.roi_percentage).toBe(30.0);
        expect(fin.sample_size).toBe(5);
        expect(fin.open_exposure).toBe(20.0);
        expect(fin.max_drawdown).toBe(-10.0);
        expect(fin.current_drawdown).toBe(0.0);
        expect(fin.sharpe_ratio).toBe(1.45);
        expect(fin.profit_factor).toBe(2.5);
        expect(fin.biggest_win).toBe(12.0);
        expect(fin.biggest_loss).toBe(-10.0);
    });

    it('calculates days covered and early estimate flag', () => {
        const fin = computeFinancials(handComputedData);
        // 2026-09-01 to 2026-09-05 = 5 days
        expect(fin.history_days).toBe(5);
        expect(fin.is_early_estimate).toBe(true);
    });

    it('computes annualized return from the inferred opening stake and current bankroll', () => {
        const fin = computeFinancials(handComputedData);
        expect(fin.annualized_return).toBeGreaterThan(0);
    });

    it('tracks a 1U opening stake through a win and a loss', () => {
        const data: Partial<AnalyticsData> = {
            stats: {
                ...handComputedData.stats!,
                total_units_bet: 2,
                gross_return: 2,
                net_profit: 0,
                initial_bankroll: 1,
                bankroll: 1,
            },
            history: [
                { date: '2026-09-01', slips_count: 1, units_bet: 1, net_profit: 1, cumulative_profit: 1, cumulative_bet: 1, roi_percentage: 100, win_rate: 100, bankroll: 2 },
                { date: '2026-09-02', slips_count: 1, units_bet: 1, net_profit: -1, cumulative_profit: 0, cumulative_bet: 2, roi_percentage: 0, win_rate: 50, bankroll: 1 },
            ],
        };
        const fin = computeFinancials(data);
        expect(fin.initial_bankroll).toBe(1);
        expect(fin.bankroll).toBe(1);
    });

    it('computes underwater periods correctly', () => {
        const fin = computeFinancials(handComputedData);
        // Drawdowns: 0, -10, -5, -7, 0 -> run of 3 consecutive underwater days
        expect(fin.underwater.longest_days).toBe(3);
        expect(fin.underwater.current_days).toBe(0);
    });

    it('computes profit concentration correctly', () => {
        const fin = computeFinancials(handComputedData);
        // biggest_win = 12, net_profit = 15 -> 12 / 15 = 80.0%
        expect(fin.concentration.biggest_win_share).toBe(80.0);
        // biggest_loss = -10, net_profit = 15 -> 10 / 15 = 66.7%
        expect(fin.concentration.biggest_loss_share).toBe(66.7);
    });

    it('returns deterministic bootstrap ROI confidence interval', () => {
        const ci1 = computeBootstrapRoiCi(handComputedData.history!);
        const ci2 = computeBootstrapRoiCi(handComputedData.history!);
        expect(ci1).not.toBeNull();
        expect(ci2).not.toBeNull();
        // Fully deterministic across identical runs
        expect(ci1).toEqual(ci2);
        expect(ci1![0]).toBeLessThanOrEqual(ci1![1]);
    });

    it('returns null confidence interval on single or empty history', () => {
        expect(computeBootstrapRoiCi([])).toBeNull();
        expect(computeBootstrapRoiCi([handComputedData.history![0]])).toBeNull();
    });

    it('aggregates daily into weekly and monthly periods', () => {
        const fin = computeFinancials(handComputedData);
        expect(fin.daily_periods).toHaveLength(5);
        expect(fin.monthly_periods).toHaveLength(1);
        expect(fin.monthly_periods[0].period).toBe('2026-09');
        expect(fin.monthly_periods[0].net_profit).toBe(15.0);
        expect(fin.monthly_periods[0].turnover).toBe(50.0);
    });
});
