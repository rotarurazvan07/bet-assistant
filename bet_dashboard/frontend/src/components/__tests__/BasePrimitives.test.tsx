// BaseCard + BaseBadge + BaseDataRow (issue #64 P0).

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BaseCard } from '../ui/BaseCard';
import { BaseBadge } from '../ui/BaseBadge';
import { BaseDataRow } from '../ui/BaseDataRow';


describe('BaseCard', () => {
    it('renders children content', () => {
        render(<BaseCard>card body</BaseCard>);
        expect(screen.getByText('card body')).toBeInTheDocument();
    });

    it('renders header and footer when provided', () => {
        render(
            <BaseCard header={<span>HEAD</span>} footer={<span>FOOT</span>}>
                body
            </BaseCard>,
        );
        expect(screen.getByText('HEAD')).toBeInTheDocument();
        expect(screen.getByText('FOOT')).toBeInTheDocument();
    });

    it('omits header/footer wrappers when not provided', () => {
        const { container } = render(<BaseCard>body</BaseCard>);
        expect(container.querySelector('.card-header')).toBeNull();
        expect(container.querySelector('.card-footer')).toBeNull();
    });

    it('success status applies win border/bg vars', () => {
        const { container } = render(<BaseCard status="success">x</BaseCard>);
        const card = container.querySelector('.card');
        expect(card?.getAttribute('style')).toContain('var(--win)');
    });

    it('error status applies loss vars', () => {
        const { container } = render(<BaseCard status="error">x</BaseCard>);
        const card = container.querySelector('.card');
        expect(card?.getAttribute('style')).toContain('var(--loss)');
    });

    it('onClick fires when provided', async () => {
        const user = userEvent.setup();
        const onClick = vi.fn();
        render(<BaseCard onClick={onClick}>clickable</BaseCard>);
        await user.click(screen.getByText('clickable'));
        expect(onClick).toHaveBeenCalledTimes(1);
    });
});


describe('BaseBadge', () => {
    it('renders children with badge class', () => {
        render(<BaseBadge>Pending</BaseBadge>);
        const el = screen.getByText('Pending');
        expect(el.className).toContain('badge');
    });

    it('success status applies win palette', () => {
        render(<BaseBadge status="success">Won</BaseBadge>);
        const el = screen.getByText('Won');
        expect(el.getAttribute('style')).toContain('var(--win)');
    });

    it('error status applies loss palette', () => {
        render(<BaseBadge status="error">Lost</BaseBadge>);
        const el = screen.getByText('Lost');
        expect(el.getAttribute('style')).toContain('var(--loss)');
    });

    it('info status applies accent palette', () => {
        render(<BaseBadge status="info">Live</BaseBadge>);
        const el = screen.getByText('Live');
        expect(el.getAttribute('style')).toContain('var(--accent)');
    });

    it('renders icon before children when provided', () => {
        render(<BaseBadge icon={<span data-testid="ic">*</span>}>tagged</BaseBadge>);
        expect(screen.getByTestId('ic')).toBeInTheDocument();
        expect(screen.getByText('tagged')).toBeInTheDocument();
    });
});


describe('BaseDataRow', () => {
    it('renders label + value in flex layout by default', () => {
        render(<BaseDataRow label="Total" value="42" />);
        expect(screen.getByText('Total')).toBeInTheDocument();
        expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('success status colors the value', () => {
        render(<BaseDataRow label="L" value="V" status="success" />);
        const value = screen.getByText('V');
        expect(value.getAttribute('style')).toContain('var(--win)');
    });

    it('isTableRow renders a tr with cells + children', () => {
        const { container } = render(
            <table><tbody>
                <BaseDataRow isTableRow cells={[<td key="a">A</td>, <td key="b">B</td>]}>
                    <td key="c">C</td>
                </BaseDataRow>
            </tbody></table>,
        );
        const row = container.querySelector('tr');
        expect(row).not.toBeNull();
        expect(screen.getByText('A')).toBeInTheDocument();
        expect(screen.getByText('B')).toBeInTheDocument();
        expect(screen.getByText('C')).toBeInTheDocument();
    });

    it('actions render in the actions slot', () => {
        render(<BaseDataRow label="L" value="V" actions={<button>ACT</button>} />);
        expect(screen.getByText('ACT')).toBeInTheDocument();
    });

    it('className and style pass through', () => {
        const { container } = render(
            <BaseDataRow label="L" value="V" className="extra" style={{ padding: '1px' }} />,
        );
        const row = container.querySelector('.data-row');
        expect(row?.className).toContain('extra');
        expect(row?.getAttribute('style')).toContain('padding');
    });
});
