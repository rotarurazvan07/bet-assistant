// OddsMovementIndicator (issue #64). SPEC DIVERGENCE: spec wants ➡️ for
// 'stable' — component returns null for stable/undefined. No strength bar
// or numeric tooltip exists (title attr only). up=red, down=green (inverted
// from naive expectation: rising odds = market disagrees = red).

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OddsMovementIndicator } from '../OddsMovementIndicator';

describe('OddsMovementIndicator', () => {
    it('renders nothing for stable direction (divergence pin: no ➡️)', () => {
        const { container } = render(<OddsMovementIndicator direction="stable" />);
        expect(container).toBeEmptyDOMElement();
    });

    it('renders nothing for undefined direction', () => {
        const { container } = render(<OddsMovementIndicator direction={undefined} />);
        expect(container).toBeEmptyDOMElement();
    });

    it('renders up arrow with rising-odds title', () => {
        render(<OddsMovementIndicator direction="up" />);
        expect(screen.getByTitle('Odds rising (market disagrees)')).toBeInTheDocument();
    });

    it('renders down arrow with falling-odds title', () => {
        render(<OddsMovementIndicator direction="down" />);
        expect(screen.getByTitle('Odds falling (market agrees)')).toBeInTheDocument();
    });

    it('applies sm size class by default and md when requested', () => {
        // SVG className is SVGAnimatedString in jsdom — assert via getAttribute
        const { container: smC } = render(<OddsMovementIndicator direction="up" />);
        const svg = smC.querySelector('svg');
        expect(svg?.getAttribute('class')).toContain('w-3.5');
        const { container: mdC } = render(<OddsMovementIndicator direction="up" size="md" />);
        const svgMd = mdC.querySelector('svg');
        expect(svgMd?.getAttribute('class')).toContain('w-5');
    });

    it('up uses red palette, down uses green palette', () => {
        const { container: upC } = render(<OddsMovementIndicator direction="up" />);
        expect(upC.querySelector('span')?.className).toContain('text-red-400');
        const { container: downC } = render(<OddsMovementIndicator direction="down" />);
        expect(downC.querySelector('span')?.className).toContain('text-emerald-400');
    });
});
