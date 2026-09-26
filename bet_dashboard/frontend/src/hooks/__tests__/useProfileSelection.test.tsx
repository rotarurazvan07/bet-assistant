// useProfileSelection tests (issue #66). SPEC DIVERGENCES (pinned):
// - NO 'manual' reset and NO profile-config loading — the hook only manages
//   a selectedProfiles string[] + setter (config lives in App/pages)
// - NO delete handling — nothing to clear on profile deletion
// - Real behaviors: per-page localStorage keys, lazy initial load with
//   {profiles: [...]} shape validation, invalid-JSON fallback to [],
//   persistence effect on every change. NOTE: code comment says 'default
//   to all profiles selected' but returns [] — pinned as-is (comment bug,
//   not behavior bug; documented, not fixed).

import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useProfileSelection } from '../useProfileSelection';


beforeEach(() => {
    localStorage.clear();
});


describe('useProfileSelection', () => {
    it('defaults to empty selection with no stored state', () => {
        const { result } = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: ['low', 'medium'] }));
        expect(result.current.selectedProfiles).toEqual([]);
    });

    it('loads saved profiles from page-specific storage key', () => {
        localStorage.setItem('analytics_profile_selector_state', JSON.stringify({ profiles: ['low', 'high_risk'] }));
        const { result } = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: ['low', 'high_risk', 'medium'] }));
        expect(result.current.selectedProfiles).toEqual(['low', 'high_risk']);
    });

    it('uses separate storage keys per page (slips vs analytics)', () => {
        localStorage.setItem('analytics_profile_selector_state', JSON.stringify({ profiles: ['low'] }));
        localStorage.setItem('slips_profile_selector_state', JSON.stringify({ profiles: ['medium', 'high_risk'] }));
        const analytics = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: [] }));
        const slips = renderHook(() => useProfileSelection({ page: 'slips', allProfiles: [] }));
        expect(analytics.result.current.selectedProfiles).toEqual(['low']);
        expect(slips.result.current.selectedProfiles).toEqual(['medium', 'high_risk']);
    });

    it('falls back to empty selection on invalid JSON in storage', () => {
        localStorage.setItem('analytics_profile_selector_state', 'not-json{');
        const { result } = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: [] }));
        expect(result.current.selectedProfiles).toEqual([]);
    });

    it('falls back to empty selection when stored shape lacks profiles array', () => {
        localStorage.setItem('analytics_profile_selector_state', JSON.stringify({ wrong: 'shape' }));
        const { result } = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: [] }));
        expect(result.current.selectedProfiles).toEqual([]);
    });

    it('persists selection changes to the page-specific key', () => {
        const { result } = renderHook(() => useProfileSelection({ page: 'slips', allProfiles: ['low', 'medium'] }));
        act(() => {
            result.current.setSelectedProfiles(['medium']);
        });
        const saved = localStorage.getItem('slips_profile_selector_state');
        expect(saved).not.toBeNull();
        expect(JSON.parse(saved as string)).toEqual({ profiles: ['medium'] });
    });

    it('setter supports functional updates', () => {
        const { result } = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: ['a', 'b', 'c'] }));
        act(() => {
            result.current.setSelectedProfiles(['a']);
        });
        act(() => {
            result.current.setSelectedProfiles((prev) => [...prev, 'b']);
        });
        expect(result.current.selectedProfiles).toEqual(['a', 'b']);
        expect(JSON.parse(localStorage.getItem('analytics_profile_selector_state') as string)).toEqual({ profiles: ['a', 'b'] });
    });

    it('does not leak state across pages when changing selection on one page only', () => {
        localStorage.setItem('slips_profile_selector_state', JSON.stringify({ profiles: ['low'] }));
        const analytics = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: ['low'] }));
        act(() => {
            analytics.result.current.setSelectedProfiles(['low', 'medium']);
        });
        const slips = renderHook(() => useProfileSelection({ page: 'slips', allProfiles: ['low', 'medium'] }));
        expect(slips.result.current.selectedProfiles).toEqual(['low']); // slips storage untouched
    });

    it('allProfiles prop is accepted (signature pin) but does not drive default selection', () => {
        const { result } = renderHook(() => useProfileSelection({ page: 'analytics', allProfiles: ['low', 'medium', 'high_risk'] }));
        expect(result.current.selectedProfiles).toEqual([]); // NOT defaulted to allProfiles despite comment
    });
});
