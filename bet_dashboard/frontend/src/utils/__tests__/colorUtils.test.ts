import { describe, it, expect } from 'vitest';
import { getPotentialStatusColor } from '../colorUtils';
import { MARKET_COLUMNS } from '../../config/marketConfig';

function k(l: string): string {
    const c = MARKET_COLUMNS.find(x => x.label === l);
    if (!c) throw new Error('no column ' + l);
    return c.market;
}
function col(m: string, s: string, o = 1.5) {
    return getPotentialStatusColor({ market: m, odds: o, status: 'Live' }, s);
}
const WIN = 'var(--potential-win)';
const LOSS = 'var(--potential-loss)';

describe('getPotentialStatusColor canonical keys (U1)', () => {
    it('user case: under_25 @ live 1-0 is WINNING (was red before the fix)', () => {
        expect(col(k('U2.5'), '1 - 0')).toBe(WIN);
        expect(col(k('U2.5'), '2 - 0')).toBe(WIN); // under 2.5 with 2 goals still WINS (strict <)
    });

    it('over_25 @ 1-0 is losing; @ 2-0 winning', () => {
        expect(col(k('O2.5'), '1 - 0')).toBe(LOSS);
        expect(col(k('O2.5'), '2 - 0')).toBe(LOSS); // over 2.5 needs 3+ goals
    });

    it('every over/under line dispatches by its canonical key (not labels)', () => {
        expect(col(k('O0.5'), '1 - 0')).toBe(WIN);
        expect(col(k('U0.5'), '0 - 0')).toBe(WIN);
        expect(col(k('U0.5'), '1 - 0')).toBe(LOSS);
        expect(col(k('O1.5'), '1 - 0')).toBe(LOSS);
        expect(col(k('U1.5'), '1 - 0')).toBe(WIN);
        expect(col(k('O3.5'), '2 - 0')).toBe(LOSS);
        expect(col(k('U3.5'), '2 - 0')).toBe(WIN);
        expect(col(k('O4.5'), '2 - 0')).toBe(LOSS);
        expect(col(k('U4.5'), '2 - 0')).toBe(WIN);
    });

    it('1X2 canonical keys', () => {
        expect(col(k('1'), '1 - 0')).toBe(WIN);
        expect(col(k('1'), '0 - 1')).toBe(LOSS);
        expect(col(k('X'), '1 - 1')).toBe(WIN);
        expect(col(k('X'), '1 - 0')).toBe(LOSS);
        expect(col(k('2'), '0 - 1')).toBe(WIN);
        expect(col(k('2'), '1 - 1')).toBe(LOSS);
    });

    it('btts canonical keys', () => {
        expect(col(k('BTTS Y'), '1 - 0')).toBe(LOSS);
        expect(col(k('BTTS N'), '1 - 0')).toBe(WIN);
        expect(col(k('BTTS Y'), '1 - 1')).toBe(WIN);
        expect(col(k('BTTS N'), '1 - 1')).toBe(LOSS);
        expect(col(k('BTTS N'), '0 - 0')).toBe(WIN);
        expect(col(k('BTTS Y'), '0 - 0')).toBe(LOSS);
    });

    it('double chance canonical keys', () => {
        expect(col(k('1X'), '1 - 1')).toBe(WIN);
        expect(col(k('1X'), '0 - 1')).toBe(LOSS);
        expect(col(k('12'), '1 - 1')).toBe(LOSS); // 12 = either team wins; draw loses
        expect(col(k('12'), '1 - 0')).toBe(WIN);
        expect(col(k('X2'), '1 - 1')).toBe(WIN);
        expect(col(k('X2'), '1 - 0')).toBe(LOSS);
    });

    it('pre-U1 label strings do NOT match markets: odds fallback (no compat shim)', () => {
        expect(col('Under 2.5', '1 - 0', 1.5)).toBe(LOSS);
        expect(col('Under 2.5', '1 - 0', 2.5)).toBe(WIN);
    });

    it('guards preserved: non-Live status and unparseable score', () => {
        expect(getPotentialStatusColor({ market: k('U2.5'), odds: 1.5, status: 'Pending' }, '1 - 0')).toBe('');
        expect(col(k('U2.5'), 'nope')).toBe(LOSS);
    });
