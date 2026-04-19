import { useCallback, useEffect, useState } from 'react';
import { fetchServices, saveServiceSettings, toggleService } from '../api/data';
import ServiceCard from '../components/ServiceCard';
import { TooltipIcon } from '../components/ui';
import type { ServicesData } from '../types';

const HOURS = Array.from({ length: 24 }, (_, i) => i);

export default function Services() {
    const [data, setData] = useState<ServicesData | null>(null);
    const [pullHour, setPullHour] = useState(6);
    const [genHour, setGenHour] = useState(8);
    const [status, setStatus] = useState('');

    const load = useCallback(async () => {
        const d = await fetchServices();
        setData(d);
        setPullHour(d.pull_hour);
        setGenHour(d.generate_hour);
    }, []);

    useEffect(() => { load(); }, [load]);

    async function handleSave() {
        await saveServiceSettings(pullHour, genHour);
        setStatus('✓ Settings saved — schedules recalculated');
        load();
    }

    async function handleToggle(name: string) {
        await toggleService(name);
        await load();
    }

    if (!data) return (
        <div>
            <div className="flex items-baseline justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Automation Services
                </h1>
            </div>
            <div className="card text-center py-16">
                <p className="font-mono text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Loading services…
                </p>
            </div>
        </div>
    );

    const now = data.server_time ? new Date(data.server_time) : new Date();

    return (
        <div>
            <div className="flex items-baseline justify-between mb-5">
                <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text-bright)' }}>
                    Automation Services
                </h1>
                <span className="font-mono text-[11px]" style={{ color: 'var(--text-secondary)' }}>
                    Server time: {now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

                {/* Service cards */}
                {Object.values(data.services ?? {}).map(svc => (
                    <ServiceCard
                        key={svc.name}
                        info={svc}
                        onToggle={() => handleToggle(svc.name)}
                    />
                ))}

                {/* Scheduler settings */}
                <div className="card p-4 lg:col-span-3">
                    <p className="font-mono text-[10px] tracking-widest uppercase mb-4"
                        style={{ color: 'var(--text-secondary)' }}>Scheduled Hours</p>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">

                        {/* Pull DB hour */}
                        <div>
                            <div className="flex items-center gap-1.5 mb-3">
                                <span className="font-sans text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                                    Pull DB
                                    <TooltipIcon text="Fetches match data and predictions from external sources. Runs daily at the scheduled hour." align="right" />
                                </span>
                                <span className="font-mono text-[10px] px-1.5 py-0.5 rounded"
                                    style={{ background: 'var(--accent)', color: '#fff', opacity: .8 }}>
                                    daily at {String(pullHour).padStart(2, '0')}:00
                                </span>
                            </div>
                            <div className="grid grid-cols-6 gap-1">
                                {HOURS.map(h => (
                                    <button key={h}
                                        onClick={() => setPullHour(h)}
                                        className="h-8 rounded text-[11px] font-mono transition-all duration-100"
                                        style={{
                                            background: h === pullHour ? 'var(--accent)' : 'var(--bg-raised)',
                                            border: `1px solid ${h === pullHour ? 'var(--accent)' : 'var(--border)'}`,
                                            color: h === pullHour ? '#fff' : 'var(--text-secondary)',
                                            transform: h === pullHour ? 'scale(1.05)' : 'scale(1)',
                                        }}>
                                        {String(h).padStart(2, '0')}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Generate Slips hour */}
                        <div>
                            <div className="flex items-center gap-1.5 mb-3">
                                <span className="font-sans text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                                    Generate Slips
                                    <TooltipIcon text="Creates betting slips based on builder configurations and predictions. Runs daily at the scheduled hour." align="right" />
                                </span>
                                <span className="font-mono text-[10px] px-1.5 py-0.5 rounded"
                                    style={{ background: 'var(--purple)', color: '#fff', opacity: .8 }}>
                                    daily at {String(genHour).padStart(2, '0')}:00
                                </span>
                            </div>
                            <div className="grid grid-cols-6 gap-1">
                                {HOURS.map(h => (
                                    <button key={h}
                                        onClick={() => setGenHour(h)}
                                        className="h-8 rounded text-[11px] font-mono transition-all duration-100"
                                        style={{
                                            background: h === genHour ? 'var(--purple)' : 'var(--bg-raised)',
                                            border: `1px solid ${h === genHour ? 'var(--purple)' : 'var(--border)'}`,
                                            color: h === genHour ? '#fff' : 'var(--text-secondary)',
                                            transform: h === genHour ? 'scale(1.05)' : 'scale(1)',
                                        }}>
                                        {String(h).padStart(2, '0')}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                        <button className="btn-primary" onClick={handleSave}>Save Settings</button>
                        {status && (
                            <span className="text-[11px] font-mono" style={{ color: 'var(--win)' }}>{status}</span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
