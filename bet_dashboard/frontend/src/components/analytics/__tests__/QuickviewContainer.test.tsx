import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import QuickviewContainer from '../QuickviewContainer';

describe('QuickviewContainer', () => {
    it('renders null or undefined values as "n/a" (never 0 or NaN)', () => {
        render(
            <QuickviewContainer
                tiles={[
                    { label: 'Null Metric', value: null },
                    { label: 'Undefined Metric', value: undefined },
                    { label: 'NaN Metric', value: NaN },
                    { label: 'Valid Metric', value: '42%' },
                ]}
            />
        );

        expect(screen.getByText('Null Metric')).toBeInTheDocument();
        expect(screen.getByText('Undefined Metric')).toBeInTheDocument();
        expect(screen.getByText('NaN Metric')).toBeInTheDocument();

        const naValues = screen.getAllByText('n/a');
        expect(naValues).toHaveLength(3);

        expect(screen.getByText('42%')).toBeInTheDocument();
    });

    it('renders badges, low sample warnings, and footer', () => {
        render(
            <QuickviewContainer
                tiles={[
                    {
                        label: 'Annualized',
                        value: '+25.4%',
                        badge: { text: '12d • early', color: 'var(--pending)' },
                        lowSampleWarning: 'Small sample (< 10 bets)',
                    },
                ]}
                footer={<div>Footer Content</div>}
            />
        );

        expect(screen.getByText('Annualized')).toBeInTheDocument();
        expect(screen.getByText('+25.4%')).toBeInTheDocument();
        expect(screen.getByText('12d • early')).toBeInTheDocument();
        expect(screen.getByText('⚠ Small sample (< 10 bets)')).toBeInTheDocument();
        expect(screen.getByText('Footer Content')).toBeInTheDocument();
    });
});
