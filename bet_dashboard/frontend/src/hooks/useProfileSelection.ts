import { useState, useEffect } from 'react';

// Storage keys for different pages
const ANALYTICS_PROFILES_STORAGE_KEY = 'analytics_profile_selector_state';
const SLIPS_PROFILES_STORAGE_KEY = 'slips_profile_selector_state';

interface UseProfileSelectionProps {
  page: 'analytics' | 'slips';
  allProfiles: string[];
}

export function useProfileSelection({ page }: UseProfileSelectionProps) {
  // Determine which storage key to use based on the page
  const storageKey = page === 'analytics'
    ? ANALYTICS_PROFILES_STORAGE_KEY
    : SLIPS_PROFILES_STORAGE_KEY;

  // Initialize selectedProfiles from page-specific storage
  const [selectedProfiles, setSelectedProfiles] = useState<string[]>(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.profiles && Array.isArray(parsed.profiles)) {
          return parsed.profiles;
        }
      } catch (e) {
        // Invalid localStorage, use default
      }
    }
    // Default to all profiles selected
    return [];
  });

  // Persist profiles to page-specific storage
  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify({ profiles: selectedProfiles }));
  }, [selectedProfiles, storageKey]);

  return { selectedProfiles, setSelectedProfiles };
}