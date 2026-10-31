/** Satisfies:*/
export const TOUR_DONE_KEY = 'bet-assistant-tour-done';
/** Satisfies: */
export const FIRST_SLIP_KEY = 'bet-assistant-first-slip-done';

/** Returns true only on the first successful addSlip. Satisfies:*/
export function markFirstSlip(): boolean {
    try {
        if (localStorage.getItem(FIRST_SLIP_KEY) === '1') return false;
        localStorage.setItem(FIRST_SLIP_KEY, '1');
        return true;
    } catch {
        return false;
    }
}
