import { useCallback, useEffect, useState } from 'react';
import { fetchServices, saveServiceSettings, toggleService } from '../api/data';
import ServiceCard from '../components/ServiceCard';
import { TooltipIcon } from '../components/ui';
import type { ServicesData } from '../types';

import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { StaticTimePicker } from '@mui/x-date-pickers/StaticTimePicker';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import dayjs from 'dayjs';

// Custom theme mapping the high-fidelity CSS variable tokens
const muiDarkTheme = createTheme({
    palette: {
        mode: 'dark',
        background: {
            default: '#131C2E', // var(--bg-raised)
            paper: '#18243A',   // var(--bg-card)
        },
        primary: {
            main: '#7C3AED',    // var(--purple)
        },
        text: {
            primary: '#C9D6F0',   // var(--text-primary)
            secondary: '#b8c1d3', // var(--text-secondary)
        },
    },
    typography: {
        fontFamily: "'JetBrains Mono', 'Inter', monospace",
        fontSize: 12,
    },
    components: {
        MuiPickersLayout: {
            styleOverrides: {
                root: {
                    backgroundColor: '#131C2E',
                    color: '#C9D6F0',
                    border: '1px solid rgba(255, 255, 255, 0.07)',
                    borderRadius: '12px',
                    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
                    overflow: 'hidden',
                },
            },
        },
        MuiPickersToolbar: {
            styleOverrides: {
                root: {
                    backgroundColor: '#18243A',
                    borderRight: '1px solid rgba(255, 255, 255, 0.07)',
                    '& .MuiTypography-root': {
                        fontFamily: "'Outfit', sans-serif",
                    },
                },
            },
        },
        MuiClock: {
            styleOverrides: {
                root: {
                    backgroundColor: '#131C2E',
                },
            },
        },
        MuiClockPointer: {
            styleOverrides: {
                root: {
                    backgroundColor: '#7C3AED',
                },
                thumb: {
                    backgroundColor: '#7C3AED',
                    borderColor: '#7C3AED',
                },
            },
        },
        MuiClockNumber: {
            styleOverrides: {
                root: {
                    fontFamily: "'JetBrains Mono', monospace",
                    color: '#b8c1d3',
                    '&.Mui-selected': {
                        color: '#ffffff',
                    },
                },
            },
        },
        MuiClockAmPmSelectedCircle: {
            styleOverrides: {
                root: {
                    backgroundColor: '#7C3AED',
                },
            },
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
});

export default function Services() {
    const [data, setData] = useState<ServicesData | null>(null);
    const [genHour, setGenHour] = useState(8);
    const [genMinute, setGenMinute] = useState(0);
    const [status, setStatus] = useState('');

    const load = useCallback(async () => {
        const d = await fetchServices();
        setData(d);
        setGenHour(d.generate_hour);
        setGenMinute(d.generate_minute);
    }, []);

    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => { load(); }, [load]);

    async function handleSave() {
        await saveServiceSettings(genHour, genMinute);
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
                        style={{ color: 'var(--text-secondary)' }}>Scheduled Time</p>

                    <div className="grid grid-cols-1 gap-6 mb-4">

                        {/* Generate Slips hour */}
                        <div>
                            <div className="flex items-center gap-1.5 mb-4">
                                <span className="font-sans text-[12px]" style={{ color: 'var(--text-secondary)' }}>
                                    Generate Slips
                                    <TooltipIcon text="Creates betting slips based on builder configurations and predictions. Runs daily at the scheduled time." align="right" />
                                </span>
                            </div>

                            <div className="flex justify-center lg:justify-start">
                                <ThemeProvider theme={muiDarkTheme}>
                                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                                        <StaticTimePicker
                                            ampm={false}
                                            orientation="landscape"
                                            value={dayjs().hour(genHour).minute(genMinute).second(0)}
                                            onChange={(newValue) => {
                                                if (newValue) {
                                                    setGenHour(newValue.hour());
                                                    setGenMinute(newValue.minute());
                                                }
                                            }}
                                            slotProps={{
                                                actionBar: {
                                                    actions: []
                                                }
                                            }}
                                        />
                                    </LocalizationProvider>
                                </ThemeProvider>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-3 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
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
