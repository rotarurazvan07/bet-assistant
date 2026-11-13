import type { AnalyticsData } from '../types';

export interface StrategyMetrics {
    // 1. Headline Edge
    edge: number;
    win_rate: number;
    implied_win_rate: number;
    sample_size: number;
    is_low_sample: boolean;

    // 2. Edge Reliability & Luck vs Skill
    expected_wins: number;
    actual_wins: number;
    variance_z: number | null;
    variance_verdict: string;

    // 3. Edge Persistence
    edge_trend: string;
    recent_edge_value: number;
    rolling_edge_series: {
        date: string;
        rolling_edge: number;
        rolling_win_rate: number;
        rolling_implied: number;
        sample_size: number;
    }[];

    // 5. Execution Discipline
    avg_units: number;
    kelly_suggested_units: number;
    kelly_ratio: number | null;
    is_aggressive: boolean;
    units_std: number | null;
    avg_odds: number;

    // 6. Aggregate Input Quality
    aggregate_sources: {
        total_sources: number;
        total_predictions: number;
        correct_predictions: number;
        accuracy: number | null;
        score_mae: number | null;
    } | null;
}

/**
 * Computes Strategy metrics judging decision quality across the filtered portfolio.
 * Pure function: no I/O, deterministic output.
 */
export function computeStrategy(data: Partial<AnalyticsData> | null | undefined): StrategyMetrics {
    const stats = data?.stats;
    const sampleSize = stats?.total_settled ?? 0;
    const isLowSample = sampleSize < 10;

    const actualWinRate = stats?.win_rate ?? 0;
    const impliedWinRate = stats?.implied_win_rate ?? 0;
    const edge = stats?.edge ?? Math.round((actualWinRate - impliedWinRate) * 10) / 10;

    // 2. Reliability / Luck vs Skill (Binomial Variance)
    const actualWins = stats?.total_won_count ?? 0;
    const p = impliedWinRate / 100;
    const expectedWins = Math.round(sampleSize * p * 10) / 10;

    let varianceZ: number | null = null;
    let varianceVerdict = 'Insufficient Data';

    if (sampleSize >= 10 && p > 0 && p < 1) {
        const variance = sampleSize * p * (1 - p);
        if (variance > 0) {
            const std = Math.sqrt(variance);
            varianceZ = Math.round(((actualWins - (sampleSize * p)) / std) * 100) / 100;
            if (varianceZ >= 1.96) {
                varianceVerdict = 'Statistical Edge (p < 0.05)';
            } else if (varianceZ <= -1.96) {
                varianceVerdict = 'Significant Drag (p < 0.05)';
            } else {
                varianceVerdict = 'Within Normal Variance';
            }
        }
    } else if (sampleSize > 0) {
        varianceVerdict = 'Small Sample (< 10 bets)';
    }

    // 3. Persistence & Trend
    const edgeTrend = stats?.edge_trend ?? 'neutral';
    const recentEdgeValue = stats?.recent_edge_value ?? 0;
    const rollingEdgeSeries = [...(data?.rolling_edge ?? [])];

    // 5. Execution Discipline
    const avgUnits = stats?.avg_units ?? 0;
    const kellySuggested = stats?.kelly_suggested_units ?? 0;
    const kellyRatio = avgUnits > 0 ? Math.round((kellySuggested / avgUnits) * 10) / 10 : null;
    const isAggressive = kellyRatio !== null && kellyRatio > 1.5;
    const unitsStd = stats?.units_std ?? null;
    const avgOdds = stats?.avg_odds ?? 0;

    // 6. Aggregate Input Quality
    const sources = data?.source_breakdown ?? [];
    let aggregateSources: StrategyMetrics['aggregate_sources'] = null;
    if (sources.length > 0) {
        const totalSources = sources.length;
        const totalPredictions = sources.reduce((sum, s) => sum + s.total_predictions, 0);
        const correctPredictions = sources.reduce((sum, s) => sum + s.correct_predictions, 0);
        const accuracy = totalPredictions > 0
            ? Math.round((correctPredictions / totalPredictions) * 1000) / 10
            : null;

        // Weighted MAE by predictions
        let weightedMaeSum = 0;
        let maeWeight = 0;
        for (const s of sources) {
            if (s.total_predictions > 0) {
                weightedMaeSum += s.score_mae * s.total_predictions;
                maeWeight += s.total_predictions;
            }
        }
        const scoreMae = maeWeight > 0 ? Math.round((weightedMaeSum / maeWeight) * 100) / 100 : null;

        aggregateSources = {
            total_sources: totalSources,
            total_predictions: totalPredictions,
            correct_predictions: correctPredictions,
            accuracy,
            score_mae: scoreMae,
        };
    }

    return {
        edge,
        win_rate: actualWinRate,
        implied_win_rate: impliedWinRate,
        sample_size: sampleSize,
        is_low_sample: isLowSample,
        expected_wins: expectedWins,
        actual_wins: actualWins,
        variance_z: varianceZ,
        variance_verdict: varianceVerdict,
        edge_trend: edgeTrend,
        recent_edge_value: recentEdgeValue,
        rolling_edge_series: rollingEdgeSeries,
        avg_units: avgUnits,
        kelly_suggested_units: kellySuggested,
        kelly_ratio: kellyRatio,
        is_aggressive: isAggressive,
        units_std: unitsStd,
        avg_odds: avgOdds,
        aggregate_sources: aggregateSources,
    };
}
