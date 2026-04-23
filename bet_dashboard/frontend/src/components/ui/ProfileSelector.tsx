import { useEffect } from 'react';

interface ProfileSelectorProps {
    profiles: string[];
    selectedProfiles: string[];
    onChange: (value: string[]) => void;
    profileData: Record<string, any> | null; // Kept for compatibility but not used
}

export function ProfileSelector({ profiles, selectedProfiles, onChange }: ProfileSelectorProps) {
    // Sync selectedProfiles with profiles when profiles change and nothing is selected
    // This handles the case when data loads for the first time
    useEffect(() => {
        if (profiles.length > 0 && selectedProfiles.length === 0) {
            onChange([...profiles]);
        }
    }, [profiles, onChange, selectedProfiles.length]);

    const toggleProfile = (profile: string) => {
        if (selectedProfiles.includes(profile)) {
            // Prevent deselecting if it's the last selected profile
            if (selectedProfiles.length > 1) {
                onChange(selectedProfiles.filter(p => p !== profile));
            }
        } else {
            onChange([...selectedProfiles, profile]);
        }
    };

    const toggleAll = () => {
        const allSelected = profiles.length > 0 && profiles.every(p => selectedProfiles.includes(p));
        
        // Only allow selecting all if not already all selected
        if (!allSelected) {
            onChange([...profiles]);
        }
    };

    const allSelected = profiles.length > 0 && profiles.every(p => selectedProfiles.includes(p));
    
    return (
        <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
                <h3 className="font-mono text-[11px] tracking-widest uppercase" style={{ color: 'var(--text-secondary)' }}>
                    SELECT PROFILES
                </h3>
                <button
                    className="text-xs font-mono"
                    style={{
                        color: allSelected ? 'var(--text-secondary)' : 'var(--accent)',
                        cursor: allSelected ? 'not-allowed' : 'pointer',
                        opacity: allSelected ? 0.5 : 1
                    }}
                    onClick={toggleAll}
                    disabled={allSelected}
                >
                    SELECT ALL
                </button>
            </div>
            
            <div className="flex flex-wrap gap-2">
                {profiles.map(profile => (
                    <div
                        key={profile}
                        className="flex items-center gap-2 px-3 py-2 rounded border cursor-pointer transition-all"
                        style={{
                            background: selectedProfiles.includes(profile)
                                ? 'var(--accent)'
                                : 'var(--bg-card)',
                            borderColor: selectedProfiles.includes(profile)
                                ? 'var(--accent)'
                                : 'var(--border)',
                        }}
                        onClick={() => toggleProfile(profile)}
                    >
                        <div
                            className="w-4 h-4 rounded border flex items-center justify-center"
                            style={{
                                borderColor: selectedProfiles.includes(profile) ? 'white' : 'var(--border)',
                                background: selectedProfiles.includes(profile) ? 'white' : 'transparent',
                            }}
                        >
                            {selectedProfiles.includes(profile) && (
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{ color: 'var(--accent)' }}>
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                            )}
                        </div>
                        <span
                            className="text-sm"
                            style={{
                                color: selectedProfiles.includes(profile) ? 'white' : 'var(--text-bright)',
                            }}
                        >
                            {profile}
                        </span>
                    </div>
                ))}
                
                {profiles.length === 0 && (
                    <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                        No profiles available
                    </div>
                )}
            </div>
        </div>
    );
}