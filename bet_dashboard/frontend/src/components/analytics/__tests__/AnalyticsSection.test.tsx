import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AnalyticsSection from '../AnalyticsSection';

describe('AnalyticsSection', () => {
    it('renders section title, quickview, and collapsed detail by default', () => {
        render(
            <AnalyticsSection
                title="Financials"
                icon="₿"
                quickview={<div>Quickview Content</div>}
                detail={<div>Detail Content</div>}
            />
        );

        expect(screen.getByText('Financials')).toBeInTheDocument();
        expect(screen.getByText('Quickview Content')).toBeInTheDocument();
        expect(screen.getByText('Detail Content')).toBeInTheDocument();

        const toggleBtn = screen.getByRole('button', { name: /view more/i });
        expect(toggleBtn).toBeInTheDocument();
        expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
    });

    it('toggles detail expansion when clicking View more / View less', async () => {
        const user = userEvent.setup();
        render(
            <AnalyticsSection
                title="Strategy"
                icon="◈"
                quickview={<div>Quickview Strategy</div>}
                detail={<div>Detail Strategy</div>}
            />
        );

        const toggleBtn = screen.getByRole('button', { name: /view more/i });
        expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');

        // Click to expand
        await user.click(toggleBtn);
        expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByRole('button', { name: /view less/i })).toBeInTheDocument();

        // Click to collapse
        await user.click(toggleBtn);
        expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
        expect(screen.getByRole('button', { name: /view more/i })).toBeInTheDocument();
    });

    it('independent expansion between two sections', async () => {
        const user = userEvent.setup();
        render(
            <div>
                <AnalyticsSection
                    title="Section 1"
                    quickview={<div>Quickview One</div>}
                    detail={<div>Detail One</div>}
                />
                <AnalyticsSection
                    title="Section 2"
                    quickview={<div>Quickview Two</div>}
                    detail={<div>Detail Two</div>}
                />
            </div>
        );

        const buttons = screen.getAllByRole('button', { name: /view more/i });
        expect(buttons).toHaveLength(2);

        // Open Section 1
        await user.click(buttons[0]);
        expect(buttons[0]).toHaveAttribute('aria-expanded', 'true');
        expect(buttons[1]).toHaveAttribute('aria-expanded', 'false');

        // Open Section 2
        await user.click(buttons[1]);
        expect(buttons[0]).toHaveAttribute('aria-expanded', 'true');
        expect(buttons[1]).toHaveAttribute('aria-expanded', 'true');
    });
});
