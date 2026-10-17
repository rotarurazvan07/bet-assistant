// TradeoffSlider (issue #41). Replaces BuilderPanel's abstract DualSlider:
// labels at each end describe the behavioural consequence, the centre label
// flips to the dominant end away from the midpoint, and the tooltip explains
// the algorithmic impact. Native range input => keyboard operable by default.

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TradeoffSlider from '../TradeoffSlider';


const base = {
    leftLabel: 'More picks, lower avg quality',
    rightLabel: 'Fewer picks, higher avg quality',
    label: 'Distribution Logic',
    tip: 'Quality vs balance trade-off',
};


describe('TradeoffSlider', () => {
    it('renders both end labels and the centre label at the midpoint', () => {
        render(<TradeoffSlider {...base} value={0.5} onChange={() => {}} />);
        expect(screen.getByText('More picks, lower avg quality')).toBeInTheDocument();
        expect(screen.getByText('Fewer picks, higher avg quality')).toBeInTheDocument();
        expect(screen.getAllByText('Balanced').length).toBeGreaterThan(0);
    });

    it('dynamic label flips to the left label at value 0', () => {
        const { container } = render(<TradeoffSlider {...base} value={0} onChange={() => {}} />);
        const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
        expect(slider.getAttribute('aria-valuetext')).toBe('More picks, lower avg quality');
    });

    it('dynamic label flips to the right label at value 1', () => {
        const { container } = render(<TradeoffSlider {...base} value={1} onChange={() => {}} />);
        const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
        expect(slider.getAttribute('aria-valuetext')).toBe('Fewer picks, higher avg quality');
    });

    it('range input is keyboard operable and carries an accessible name', () => {
        const { container } = render(<TradeoffSlider {...base} value={0.5} onChange={() => {}} />);
        const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
        expect(slider.getAttribute('aria-label')).toBe('Distribution Logic');
        expect(slider.disabled).toBe(false);
    });

    it('change fires onChange with the 0..1 value', () => {
        const onChange = vi.fn();
        const { container } = render(<TradeoffSlider {...base} value={0.5} onChange={onChange} />);
        fireEvent.change(container.querySelector('input[type="range"]') as HTMLInputElement, { target: { value: '80' } });
        expect(onChange).toHaveBeenCalledWith(0.8);
    });

    it('tooltip is reachable by focus (not hover only) and explains the impact', async () => {
        const user = userEvent.setup();
        render(<TradeoffSlider {...base} value={0.5} onChange={() => {}} />);
        await user.tab(); // first tab stop is the tooltip trigger (before the slider)
        expect(screen.getByText(/Quality vs balance trade-off/)).toBeInTheDocument();
    });

    it('tooltip is reachable by hover too', async () => {
        const user = userEvent.setup();
        render(<TradeoffSlider {...base} value={0.5} onChange={() => {}} />);
        await user.hover(screen.getByText('?'));
        expect(screen.getByText(/Quality vs balance trade-off/)).toBeInTheDocument();
    });

    it('disabled marks the range input disabled (blocks keyboard/pointer use)', () => {
        const { container } = render(<TradeoffSlider {...base} value={0.5} onChange={() => {}} disabled />);
        const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
        expect(slider.disabled).toBe(true);
    });
});
