import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { useSocket } from './hooks/useSocket';
import { fetchStatus } from './api/data';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import BettingTips from './pages/BettingTips';
import SmartBuilder from './pages/SmartBuilder';
import Slips from './pages/Slips';
import Analytics from './pages/Analytics';
import Services from './pages/Services';
import OddsAlert from './pages/OddsAlert';
import type { ValidationCompletion, ValidationProgress } from './types';

export default function App() {
    const [lastPull, setLastPull] = useState('');
    // Increment to signal a component it should refetch
    const [matchesRefresh, setMatchesRefresh] = useState(0);
    const [slipsRefresh, setSlipsRefresh] = useState(0);
    // Live data from WebSocket validation
    const [liveData, setLiveData] = useState<Record<string, { score: string; minute: string }>>({});
    const [validationProgress, setValidationProgress] = useState<ValidationProgress | null>(null);
    const [validationCompletion, setValidationCompletion] = useState<ValidationCompletion | null>(null);

    // One-time status load — empty-deps effect runs exactly once on mount
    // (replaces the render-time ref write flagged by react-hooks/refs)
    useEffect(() => {
        fetchStatus().then((s: { last_pull: string }) => setLastPull(s.last_pull)).catch(() => { });
    }, []);

    // WebSocket: targeted refetch on named events only
    useSocket({
        matches_updated: useCallback((ev) => {
            if (ev.timestamp) setLastPull(ev.timestamp);
            setMatchesRefresh(n => n + 1);
        }, []),
        slips_updated: useCallback((ev) => {
            setSlipsRefresh(n => n + 1);
            // Update live data from the WebSocket event
            if (ev.live_data && typeof ev.live_data === 'object') {
                setLiveData(ev.live_data as Record<string, { score: string; minute: string }>);
            }
        }, []),
        validation_progress: useCallback((ev) => {
            if (
                ev.job_id
                && typeof ev.checked === 'number'
                && typeof ev.total === 'number'
                && typeof ev.current_match === 'string'
            ) {
                setValidationProgress({
                    job_id: ev.job_id,
                    checked: ev.checked,
                    total: ev.total,
                    current_match: ev.current_match,
                });
            }
        }, []),
        validation_completed: useCallback((ev) => {
            if (!ev.job_id) return;
            setValidationProgress(current => current?.job_id === ev.job_id ? null : current);
            setValidationCompletion({
                job_id: ev.job_id,
                checked: ev.checked,
                settled: ev.settled,
                live: ev.live,
                errors: ev.errors,
                cancelled: ev.cancelled,
                failed: ev.failed,
            });
        }, []),
        service_toggled: useCallback(() => {
            // Services component doesn't need refresh as it auto-refreshes on toggle
        }, []),
    });

    function handleRefresh() {
        setMatchesRefresh(n => n + 1);
        setSlipsRefresh(n => n + 1);
    }

    function handleMatchesUpdated() {
        setMatchesRefresh(n => n + 1);
    }

    return (
        <BrowserRouter>
            <Layout
                lastPull={lastPull ? `Updated: ${lastPull}` : ''}
                onRefresh={handleRefresh}
                onMatchesUpdated={handleMatchesUpdated}
            >
                {(filters) => (
                    <ErrorBoundary>
                        <Routes>
                            <Route path="/"
                                element={<BettingTips filters={filters} refreshKey={matchesRefresh} />} />
                            <Route path="/builder"
                                element={<SmartBuilder filters={filters} refreshKey={matchesRefresh} />} />
                            <Route path="/slips"
                                element={<Slips
                                    filters={filters}
                                    refreshKey={slipsRefresh}
                                    liveData={liveData}
                                    validationProgress={validationProgress ?? undefined}
                                    validationCompletion={validationCompletion ?? undefined}
                                />} />
                            <Route path="/analytics"
                                element={<Analytics filters={filters} refreshKey={slipsRefresh} />} />
                            <Route path="/services"
                                element={<Services />} />
                            <Route path="/odds-alert"
                                element={<OddsAlert />} />
                        </Routes>
                    </ErrorBoundary>
                )}
            </Layout>
        </BrowserRouter>
    );
}
