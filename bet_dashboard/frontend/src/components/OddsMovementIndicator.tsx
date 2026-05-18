import React from 'react';
import type { OddsMovementDirection } from '../types';

interface OddsMovementIndicatorProps {
    direction?: OddsMovementDirection;
    size?: 'sm' | 'md';
}

export const OddsMovementIndicator: React.FC<OddsMovementIndicatorProps> = ({
    direction,
    size = 'sm',
}) => {
    if (!direction || direction === 'stable') {
        return null;
    }

    const sizeClasses = size === 'sm' ? 'w-3 h-3' : 'w-4 h-4';

    if (direction === 'up') {
        return (
            <span
                className={`inline-flex items-center text-green-500 ${sizeClasses}`}
                title="Odds increased"
            >
                <svg
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-full h-full"
                >
                    <path
                        fillRule="evenodd"
                        d="M10 17a.75.75 0 01-.75-.75V5.612L5.29 9.77a.75.75 0 01-1.08-1.04l5.25-5.5a.75.75 0 011.08 0l5.25 5.5a.75.75 0 11-1.08 1.04l-3.96-4.158V16.25A.75.75 0 0110 17z"
                        clipRule="evenodd"
                    />
                </svg>
            </span>
        );
    }

    if (direction === 'down') {
        return (
            <span
                className={`inline-flex items-center text-red-500 ${sizeClasses}`}
                title="Odds decreased"
            >
                <svg
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-full h-full"
                >
                    <path
                        fillRule="evenodd"
                        d="M10 3a.75.75 0 01.75.75v10.638l3.96-4.158a.75.75 0 111.08 1.04l-5.25 5.5a.75.75 0 01-1.08 0l-5.25-5.5a.75.75 0 01-1.08-1.04l3.96 4.158V3.75A.75.75 0 0110 3z"
                        clipRule="evenodd"
                    />
                </svg>
            </span>
        );
    }

    return null;
};

export default OddsMovementIndicator;