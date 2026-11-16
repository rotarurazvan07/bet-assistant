import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

    it('sorts rows by the clicked column, toggling asc/desc, columns keep their order', async () => {
        const user = userEvent.setup();
        const view = {
            key: 'acc',
            label: 'Accuracy',
            getValue: (cell: { accuracy?: number }) => Number(cell.accuracy),
            formatValue: (value: number) => `${value.toFixed(1)}%`,
            getColor: () => ({ color: 'green', bg: 'transparent' }),
        };
        render(
            <CorrelationContainer
                title="Source x Market Type Correlation"
                rowLabel="Source"
                colLabel="Market Type"
                rows={['forebet', 'xgscore']}
                cols={['result', 'btts']}
                formatColumnLabel={key => key === 'result' ? 'Result' : key === 'btts' ? 'BTTS' : key}
                matrix={{
                    forebet: { result: { accuracy: 40, total: 20 }, btts: { accuracy: 80, total: 20 } },
                    xgscore: { result: { accuracy: 60, total: 20 }, btts: { accuracy: 20, total: 20 } },
                }}
                minSampleSize={0}
                views={[view]}
            />,
        );

        const rowOrder = () =>
            screen.getAllByRole('row').slice(1).map(tr => (tr as HTMLTableRowElement).cells[0]?.textContent?.trim());
        const headerOrder = () =>
            screen.getAllByRole('columnheader').slice(1).map(th => th.textContent?.replace(/[↓↑]/g, '').trim());

        // Default: original row and column order
        expect(rowOrder()).toEqual(['forebet', 'xgscore']);
        expect(headerOrder()).toEqual(['Result', 'BTTS']);

        // Click Result header: desc by that column -> xgscore (60) before forebet (40)
        await user.click(screen.getByRole('columnheader', { name: /Result/ }));
        expect(rowOrder()).toEqual(['xgscore', 'forebet']);
        // Columns are NOT reordered
        expect(headerOrder()).toEqual(['Result', 'BTTS']);

        // Second click: asc -> forebet (40) before xgscore (60)
        await user.click(screen.getByRole('columnheader', { name: /Result/ }));
        expect(rowOrder()).toEqual(['forebet', 'xgscore']);
        expect(headerOrder()).toEqual(['Result', 'BTTS']);
    });

    it('keeps low-sample rows after sufficient ones regardless of direction', async () => {
        const user = userEvent.setup();
        const view = {
            key: 'acc',
            label: 'Accuracy',
            getValue: (cell: { accuracy?: number }) => Number(cell.accuracy),
            formatValue: (value: number) => `${value.toFixed(1)}%`,
            getColor: () => ({ color: 'green', bg: 'transparent' }),
        };
        render(
            <CorrelationContainer
                title="T"
                rowLabel="Source"
                colLabel="Market Type"
                rows={['low', 'high']}
                cols={['result']}
                matrix={{ low: { result: { accuracy: 99, total: 2 } }, high: { result: { accuracy: 10, total: 50 } } }}
                minSampleSize={10}
                views={[view]}
            />,
        );

        const rowOrder = () =>
            screen.getAllByRole('row').slice(1).map(tr => (tr as HTMLTableRowElement).cells[0]?.textContent?.trim());

        // Desc: sufficient (high, 10) before low-sample (low, 99) despite higher value
        await user.click(screen.getByRole('columnheader', { name: /result/i }));
        expect(rowOrder()).toEqual(['high', 'low']);

        // Asc: still sufficient first
        await user.click(screen.getByRole('columnheader', { name: /result/i }));
        expect(rowOrder()).toEqual(['high', 'low']);
    });
});
