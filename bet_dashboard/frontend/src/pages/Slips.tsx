import { useEffect, useState, useCallback } from 'react';
import { fetchSlips, deleteSlip, validateSlips, generateSlips } from '../api/data';
import { SlipCard } from '../components/BetComponents';
import { StatCard, Toggle } from '../components/ui';
import type { GlobalFilters } from '../components/Layout';
import type { SlipsPage, LiveData } from '../types';

const STORAGE_KEY = 'slips_state';

interface Props { filters: GlobalFilters; refreshKey: number; liveData?: LiveData }

export default function Slips({ filters, refreshKey, liveData: externalLiveData }: Props) {
    const [data, setData] = useState<SlipsPage | null>(null);
    const [profileFilter, setProfileFilter] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).profileFilter : 'all';
    });
    const [hideSettled, setHideSettled] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).hideSettled : false;
    });
    const [liveOnly, setLiveOnly] = useState(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved ? JSON.parse(saved).liveOnly : false;
    });
    // Use external liveData from WebSocket if provided, otherwise use local state
    const [localLiveData, setLocalLiveData] = useState<LiveData>({});
    const liveData = externalLiveData ?? localLiveData;
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState('');

    // Persist state to localStorage
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ profileFilter, hideSettled, liveOnly }));
    }, [profileFilter, hideSettled, liveOnly]);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const d = await fetchSlips({
                profile: profileFilter === 'all' ? undefined : profileFilter,
                date_from: filters.dateFrom || undefined,
                date_to: filters.dateTo || undefined,
                hide_settled: hideSettled,
                live_only: liveOnly,
            });
            setData(d);
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
            setLocalLiveData(ld);
        } catch {
            // Set empty state on error
            setData({ slips: [], stats: { total_settled: 0, total_won_count: 0, win_rate: 0, total_units_bet: 0, gross_return: 0, net_profit: 0, roi_percentage: 0 }, profiles: [] });
        } finally { setLoading(false); }
    }, [profileFilter, filters, hideSettled, liveOnly, refreshKey]);

    useEffect(() => { load(); }, [load]);

    // Update live data when WebSocket pushes new live_data
    useEffect(() => {
        if (externalLiveData && Object.keys(externalLiveData).length > 0) {
            setLocalLiveData(externalLiveData);
        }
    }, [externalLiveData]);

    async function handleValidate() {
        setStatus('Validating…');
        const result = await validateSlips();
        const ld: LiveData = {};
        result.live_data.forEach(item => {
            ld[item.match_name] = { score: item.score, minute: item.minute };
        });
        setLocalLiveData(ld);
        setStatus(`✓ Checked ${result.checked} · Settled ${result.settled} · Live ${result.live}`);
        load();
    }

    async function handleGenerate() {
        setStatus('Generating…');
        const result = await generateSlips();
        setStatus(`✓ Generated ${result.generated} slip(s)`);
        load();
    }

    async function handleDelete(id: number) {
        await deleteSlip(id);
        load();
    }

    const stats = data?.stats;

    return (
        <div>
            <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Slips
                </h1>
                <div className="flex items-center gap-3 flex-wrap">
                    {/* Profile filter */}
                    <select className="field w-44"
                        value={profileFilter}
                        onChange={e => setProfileFilter(e.target.value)}>
                        <option value="all">All Profiles</option>
                        {data?.profiles?.map(p => (
                            <option key={p} value={p}>{p.toUpperCase()}</option>
                        ))}
                    </select>

                    <button className="btn-ghost" onClick={handleValidate}>✓ Validate Results</button>
                    <button className="btn-success" onClick={handleGenerate}>✦ Generate Slips</button>

                    <Toggle checked={hideSettled} onChange={setHideSettled} label="Hide settled" />
                    <Toggle checked={liveOnly} onChange={setLiveOnly} label="Live only" />

                    {status && (
                        <span className="text-[11px] font-mono" style={{ color: 'var(--accent)' }}>{status}</span>
                    )}
                </div>
            </div>

            {/* Empty state */}
            {!loading && data && (!data.slips || data.slips.length === 0) && (
                <div className="card text-center py-16 fade-in">
                    <p className="font-mono text-sm" style={{ color: 'var(--text-muted)' }}>
                        No slips available.
                    </p>
                    <p className="font-mono text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                        Click "✦ Generate Slips" to create betting slips from your profiles.
                    </p>
                </div>
            )}

            {/* Stats row */}
            {stats && (
                <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
                    <StatCard label="Total Bet" value={`${stats.total_units_bet} U`} accent />
                    <StatCard label="Gross Return" value={`${stats.gross_return} U`} positive={stats.gross_return > 0} />
                    <StatCard label="Net Profit" value={`${stats.net_profit > 0 ? '+' : ''}${stats.net_profit} U`}
                        positive={stats.net_profit > 0} negative={stats.net_profit < 0} />
                    <StatCard label="Win Rate" value={`${stats.win_rate}%`} positive={stats.win_rate > 50} />
                    <StatCard label="ROI" value={`${stats.roi_percentage}%`}
                        positive={stats.roi_percentage > 0} negative={stats.roi_percentage < 0} />
                    <StatCard label="Settled" value={stats.total_settled} />
                </div>
            )}

            {/* Slips list */}
            {data && data.slips && data.slips.length > 0 && (
                <div style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .2s' }}>
                    {data.slips.map(slip => (
                        <SlipCard
                            key={slip.slip_id}
                            slip={slip}
                            liveData={liveData}
                            onDelete={handleDelete}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
