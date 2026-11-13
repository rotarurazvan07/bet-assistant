import { describe, it, expect } from 'vitest';
import { computeStrategy } from '../analyticsStrategy';
import type { AnalyticsData } from '../../types';

describe('computeStrategy', () => {
    it('computes edge and actual-vs-implied win rate pairs', () => {
        const data: Partial<AnalyticsData> = {
            stats: {
                total_settled: 40,
                total_won_count: 24,
                win_rate: 60.0,
                implied_win_rate: 52.0,
                edge: 8.0,
                total_units_bet: 40,
                gross_return: 48,
                net_profit: 8,
                roi_percentage: 20,
                avg_odds: 1.92,
                avg_units: 1.0,
                units_std: 0.1,
                pending_count: 0,
                sharpe_ratio: 1.2,
                profit_factor: 1.5,
                biggest_win_units: 2,
                biggest_loss_units: -1,
                best_day_pnl: 3,
                worst_day_pnl: -2,
                current_streak: 1,
                longest_win_streak: 4,
                longest_loss_streak: 2,
                kelly_suggested_units: 1.2,
                edge_trend: 'growing',
                recent_edge_value: 10.2,
            },
        };

        const res = computeStrategy(data);
        expect(res.edge).toBe(8.0);
        expect(res.win_rate).toBe(60.0);
        expect(res.implied_win_rate).toBe(52.0);
        expect(res.sample_size).toBe(40);
        expect(res.is_low_sample).toBe(false);
    });

    it('flags low sample warning when settled bets < 10', () => {
        const data: Partial<AnalyticsData> = {
            stats: {
                total_settled: 8,
                total_won_count: 5,
                win_rate: 62.5,
                implied_win_rate: 50.0,
                edge: 12.5,
                total_units_bet: 8,
                gross_return: 10,
                net_profit: 2,
                roi_percentage: 25,
                avg_odds: 2.0,
                avg_units: 1.0,
                units_std: 0.0,
                pending_count: 0,
                sharpe_ratio: 0.8,
                profit_factor: 1.3,
                biggest_win_units: 1,
                biggest_loss_units: -1,
                best_day_pnl: 1,
                worst_day_pnl: -1,
                current_streak: 1,
                longest_win_streak: 2,
                longest_loss_streak: 1,
                kelly_suggested_units: 1.0,
                edge_trend: 'neutral',
                recent_edge_value: 0,
            },
        };

        const res = computeStrategy(data);
        expect(res.is_low_sample).toBe(true);
        expect(res.variance_verdict).toContain('Small Sample');
    });

    it('computes luck vs skill binomial variance z-score on sufficient sample', () => {
        // 100 bets, implied 50% (expected 50 wins), actual 65 wins
        // std = sqrt(100 * 0.5 * 0.5) = 5
        // z = (65 - 50) / 5 = 3.0 (Statistical edge, p < 0.05)
        const data: Partial<AnalyticsData> = {
            stats: {
                total_settled: 100,
                total_won_count: 65,
                win_rate: 65.0,
                implied_win_rate: 50.0,
                edge: 15.0,
                total_units_bet: 100,
                gross_return: 130,
                net_profit: 30,
                roi_percentage: 30,
                avg_odds: 2.0,
                avg_units: 1.0,
                units_std: 0.0,
                pending_count: 0,
                sharpe_ratio: 2.0,
                profit_factor: 2.0,
                biggest_win_units: 1,
                biggest_loss_units: -1,
                best_day_pnl: 5,
                worst_day_pnl: -3,
                current_streak: 3,
                longest_win_streak: 6,
                longest_loss_streak: 2,
                kelly_suggested_units: 1.5,
                edge_trend: 'growing',
                recent_edge_value: 14.0,
            },
        };

        const res = computeStrategy(data);
        expect(res.expected_wins).toBe(50.0);
        expect(res.actual_wins).toBe(65);
        expect(res.variance_z).toBe(3.0);
        expect(res.variance_verdict).toBe('Statistical Edge (p < 0.05)');
    });

    it('computes aggregate source accuracy and score MAE', () => {
        const data: Partial<AnalyticsData> = {
            stats: {
                total_settled: 20,
                total_won_count: 10,
                win_rate: 50,
                implied_win_rate: 50,
                edge: 0,
                total_units_bet: 20,
                gross_return: 20,
                net_profit: 0,
                roi_percentage: 0,
                avg_odds: 2.0,
                avg_units: 1.0,
                units_std: 0,
                pending_count: 0,
                sharpe_ratio: null,
                profit_factor: 1.0,
                biggest_win_units: 1,
                biggest_loss_units: -1,
                best_day_pnl: 1,
                worst_day_pnl: -1,
                current_streak: 0,
                longest_win_streak: 1,
                longest_loss_streak: 1,
                kelly_suggested_units: 1.0,
                edge_trend: 'neutral',
                recent_edge_value: 0,
            },
            source_breakdown: [
                {
                    source: 'SrcA',
                    total_predictions: 10,
                    correct_predictions: 7,
                    accuracy: 70.0,
                    score_mae: 1.0,
                    markets: [],
                },
                {
                    source: 'SrcB',
                    total_predictions: 10,
                    correct_predictions: 5,
                    accuracy: 50.0,
                    score_mae: 1.4,
                    markets: [],
                },
            ],
        };

        const res = computeStrategy(data);
        expect(res.aggregate_sources).not.toBeNull();
        expect(res.aggregate_sources!.total_sources).toBe(2);
        expect(res.aggregate_sources!.total_predictions).toBe(20);
        expect(res.aggregate_sources!.correct_predictions).toBe(12);
        // (12 / 20) * 100 = 60.0%
        expect(res.aggregate_sources!.accuracy).toBe(60.0);
        // Weighted MAE: (10*1.0 + 10*1.4) / 20 = 1.20
        expect(res.aggregate_sources!.score_mae).toBe(1.2);
    });
});
