/**
 * CooldownIndicator Component
 * Shows when an API/service is in cooldown mode with countdown timer
 */

import React from 'react';
import { useCooldownTimer } from '../../hooks/useNexusHealth';
import './CooldownIndicator.css';

interface CooldownIndicatorProps {
    /** Service identifier (e.g., 'nba_api', '/aegis/simulate/{player_id}') */
    service: string;
    /** Display variant */
    variant?: 'badge' | 'banner' | 'inline';
    /** Custom message */
    message?: string;
    /** Show countdown timer */
    showTimer?: boolean;
}

export const CooldownIndicator: React.FC<CooldownIndicatorProps> = ({
    service,
    variant = 'badge',
    message,
    showTimer = true
}) => {
    const { inCooldown, formattedRemaining } = useCooldownTimer(service);

    if (!inCooldown) return null;

    const defaultMessage = 'Rate limited - using cached data';

    if (variant === 'banner') {
        return (
            <div className="cooldown-banner">
                <div className="banner-icon">⏸</div>
                <div className="banner-content">
                    <div className="banner-title">Service Cooldown</div>
                    <div className="banner-message">
                        {message || defaultMessage}
                    </div>
                    {showTimer && (
                        <div className="banner-timer">
                            Resumes in {formattedRemaining}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    if (variant === 'inline') {
        return (
            <span className="cooldown-inline">
                <span className="inline-icon">⏸</span>
                <span className="inline-text">
                    Cooldown {showTimer && `(${formattedRemaining})`}
                </span>
            </span>
        );
    }

    // Default: badge variant
    return (
        <div className="cooldown-badge-container">
            <div className="cooldown-badge">
                <span className="badge-icon">⏸</span>
                <span className="badge-text">COOLDOWN</span>
                {showTimer && (
                    <span className="badge-timer">{formattedRemaining}</span>
                )}
            </div>
            {message && (
                <div className="cooldown-tooltip">{message}</div>
            )}
        </div>
    );
};

/**
 * Source indicator showing where data came from
 */
interface DataSourceBadgeProps {
    source: 'live' | 'cache' | 'stale' | 'fallback' | 'timeout';
    executionTimeMs?: number;
    lateArrivalPending?: boolean;
}

export const DataSourceBadge: React.FC<DataSourceBadgeProps> = ({
    source,
    executionTimeMs,
    lateArrivalPending = false
}) => {
    const getSourceInfo = () => {
        switch (source) {
            case 'live':
                return { icon: '⚡', label: 'LIVE', color: 'green' };
            case 'cache':
                return { icon: '💾', label: 'CACHED', color: 'blue' };
            case 'stale':
                return { icon: '⏳', label: 'STALE', color: 'yellow' };
            case 'fallback':
                return { icon: '🔄', label: 'FALLBACK', color: 'orange' };
            case 'timeout':
                return { icon: '⏱', label: 'TIMEOUT', color: 'red' };
            default:
                return { icon: '?', label: 'UNKNOWN', color: 'gray' };
        }
    };

    const { icon, label, color } = getSourceInfo();

    return (
        <div className={`data-source-badge source-${color}`}>
            <span className="source-icon">{icon}</span>
            <span className="source-label">{label}</span>
            {executionTimeMs !== undefined && (
                <span className="source-time">{executionTimeMs}ms</span>
            )}
            {lateArrivalPending && (
                <span className="late-arrival-indicator" title="Live data coming soon">
                    <span className="pulse-dot"></span>
                </span>
            )}
        </div>
    );
};

/**
 * Shadow-Race status indicator
 */
interface ShadowRaceStatusProps {
    patientResult: {
        source: 'live' | 'cache' | 'timeout' | 'error';
        lateArrivalPending: boolean;
        executionTimeMs: number;
    };
}

export const ShadowRaceStatus: React.FC<ShadowRaceStatusProps> = ({ patientResult }) => {
    const { source, lateArrivalPending, executionTimeMs } = patientResult;

    return (
        <div className="shadow-race-status">
            <DataSourceBadge
                source={source}
                executionTimeMs={executionTimeMs}
                lateArrivalPending={lateArrivalPending}
            />
            {lateArrivalPending && (
                <div className="late-arrival-text">
                    Showing cached data · Live update coming...
                </div>
            )}
        </div>
    );
};

export default CooldownIndicator;
