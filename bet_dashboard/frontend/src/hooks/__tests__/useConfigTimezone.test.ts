import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useConfigTimezone, formatMatchTime, formatTimeToMatch, naiveToInstant } from '../useConfigTimezone';

vi.mock('../../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { timezone: 'UTC' } }) },
}));

import client from '../../api/client';

describe('useConfigTimezone', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exposes cached timezone and loading state', async () => {
    const { result } = renderHook(() => useConfigTimezone());
    expect(result.current.timezone).toBeNull();
    expect(result.current.loading).toBe(true);
  });
});

describe('formatMatchTime', () => {
  it('formats a naive ISO string in the given timezone', () => {
    const formatted = formatMatchTime('2026-01-15T20:30:00', 'UTC');
    expect(formatted).toContain('15');
    expect(formatted).toContain('Jan');
  });

  it('renders the naive wall clock in the configured timezone, not the browser zone', () => {
    // The same naive string is 20:30 wall clock in whichever zone is configured,
    // so the rendered wall clock must not shift with the configured zone.
    const utc = formatMatchTime('2026-01-15T20:30:00', 'UTC');
    const bangkok = formatMatchTime('2026-01-15T20:30:00', 'Asia/Bangkok');
    expect(utc).toBe(bangkok);
    expect(utc).toContain('20:30');

    // ...while the underlying instants differ by the zone offset.
    expect(naiveToInstant('2026-01-15T20:30:00', 'UTC')).not.toBe(
      naiveToInstant('2026-01-15T20:30:00', 'Asia/Bangkok'),
    );
  });

  it('renders a UTC-timestamp input in the configured timezone', () => {
    // An instant-bearing string must be converted into the configured wall clock.
    expect(formatMatchTime('2026-01-15T20:30:00Z', 'Asia/Bangkok')).toContain('03:30');
  });

  it('returns an empty string for missing input', () => {
    expect(formatMatchTime(null, 'UTC')).toBe('');
    expect(formatMatchTime(undefined, 'UTC')).toBe('');
  });
});

describe('naiveToInstant', () => {
  it('converts naive ISO to instant in given timezone', () => {
    const iso = '2026-01-15T20:30:00';
    const utcInstant = naiveToInstant(iso, 'UTC');
    const bangkokInstant = naiveToInstant(iso, 'Asia/Bangkok');
    expect(utcInstant).not.toBe(bangkokInstant);
    expect(bangkokInstant).toBeLessThan(utcInstant); // Bangkok is ahead
  });

  it('returns NaN for missing input', () => {
    expect(naiveToInstant(null, 'UTC')).toBeNaN();
    expect(naiveToInstant(undefined, 'UTC')).toBeNaN();
  });
});

describe('formatTimeToMatch', () => {
  const FIXED_NOW = new Date('2026-01-15T12:00:00Z').getTime(); // 12:00 UTC

  it('reports hours for a future match', () => {
    // 2 hours in the future: 14:00 UTC → 2h
    const future = new Date(FIXED_NOW + 2 * 60 * 60 * 1000).toISOString();
    expect(formatTimeToMatch(future, 'UTC', FIXED_NOW)).toBe('Next match in 2h');
  });

  it('reports minutes under an hour', () => {
    // 30 minutes in the future
    const future = new Date(FIXED_NOW + 30 * 60 * 1000).toISOString();
    expect(formatTimeToMatch(future, 'UTC', FIXED_NOW)).toBe('Next match in 30m');
  });

  it('reports live for a past match', () => {
    // 1 hour in the past
    const past = new Date(FIXED_NOW - 60 * 60 * 1000).toISOString();
    expect(formatTimeToMatch(past, 'UTC', FIXED_NOW)).toBe('live');
  });

  it('returns no upcoming for missing input', () => {
    expect(formatTimeToMatch(null, 'UTC', FIXED_NOW)).toBe('no upcoming');
  });
});
