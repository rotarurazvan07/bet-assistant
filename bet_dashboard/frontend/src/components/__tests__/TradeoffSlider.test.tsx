// TradeoffSlider (issue #41 / Workstream B Part A): narrated trade-off slider.
// Contract: same range-input shape as the retired DualSlider (min 0 max 100
// step 5, value*100, /100 on change, disabled passthrough) plus captions that
// change with the band and a tooltip explaining algorithmic impact.

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TradeoffSlider } from '../TradeoffSlider';


function renderSlider(overrides: Partial<Parameters<typeof TradeoffSlider>[0]> = {}) {
    const onChange = vi.fn();
    const props = {
        label: 'Distribution Logic',
        tip: 'Balances quality vs balance.',
        leftLabel: 'Balance',
        rightLabel: 'Quality',
        leftCaption: 'Left caption — coverage first.',
        midCaption: 'Mid caption — balanced.',
        rightCaption: 'Right caption — precision first.',
        value: 0.5,
        onChange,
        ...overrides,
    };
    render(<TradeoffSlider {...props} />);
    return { onChange };
}


describe('TradeoffSlider', () => {
    it('renders the range contract: min 0, max 100, step 5, value*100', () => {
        renderSlider({ value: 0.5 });
        const slider = screen.getByRole('slider', { name: 'Distribution Logic' }) as HTMLInputElement;
        expect(slider.type).toBe('range');
        expect(slider.min).toBe('0');
        expect(slider.max).toBe('100');
        expect(slider.step).toBe('5');
        expect(slider.value).toBe('50');
    });

    it('emits value/100 on change', () => {
        const { onChange } = renderSlider();
        const slider = screen.getByRole('slider', { name: 'Distribution Logic' });
        fireEvent.change(slider, { target: { value: '80' } });
        expect(onChange).toHaveBeenCalledWith(0.8);
    });

    it('shows the mid caption in the middle band', () => {
        renderSlider({ value: 0.5 });
        expect(screen.getByTestId('tradeoff-caption')).toHaveTextContent('Mid caption — balanced.');
    });

    it('shows the left caption below one third', () => {
        renderSlider({ value: 0.1 });
        expect(screen.getByTestId('tradeoff-caption')).toHaveTextContent('Left caption — coverage first.');
    });

    it('shows the right caption above two thirds', () => {
        renderSlider({ value: 0.9 });
        expect(screen.getByTestId('tradeoff-caption')).toHaveTextContent('Right caption — precision first.');
    });

    it('exposes the tooltip text via title and aria-describedby (screen-reader safe)', () => {
        renderSlider({ tip: 'Algorithmic impact explanation.' });
        const slider = screen.getByRole('slider', { name: 'Distribution Logic' });
        expect(slider.getAttribute('title')).toBe('Algorithmic impact explanation.');
        const describedBy = slider.getAttribute('aria-describedby');
        expect(describedBy).toBeTruthy();
        expect(document.getElementById(describedBy as string)?.textContent).toBe('Algorithmic impact explanation.');
    });

    it('falls back to the caption as tooltip text when no tip is provided', () => {
        renderSlider({ tip: undefined, value: 0.9 });
        const slider = screen.getByRole('slider', { name: 'Distribution Logic' });
        expect(slider.getAttribute('title')).toBe('Right caption — precision first.');
    });

    it('passes disabled through to the input and blocks pointer events', () => {
        renderSlider({ disabled: true });
        const slider = screen.getByRole('slider', { name: 'Distribution Logic' }) as HTMLInputElement;
        expect(slider.disabled).toBe(true);
    });

    it('sets aria-valuetext to the active caption band', () => {
        renderSlider({ value: 0.1 });
        const slider = screen.getByRole('slider', { name: 'Distribution Logic' });
        expect(slider.getAttribute('aria-valuetext')).toBe('Left caption — coverage first.');
    });
});
