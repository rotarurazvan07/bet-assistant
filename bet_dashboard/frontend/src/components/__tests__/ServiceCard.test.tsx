// ServiceCard (issue #64 P1). ACTUAL: active = alive && enabled;
// 'Stop/Start Service' button; 'Last Generated' footer (generator only,
// 'Never' fallback); icons puller/generator/verifier; NO next-run estimate
// (cycle-12 divergence).

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ServiceCard from '../ServiceCard';
import { makeServiceInfo } from '../../test/factories';


describe('ServiceCard', () => {
    it('shows Running badge when alive && enabled', () => {
        render(<ServiceCard info={makeServiceInfo()} onToggle={() => {}} />);
        expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('shows Stopped badge when enabled but not alive', () => {
        render(<ServiceCard info={makeServiceInfo({ alive: false })} onToggle={() => {}} />);
        expect(screen.getByText('Stopped')).toBeInTheDocument();
    });

    it('shows Stopped badge when alive but disabled', () => {
        render(<ServiceCard info={makeServiceInfo({ enabled: false })} onToggle={() => {}} />);
        expect(screen.getByText('Stopped')).toBeInTheDocument();
    });

    it('active card shows Stop Service button and fires onToggle', async () => {
        const user = userEvent.setup();
        const onToggle = vi.fn();
        render(<ServiceCard info={makeServiceInfo()} onToggle={onToggle} />);
        await user.click(screen.getByText('Stop Service'));
        expect(onToggle).toHaveBeenCalledTimes(1);
    });

    it('inactive card shows Start Service button', () => {
        render(<ServiceCard info={makeServiceInfo({ enabled: false })} onToggle={() => {}} />);
        expect(screen.getByText('Start Service')).toBeInTheDocument();
    });

    it('generator footer shows formatted Last Generated', () => {
        render(<ServiceCard info={makeServiceInfo({ name: 'generator', last_time_generated: '2026-09-24T09:30:00' })} onToggle={() => {}} />);
        expect(screen.getByText('Last Generated')).toBeInTheDocument();
        expect(screen.getByText(/24\/09/)).toBeInTheDocument();
    });

    it('generator footer shows Never when last_time_generated null', () => {
        render(<ServiceCard info={makeServiceInfo({ name: 'generator', last_time_generated: null })} onToggle={() => {}} />);
        expect(screen.getByText('Never')).toBeInTheDocument();
    });

    it('non-generator services have no Last Generated footer', () => {
        render(<ServiceCard info={makeServiceInfo({ name: 'puller' })} onToggle={() => {}} />);
        expect(screen.queryByText('Last Generated')).not.toBeInTheDocument();
    });

    it('renders per-service icons (puller ⬇ generator ✦ verifier ⟳)', () => {
        const { unmount } = render(<ServiceCard info={makeServiceInfo({ name: 'puller' })} onToggle={() => {}} />);
        expect(screen.getByText('⬇')).toBeInTheDocument();
        unmount();
        render(<ServiceCard info={makeServiceInfo({ name: 'verifier' })} onToggle={() => {}} />);
        expect(screen.getByText('⟳')).toBeInTheDocument();
    });
});
