import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import SlipCalendar from '../SlipCalendar';
import { server } from '../../test/handlers';
import { makeSlipCalendarData } from '../../test/factories';

function currentMonthDate(day: number): string {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

describe('SlipCalendar', () => {
    it('shows daily P&L tooltip and selects a date', async () => {
        const selected: string[] = [];
        const date = currentMonthDate(7);
        server.use(http.get('/api/slips/calendar', () => HttpResponse.json(makeSlipCalendarData({
            days: [{ date, slips: 3, wins: 2, losses: 1, net_profit: 2.4 }],
        }))));

        render(
            <SlipCalendar
                profiles={['low']}
                dateFrom=""
                dateTo=""
                selectedDate={null}
                onSelectDate={value => selected.push(value)}
            />,
        );

        const dayButton = await screen.findByRole('button', { name: `${date}: 3 slips, +2.4U, 2W/1L` });
        expect(dayButton).toHaveAttribute('title', '3 slips, +2.4U, 2W/1L');
        fireEvent.click(dayButton);
        expect(selected).toEqual([date]);
    });

    it('clips the requested calendar range to global date filters', async () => {
        const dateFrom = currentMonthDate(7);
        const dateTo = currentMonthDate(8);
        let query = '';
        server.use(http.get('/api/slips/calendar', ({ request }) => {
            query = new URL(request.url).search;
            return HttpResponse.json(makeSlipCalendarData());
        }));

        render(
            <SlipCalendar
                profiles={[]}
                dateFrom={dateFrom}
                dateTo={dateTo}
                selectedDate={null}
                onSelectDate={() => {}}
            />,
        );

        await waitFor(() => expect(query).toContain(`date_from=${dateFrom}`));
        expect(query).toContain(`date_to=${dateTo}`);
        expect(screen.getByRole('button', { name: new RegExp(`${dateFrom}:`) })).toBeEnabled();
        const previousDay = currentMonthDate(6);
        expect(screen.getByRole('button', { name: new RegExp(`${previousDay}:`) })).toBeDisabled();
    });

    it('supports month navigation and returning to the current month', () => {
        render(
            <SlipCalendar
                profiles={[]}
                dateFrom=""
                dateTo=""
                selectedDate={null}
                onSelectDate={() => {}}
            />,
        );
        const heading = screen.getByRole('heading', { level: 2 });
        const currentMonth = heading.textContent;
        fireEvent.click(screen.getByRole('button', { name: 'Previous month' }));
        expect(heading.textContent).not.toBe(currentMonth);
        fireEvent.click(screen.getByRole('button', { name: 'Next month' }));
        expect(heading.textContent).toBe(currentMonth);
        fireEvent.click(screen.getByRole('button', { name: 'Previous month' }));
        fireEvent.click(screen.getByRole('button', { name: 'Today' }));
        expect(heading.textContent).toBe(currentMonth);
    });
});
