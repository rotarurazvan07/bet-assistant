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
