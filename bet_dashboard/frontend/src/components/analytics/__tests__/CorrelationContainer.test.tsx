import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import CorrelationContainer from '../CorrelationContainer';

describe('CorrelationContainer', () => {
    it('formats column labels without changing matrix lookup keys', () => {
        render(
            <CorrelationContainer
                title="League x Market Correlation"
                rowLabel="League"
                colLabel="Market"
                rows={['La Liga']}
                cols={['home']}
                formatColumnLabel={key => key === 'home' ? '1' : key}
                matrix={{ 'La Liga': { home: { edge: 12.5, total: 8 } } }}
                minSampleSize={0}
                views={[{
                    key: 'edge',
                    label: 'Edge',
                    getValue: cell => Number(cell.edge),
                    formatValue: value => `+${value.toFixed(1)}%`,
                    getColor: () => ({ color: 'green', bg: 'transparent' }),
                }]}
            />,
        );

        expect(screen.getByRole('columnheader', { name: '1' })).toBeInTheDocument();
        expect(screen.getByText('+12.5%')).toBeInTheDocument();
        expect(screen.getByText('n=8')).toBeInTheDocument();
    });
});
