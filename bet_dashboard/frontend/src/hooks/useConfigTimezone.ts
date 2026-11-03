/**
 * Timezone configuration hook and utilities
 *
 * Backend match datetimes are naive wall-clock strings expressed in the
 * configured match-data timezone (scraper_config.local_timezone).
 * These helpers ensure the browser renders/compares them in that same tz.
 */

import { useEffect, useState } from 'react';
import client from '../api/client';
import { naiveToInstant } from '../utils/betUtils';

let cachedTimezone: string | null = null;
let loadingPromise: Promise<string> | null = null;

/**
 * Load the configured match-data timezone from the backend.
 * Caches the result so multiple callers share one request.
 */
export async function loadConfigTimezone(): Promise<string> {
  if (cachedTimezone) return cachedTimezone;
  if (loadingPromise) return loadingPromise;

  loadingPromise = (async () => {
    const res = await client.get<{ timezone: string }>('/config/timezone');
    cachedTimezone = res.data.timezone;
    return cachedTimezone;
  })();

  return loadingPromise;
}

/**
 * React hook that provides the configured timezone.
 * Returns the cached value immediately if available, otherwise loads it.
 * The timezone is null until the first load resolves; callers should treat
 * null as 'use the naive wall clock as-is' (see formatMatchTime).
 */
export function useConfigTimezone() {
  const [timezone, setTimezone] = useState<string | null>(cachedTimezone);
  const [loading, setLoading] = useState(!cachedTimezone);

  useEffect(() => {
    if (cachedTimezone) return;
    setLoading(true);
    loadConfigTimezone()
      .then(setTimezone)
      .catch(() => setTimezone(null))
      .finally(() => setLoading(false));
  }, []);

  return { timezone, loading };
}

// Re-export the shared, browser-independent formatters so call sites only
// ever import datetime helpers from one place.
export { formatMatchTime, naiveToInstant } from '../utils/betUtils';

/**
 * Format a naive ISO datetime string for the upcoming-match display.
 * Shows 'Next match in Xh' or 'Next match in Ym' relative to now in the config timezone.
 *
 * @param iso - Naive ISO datetime from backend
 * @param timezone - IANA timezone identifier the naive value is expressed in
 * @param nowMs - Optional injected 'now' for deterministic testing (defaults to Date.now())
 * @returns Human-readable time-to-match string, or 'live' if already past
 */
export function formatTimeToMatch(
  iso: string | null | undefined,
  timezone: string,
  nowMs: number = Date.now()
): string {
  if (!iso) return 'no upcoming';

  const matchInstant = naiveToInstant(iso, timezone);
  if (Number.isNaN(matchInstant)) return 'no upcoming';

  const msUntil = matchInstant - nowMs;
  if (msUntil <= 0) return 'live';

  const hours = Math.floor(msUntil / (1000 * 60 * 60));
  if (hours >= 1) return `Next match in ${hours}h`;

  const mins = Math.round(msUntil / (1000 * 60));
  return `Next match in ${mins}m`;
}
