/** Satisfies: AC-02, AC-09 */
export const TOUR_DONE_KEY = 'bet-assistant-tour-done';
/** Satisfies: AC-06 */
export const FIRST_SLIP_KEY = 'bet-assistant-first-slip-done';

/** Returns true only on the first successful addSlip. Satisfies: AC-06, AC-10 */
export function markFirstSlip(): boolean {
    try {
        if (localStorage.getItem(FIRST_SLIP_KEY) === '1') return false;
        localStorage.setItem(FIRST_SLIP_KEY, '1');
        return true;
    } catch {
        return false;
    }
}

/** Workstream B (#47): module-level tour-open flag + subscribers so the slip
 * panel's focus trap can stand down while the tour dialog is open.
 * Kept deliberately tiny — no context, no new deps. */
let tourOpen = false;
const tourListeners = new Set<(open: boolean) => void>();

export function setTourOpen(open: boolean): void {
    tourOpen = open;
    tourListeners.forEach((fn) => fn(open));
}

export function subscribeTourOpen(fn: (open: boolean) => void): () => void {
    tourListeners.add(fn);
    fn(tourOpen);
    return () => { tourListeners.delete(fn); };
}

export function isTourOpen(): boolean {
    return tourOpen;
}
