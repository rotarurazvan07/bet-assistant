// ErrorBoundary (issue #64). Matches spec: catches render errors, fallback UI,
// logs via console.error, Try Again resets state.

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorBoundary from '../ErrorBoundary';


function Boom(): never { throw new Error('kaboom'); }


beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
});


describe('ErrorBoundary', () => {
    it('renders children when no error', () => {
        render(<ErrorBoundary><p>fine</p></ErrorBoundary>);
        expect(screen.getByText('fine')).toBeInTheDocument();
    });

    it('shows default fallback with error message on crash', () => {
        render(<ErrorBoundary><Boom /></ErrorBoundary>);
        expect(screen.getByText('Something went wrong.')).toBeInTheDocument();
        expect(screen.getByText('kaboom')).toBeInTheDocument();
    });

    it('uses custom fallback when provided', () => {
        render(<ErrorBoundary fallback={<p>custom</p>}><Boom /></ErrorBoundary>);
        expect(screen.getByText('custom')).toBeInTheDocument();
        expect(screen.queryByText('Something went wrong.')).not.toBeInTheDocument();
    });

    it('logs the caught error to console.error', () => {
        render(<ErrorBoundary><Boom /></ErrorBoundary>);
        expect(console.error).toHaveBeenCalledWith(
            'ErrorBoundary caught:', expect.any(Error), expect.objectContaining({ componentStack: expect.stringContaining('Boom') }),
        );
    });

    it('Try Again resets to children render', async () => {
        const user = userEvent.setup();
        let shouldThrow = true;
        function MaybeBoom() {
            if (shouldThrow) throw new Error('temp');
            return <p>recovered</p>;
        }
        render(<ErrorBoundary><MaybeBoom /></ErrorBoundary>);
        expect(screen.getByText('Something went wrong.')).toBeInTheDocument();
        shouldThrow = false;
        await user.click(screen.getByText('Try Again'));
        expect(screen.getByText('recovered')).toBeInTheDocument();
    });
});
