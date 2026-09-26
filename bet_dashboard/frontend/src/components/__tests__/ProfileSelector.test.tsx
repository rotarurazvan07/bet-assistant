// ProfileSelector (issue #64 P0). ACTUAL behavior (cycle-12 divergence
// notes): syncs ALL profiles on first load when none selected; blocks
// deselecting the last profile; SELECT ALL disabled when all selected.

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProfileSelector } from '../ui/ProfileSelector';


describe('ProfileSelector', () => {
    it('renders all profile chips', () => {
        render(<ProfileSelector profiles={['low', 'medium', 'high_risk']} selectedProfiles={['low']} onChange={() => {}} profileData={null} />);
        expect(screen.getByText('low')).toBeInTheDocument();
        expect(screen.getByText('medium')).toBeInTheDocument();
        expect(screen.getByText('high_risk')).toBeInTheDocument();
    });

    it('shows empty-state text when no profiles', () => {
        render(<ProfileSelector profiles={[]} selectedProfiles={[]} onChange={() => {}} profileData={null} />);
        expect(screen.getByText('No profiles available')).toBeInTheDocument();
    });

    it('auto-selects all on mount when none selected (divergence: no manual default)', async () => {
        const onChange = vi.fn();
        render(<ProfileSelector profiles={['low', 'medium']} selectedProfiles={[]} onChange={onChange} profileData={null} />);
        expect(onChange).toHaveBeenCalledWith(['low', 'medium']);
    });

    it('does not auto-select when something already selected', () => {
        const onChange = vi.fn();
        render(<ProfileSelector profiles={['low', 'medium']} selectedProfiles={['low']} onChange={onChange} profileData={null} />);
        expect(onChange).not.toHaveBeenCalled();
    });

    it('toggles a profile off when clicked', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ProfileSelector profiles={['low', 'medium']} selectedProfiles={['low', 'medium']} onChange={onChange} profileData={null} />);
        await user.click(screen.getByText('low'));
        expect(onChange).toHaveBeenCalledWith(['medium']);
    });

    it('toggles an unselected profile on when clicked', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ProfileSelector profiles={['low', 'medium']} selectedProfiles={['low']} onChange={onChange} profileData={null} />);
        await user.click(screen.getByText('medium'));
        expect(onChange).toHaveBeenCalledWith(['low', 'medium']);
    });

    it('blocks deselecting the last remaining profile', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ProfileSelector profiles={['low', 'medium']} selectedProfiles={['low']} onChange={onChange} profileData={null} />);
        await user.click(screen.getByText('low'));
        expect(onChange).not.toHaveBeenCalled();
    });

    it('SELECT ALL fires with all profiles when not all selected', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(<ProfileSelector profiles={['low', 'medium']} selectedProfiles={['low']} onChange={onChange} profileData={null} />);
        await user.click(screen.getByText('SELECT ALL'));
        expect(onChange).toHaveBeenCalledWith(['low', 'medium']);
    });

    it('SELECT ALL disabled when all selected', () => {
        render(<ProfileSelector profiles={['low', 'medium']} selectedProfiles={['low', 'medium']} onChange={() => {}} profileData={null} />);
        expect(screen.getByText('SELECT ALL')).toBeDisabled();
    });
});
