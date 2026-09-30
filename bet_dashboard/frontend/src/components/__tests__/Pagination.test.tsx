// Pagination (issue #64). SPEC DIVERGENCE: no page-size selector exists —
// page numbers + prev/next + ellipsis gaps only.

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Pagination from '../Pagination';


describe('Pagination', () => {
    it('renders nothing when totalPages <= 1', () => {
        const { container } = render(<Pagination page={1} totalPages={1} onPageChange={() => {}} />);
        expect(container).toBeEmptyDOMElement();
    });

    it('disables prev on page 1 and next on last page', () => {
        render(<Pagination page={1} totalPages={3} onPageChange={() => {}} />);
        expect(screen.getByText('‹')).toBeDisabled();
        expect(screen.getByText('›')).toBeEnabled();
    });

    it('disables next on final page', () => {
        render(<Pagination page={3} totalPages={3} onPageChange={() => {}} />);
        expect(screen.getByText('›')).toBeDisabled();
        expect(screen.getByText('‹')).toBeEnabled();
    });

    it('prev/next fire onPageChange with adjacent page', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<Pagination page={2} totalPages={3} onPageChange={onChange} />);
        await user.click(screen.getByText('‹'));
        expect(onChange).toHaveBeenCalledWith(1);
        await user.click(screen.getByText('›'));
        expect(onChange).toHaveBeenCalledWith(3);
    });

    it('numbered page buttons fire onPageChange', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        // page=1 totalPages=5 window renders [1,2,3,…,5] — 3 is the
        // farthest visible non-current page; 4 hides behind the ellipsis
        render(<Pagination page={1} totalPages={5} onPageChange={onChange} />);
        await user.click(screen.getByText('3'));
        expect(onChange).toHaveBeenCalledWith(3);
    });

    it('inserts ellipsis gaps for far pages', () => {
        render(<Pagination page={6} totalPages={20} onPageChange={() => {}} />);
        expect(screen.getAllByText('…').length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('20')).toBeInTheDocument();
    });

    it('no ellipsis when window covers all pages', () => {
        render(<Pagination page={2} totalPages={4} onPageChange={() => {}} />);
        expect(screen.queryByText('…')).not.toBeInTheDocument();
    });
});
