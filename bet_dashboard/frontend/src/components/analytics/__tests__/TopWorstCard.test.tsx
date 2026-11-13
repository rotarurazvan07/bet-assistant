import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import TopWorstCard from '../TopWorstCard';
import { ALL_MARKETS } from '../../../config/marketConfig';
import type { RankableItem } from '../../../utils/analyticsRetrospection';

describe('TopWorstCard', () => {
    it('renders empty message when no items are eligible', () => {
        render(
            <TopWorstCard
                title="Markets"
                top={[]}
                worst={[]}
            />
        );

        expect(screen.getByText('Markets')).toBeInTheDocument();
        expect(screen.getByText('not enough data (min legs)')).toBeInTheDocument();
    });

    it('renders top and worst lists with formatted names, edge, and leg count', () => {
        const key1 = ALL_MARKETS[0];
        const key2 = ALL_MARKETS[1];
        const key3 = ALL_MARKETS[2];

        const top: RankableItem[] = [
            { name: key1, edge: 8.5, legs: 25 },
            { name: key2, edge: 4.2, legs: 18 },
        ];
        const worst: RankableItem[] = [
            { name: key3, edge: -6.1, legs: 14 },
        ];

        render(
            <TopWorstCard
                title="Markets"
                top={top}
                worst={worst}
                formatName={name => `Market: ${name}`}
            />
        );

        expect(screen.getByText(`1. Market: ${key1}`)).toBeInTheDocument();
        expect(screen.getByText('+8.5%')).toBeInTheDocument();
        expect(screen.getByText('(n=25)')).toBeInTheDocument();

        expect(screen.getByText(`2. Market: ${key2}`)).toBeInTheDocument();
        expect(screen.getByText('+4.2%')).toBeInTheDocument();
        expect(screen.getByText('(n=18)')).toBeInTheDocument();

        expect(screen.getByText(`Market: ${key3}`)).toBeInTheDocument();
        expect(screen.getByText('-6.1%')).toBeInTheDocument();
        expect(screen.getByText('(n=14)')).toBeInTheDocument();
    });

    it('shows message when top exists but worst has no remaining items', () => {
        const top: RankableItem[] = [
            { name: 'League A', edge: 10.0, legs: 12 },
        ];

        render(
            <TopWorstCard
                title="Leagues"
                top={top}
                worst={[]}
            />
        );

        expect(screen.getByText('1. League A')).toBeInTheDocument();
        expect(screen.getByText('No eligible worst items')).toBeInTheDocument();
    });
});
