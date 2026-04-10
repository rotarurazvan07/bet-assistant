import { useCallback, useRef, useState } from 'react';
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

export default function App() {
    const [lastPull, setLastPull] = useState('');
    // Increment to signal a component it should refetch
    const [matchesRefresh, setMatchesRefresh] = useState(0);
    const [slipsRefresh, setSlipsRefresh] = useState(0);
    // Live data from WebSocket validation
    const [liveData, setLiveData] = useState<Record<string, { score: string; minute: string }>>({});

    // One-time status load
    const statusLoaded = useRef(false);
    if (!statusLoaded.current) {
        statusLoaded.current = true;
        fetchStatus().then(s => setLastPull(s.last_pull)).catch(() => { });
    }

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
                                element={<Slips filters={filters} refreshKey={slipsRefresh} liveData={liveData} />} />
                            <Route path="/analytics"
                                element={<Analytics filters={filters} refreshKey={slipsRefresh} />} />
                            <Route path="/services"
                                element={<Services />} />
                        </Routes>
                    </ErrorBoundary>
                )}
            </Layout>
        </BrowserRouter>
    );
}
