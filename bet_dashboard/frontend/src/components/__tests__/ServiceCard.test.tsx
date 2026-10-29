// ServiceCard (issue #64 P1). ACTUAL: active = alive && enabled;
// 'Stop/Start Service' button; icons puller/generator/verifier; NO next-run
// estimate. Issue #95: the 'Last Generated' footer was removed — that info is
// now shown per-profile in the scheduling table, not globally on the card.

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

    it('no Last Generated footer on any card (moved to per-profile table, issue #95)', () => {
        render(<ServiceCard info={makeServiceInfo({ name: 'generator', last_time_generated: '2026-09-24T09:30:00' })} onToggle={() => {}} />);
        expect(screen.queryByText('Last Generated')).not.toBeInTheDocument();
        expect(screen.queryByText('Never')).not.toBeInTheDocument();
    });

    it('renders per-service icons (puller ⬇ generator ✦ verifier ⟳)', () => {
        const { unmount } = render(<ServiceCard info={makeServiceInfo({ name: 'puller' })} onToggle={() => {}} />);
        expect(screen.getByText('⬇')).toBeInTheDocument();
        unmount();
        render(<ServiceCard info={makeServiceInfo({ name: 'verifier' })} onToggle={() => {}} />);
        expect(screen.getByText('⟳')).toBeInTheDocument();
    });
});
