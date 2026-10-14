// tourStorage (Workstream B #47): tour-open flag + subscriptions used by the
// slip-panel focus-trap coordination.

import { describe, it, expect } from 'vitest';
import { isTourOpen, setTourOpen, subscribeTourOpen } from '../tourStorage';


describe('tourStorage tour-open flag', () => {
    it('defaults to closed', () => {
        setTourOpen(false);
        expect(isTourOpen()).toBe(false);
    });

    it('setTourOpen updates the flag and notifies subscribers immediately', () => {
        const seen: boolean[] = [];
        const unsub = subscribeTourOpen((open) => seen.push(open));
        setTourOpen(true);
        expect(isTourOpen()).toBe(true);
        expect(seen).toEqual([false, true]); // immediate current value + update
        setTourOpen(false);
        expect(seen).toEqual([false, true, false]);
        unsub();
    });

    it('after unsubscribe no further notifications arrive', () => {
        const seen: boolean[] = [];
        const unsub = subscribeTourOpen((open) => seen.push(open));
        unsub();
        setTourOpen(true);
        expect(seen).toEqual([false]);
        setTourOpen(false);
    });
});
