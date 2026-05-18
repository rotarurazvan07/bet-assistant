interface OddsMovementIndicatorProps {
    direction: 'up' | 'down' | 'stable' | null | undefined;
    size?: 'sm' | 'md';
}

export function OddsMovementIndicator({ direction, size = 'sm' }: OddsMovementIndicatorProps) {
    if (!direction || direction === 'stable') return null;

    const isUp = direction === 'up';
    const sz = size === 'sm' ? 'w-3.5 h-3.5' : 'w-5 h-5';

    return (
        <span
            className={`inline-flex items-center justify-center ml-1 rounded-full font-bold ${
                isUp
                    ? 'text-emerald-400 bg-emerald-400/15'
                    : 'text-red-400 bg-red-400/15'
            } ${size === 'sm' ? 'p-0.5' : 'p-1'}`}
            title={isUp ? 'Odds rising (drifting)' : 'Odds dropping (shortening)'}
        >
            <svg className={sz} viewBox="0 0 20 20" fill="currentColor">
                {isUp ? (
                    <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                ) : (
                    <path fillRule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clipRule="evenodd" />
                )}
            </svg>
        </span>
    );
}

export default OddsMovementIndicator;