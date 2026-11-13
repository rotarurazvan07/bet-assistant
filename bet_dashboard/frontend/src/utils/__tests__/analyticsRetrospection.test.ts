import { describe, it, expect } from 'vitest';
import {
    rankTopWorst, filterEligibleItems, MIN_SAMPLE_SIZE,
    trustLevel, sortByTrust,
} from '../analyticsRetrospection';

describe('rankTopWorst', () => {
    it('returns empty top and worst for an empty list', () => {
        const result = rankTopWorst([]);
        expect(result.top).toEqual([]);
        expect(result.worst).toEqual([]);
    });

    it('handles list with fewer than 6 items without intersection', () => {
        // Exactly 5 items
        const items = [
            { name: 'A', edge: 10, legs: 20 },
            { name: 'B', edge: 8, legs: 15 },
            { name: 'C', edge: 5, legs: 12 },
            { name: 'D', edge: -2, legs: 25 },
            { name: 'E', edge: -5, legs: 30 },
        ];

        const { top, worst } = rankTopWorst(items, 3);

        // Top gets 3 items
        expect(top).toHaveLength(3);
        expect(top.map(i => i.name)).toEqual(['A', 'B', 'C']);

        // Worst gets the remaining 2 items
        expect(worst).toHaveLength(2);
        expect(worst.map(i => i.name)).toEqual(['E', 'D']);

        // Assert zero overlap
        const topNames = new Set(top.map(i => i.name));
        for (const w of worst) {
            expect(topNames.has(w.name)).toBe(false);
        }
    });

    it('handles list with 3 or fewer items (top gets all, worst gets none)', () => {
        const items = [
            { name: 'A', edge: 10, legs: 20 },
            { name: 'B', edge: 5, legs: 15 },
            { name: 'C', edge: 1, legs: 12 },
        ];

        const { top, worst } = rankTopWorst(items, 3);
        expect(top).toHaveLength(3);
        expect(worst).toHaveLength(0);

        const single = rankTopWorst([{ name: 'Only', edge: 4.2, legs: 10 }], 3);
        expect(single.top).toHaveLength(1);
        expect(single.worst).toHaveLength(0);
    });

    it('handles 6 or more items with no intersection', () => {
        const items = [
            { name: 'A', edge: 15, legs: 20 },
            { name: 'B', edge: 12, legs: 15 },
            { name: 'C', edge: 10, legs: 18 },
            { name: 'D', edge: 5, legs: 10 },
            { name: 'E', edge: 2, legs: 14 },
            { name: 'F', edge: 0, legs: 22 },
            { name: 'G', edge: -3, legs: 11 },
            { name: 'H', edge: -7, legs: 16 },
        ];

        const { top, worst } = rankTopWorst(items, 3);
        expect(top.map(i => i.name)).toEqual(['A', 'B', 'C']);
        // Worst sorted by lowest edge first
        expect(worst.map(i => i.name)).toEqual(['H', 'G', 'F']);

        // Intersection must be empty
        const topNames = new Set(top.map(i => i.name));
        for (const w of worst) {
            expect(topNames.has(w.name)).toBe(false);
        }
    });

    it('resolves ties deterministically by name', () => {
        const items = [
            { name: 'Beta', edge: 5, legs: 20 },
            { name: 'Alpha', edge: 5, legs: 20 },
            { name: 'Gamma', edge: 5, legs: 20 },
            { name: 'Delta', edge: -1, legs: 20 },
            { name: 'Epsilon', edge: -1, legs: 20 },
            { name: 'Zeta', edge: -1, legs: 20 },
        ];

        const { top, worst } = rankTopWorst(items, 3);
        // Alpha, Beta, Gamma tie at 5 -> sorted alphabetically
        expect(top.map(i => i.name)).toEqual(['Alpha', 'Beta', 'Gamma']);
        // Delta, Epsilon, Zeta tie at -1 -> sorted alphabetically
        expect(worst.map(i => i.name)).toEqual(['Delta', 'Epsilon', 'Zeta']);
    });
});

describe('filterEligibleItems', () => {
    it('filters out items with legs below MIN_SAMPLE_SIZE', () => {
        const items = [
            { name: 'Valid', legs: MIN_SAMPLE_SIZE },
            { name: 'Above', legs: MIN_SAMPLE_SIZE + 5 },
            { name: 'Below', legs: MIN_SAMPLE_SIZE - 1 },
            { name: 'Zero', legs: 0 },
        ];
        const eligible = filterEligibleItems(items);
        expect(eligible.map(i => i.name)).toEqual(['Valid', 'Above']);
    });
});

describe('trustLevel', () => {
    it('classifies high above 0.6', () => {
        expect(trustLevel(0.61)).toBe('high');
        expect(trustLevel(1.0)).toBe('high');
        expect(trustLevel(0.6)).toBe('medium'); // boundary: not > 0.6
    });
    it('classifies medium between 0.3 and 0.6 inclusive', () => {
        expect(trustLevel(0.3)).toBe('medium');
        expect(trustLevel(0.5)).toBe('medium');
        expect(trustLevel(0.6)).toBe('medium');
    });
    it('classifies low below 0.3', () => {
        expect(trustLevel(0.29)).toBe('low');
        expect(trustLevel(0.0)).toBe('low');
    });
});

describe('sortByTrust', () => {
    const rows = [
        { source: 'b', trust_score: 0.5 },
        { source: 'a', trust_score: 0.9 },
        { source: 'c', trust_score: 0.5 },
    ];
    it('sorts descending by default with source name tiebreaker', () => {
        expect(sortByTrust(rows).map(r => r.source)).toEqual(['a', 'b', 'c']);
    });
    it('sorts ascending when requested', () => {
        expect(sortByTrust(rows, 'asc').map(r => r.source)).toEqual(['b', 'c', 'a']);
    });
    it('does not mutate input', () => {
        const copy = [...rows];
        sortByTrust(rows);
        expect(rows).toEqual(copy);
    });
});
