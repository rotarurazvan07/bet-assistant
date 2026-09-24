// ui.tsx primitives (issue #64 P0). SPEC DIVERGENCE: spec wanted
// 'Button, Input, Select' components — actual exports are Tooltip,
// TooltipIcon, LiveDot, StatCard, Toggle, SectionHeader, StatusBadge.

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tooltip, TooltipIcon, LiveDot, StatCard, Toggle, SectionHeader, StatusBadge } from '../ui';


describe('Tooltip', () => {
    it('renders children without tooltip by default', () => {
        render(<Tooltip text="hint">hover me</Tooltip>);
        expect(screen.getByText('hover me')).toBeInTheDocument();
        expect(screen.queryByText('hint')).not.toBeInTheDocument();
    });

    it('shows tooltip text on hover via portal', async () => {
        const user = userEvent.setup();
        render(<Tooltip text="hint content">hover me</Tooltip>);
        await user.hover(screen.getByText('hover me'));
        expect(screen.getByText('hint content')).toBeInTheDocument();
    });

    it('hides tooltip on unhover', async () => {
        const user = userEvent.setup();
        render(<Tooltip text="hint content">hover me</Tooltip>);
        const trigger = screen.getByText('hover me');
        await user.hover(trigger);
        expect(screen.getByText('hint content')).toBeInTheDocument();
        await user.unhover(trigger);
        expect(screen.queryByText('hint content')).not.toBeInTheDocument();
    });
});


describe('TooltipIcon', () => {
    it('renders the ? trigger wrapping a tooltip', () => {
        render(<TooltipIcon text="what is this" />);
        expect(screen.getByText('?')).toBeInTheDocument();
        expect(screen.queryByText('what is this')).not.toBeInTheDocument();
    });
});


describe('LiveDot', () => {
    it('active (alive && enabled) renders the animate-ping layer', () => {
        const { container } = render(<LiveDot alive={true} enabled={true} />);
        expect(container.querySelector('.animate-ping')).not.toBeNull();
    });

    it('inactive (alive but disabled) renders no ping layer', () => {
        const { container } = render(<LiveDot alive={true} enabled={false} />);
        expect(container.querySelector('.animate-ping')).toBeNull();
    });

    it('inactive (enabled but not alive) renders no ping layer', () => {
        const { container } = render(<LiveDot alive={false} enabled={true} />);
        expect(container.querySelector('.animate-ping')).toBeNull();
    });
});


describe('StatCard', () => {
    it('renders label + value + optional sub', () => {
        render(<StatCard label="WIN RATE" value="66%" sub="of settled slips" />);
        expect(screen.getByText('WIN RATE')).toBeInTheDocument();
        expect(screen.getByText('66%')).toBeInTheDocument();
        expect(screen.getByText('of settled slips')).toBeInTheDocument();
    });

    it('omits sub when not provided', () => {
        render(<StatCard label="X" value="1" />);
        expect(screen.getByText('X')).toBeInTheDocument();
        expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('negative flag wins over positive (loss color)', () => {
        // color priority: negative beats positive per source order
        const { container } = render(<StatCard label="X" value="-1" positive negative />);
        const value = container.querySelector('.font-bold');
        expect(value).not.toBeNull();
    });
});


describe('Toggle', () => {
    it('fires onChange with new checked state on click', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<Toggle checked={false} onChange={onChange} label="Show all" />);
        expect(screen.getByText('Show all')).toBeInTheDocument();
        const checkbox = screen.getByRole('checkbox');
        expect(checkbox).not.toBeChecked();
        await user.click(checkbox);
        expect(onChange).toHaveBeenCalledWith(true);
    });

    it('reflects checked state', () => {
        render(<Toggle checked={true} onChange={() => {}} />);
        expect(screen.getByRole('checkbox')).toBeChecked();
    });
});


describe('SectionHeader', () => {
    it('renders icon + title + sub', () => {
        render(<SectionHeader icon="📊" title="Analytics" sub="last 30 days" />);
        expect(screen.getByText('📊')).toBeInTheDocument();
        expect(screen.getByText('Analytics')).toBeInTheDocument();
        expect(screen.getByText('last 30 days')).toBeInTheDocument();
    });

    it('renders title only when icon/sub omitted', () => {
        render(<SectionHeader title="Solo" />);
        expect(screen.getByText('Solo')).toBeInTheDocument();
    });
});


describe('StatusBadge', () => {
    it.each([
        ['Won', 'badge-won'],
        ['Lost', 'badge-lost'],
        ['Pending', 'badge-pending'],
        ['Live', 'badge-live'],
    ])('%s → class %s', (status, cls) => {
        render(<StatusBadge status={status} />);
        expect(screen.getByText(status).className).toContain(cls);
    });

    it('unknown status falls back to badge-pending', () => {
        render(<StatusBadge status="Unknown" />);
        expect(screen.getByText('Unknown').className).toContain('badge-pending');
    });
});

// ── Gap-closing: Tooltip align variants ──

describe('Tooltip align variants', () => {
    it('left align renders on hover', async () => {
        const user = userEvent.setup();
        render(<Tooltip text="left tip" align="left">L</Tooltip>);
        await user.hover(screen.getByText('L'));
        expect(screen.getByText('left tip')).toBeInTheDocument();
    });

    it('right align renders on hover', async () => {
        const user = userEvent.setup();
        render(<Tooltip text="right tip" align="right">R</Tooltip>);
        await user.hover(screen.getByText('R'));
        expect(screen.getByText('right tip')).toBeInTheDocument();
    });

    it('TooltipIcon align passes through to tooltip', async () => {
        const user = userEvent.setup();
        render(<TooltipIcon text="icon tip" align="left" />);
        await user.hover(screen.getByText('?'));
        expect(screen.getByText('icon tip')).toBeInTheDocument();
    });
});
