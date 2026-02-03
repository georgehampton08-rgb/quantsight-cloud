/**
 * useNexusHealth Hook
 * React hook for monitoring Nexus Hub health and cooldown states
 * 
 * Features:
 * - Auto-refresh health status
 * - Cooldown monitoring
 * - Service availability checks
 * - Loading and error states
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { NexusApi, SystemHealth, ActiveCooldowns, NexusOverview, HealthStatus } from '../services/nexusApi';

// =============================================================================
// Types
// =============================================================================

export interface UseNexusHealthOptions {
    /** Auto-refresh interval in milliseconds (default: 30000 = 30s) */
    refreshInterval?: number;
    /** Enable auto-refresh (default: true) */
    autoRefresh?: boolean;
    /** Fetch full overview instead of just health (default: false) */
    fullOverview?: boolean;
}

export interface NexusHealthState {
    health: SystemHealth | null;
    overview: NexusOverview | null;
    cooldowns: ActiveCooldowns | null;
    loading: boolean;
    error: string | null;
    lastUpdated: Date | null;
}

export interface UseNexusHealthReturn extends NexusHealthState {
    /** Manually refresh health data */
    refresh: () => Promise<void>;
    /** Check if a specific service is available */
    isServiceAvailable: (service: string) => boolean;
    /** Check if a specific service is in cooldown */
    isInCooldown: (service: string) => boolean;
    /** Get remaining cooldown seconds for a service */
    getCooldownRemaining: (service: string) => number;
    /** Get overall system status summary */
    getStatusSummary: () => {
        status: HealthStatus;
        healthy: number;
        degraded: number;
        down: number;
        cooldown: number;
    };
}

// =============================================================================
// Hook Implementation
// =============================================================================

export const useNexusHealth = (options: UseNexusHealthOptions = {}): UseNexusHealthReturn => {
    const {
        refreshInterval = 30000,
        autoRefresh = true,
        fullOverview = false
    } = options;

    const [state, setState] = useState<NexusHealthState>({
        health: null,
        overview: null,
        cooldowns: null,
        loading: true,
        error: null,
        lastUpdated: null
    });

    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    // Fetch health data
    const refresh = useCallback(async () => {
        setState(prev => ({ ...prev, loading: true, error: null }));

        try {
            if (fullOverview) {
                const overview = await NexusApi.getOverview();
                setState(prev => ({
                    ...prev,
                    overview,
                    health: overview.health,
                    loading: false,
                    lastUpdated: new Date()
                }));
            } else {
                const [health, cooldowns] = await Promise.all([
                    NexusApi.getHealth(),
                    NexusApi.getCooldowns()
                ]);
                setState(prev => ({
                    ...prev,
                    health,
                    cooldowns,
                    loading: false,
                    lastUpdated: new Date()
                }));
            }
        } catch (error: any) {
            console.error('[useNexusHealth] Fetch failed:', error);
            setState(prev => ({
                ...prev,
                loading: false,
                error: error.message || 'Failed to fetch Nexus health'
            }));
        }
    }, [fullOverview]);

    // Auto-refresh effect
    useEffect(() => {
        // Initial fetch
        refresh();

        // Setup interval if auto-refresh enabled
        if (autoRefresh && refreshInterval > 0) {
            intervalRef.current = setInterval(refresh, refreshInterval);
        }

        // Cleanup
        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [refresh, autoRefresh, refreshInterval]);

    // Check if service is available
    const isServiceAvailable = useCallback((service: string): boolean => {
        if (!state.health) return true; // Assume available if no data

        // Check core services
        if (state.health.core[service]) {
            return state.health.core[service].available;
        }
        // Check external services
        if (state.health.external[service]) {
            return state.health.external[service].available;
        }
        // Check components
        if (state.health.components[service]) {
            return state.health.components[service].available;
        }

        return true; // Unknown service - assume available
    }, [state.health]);

    // Check if service is in cooldown
    const isInCooldown = useCallback((service: string): boolean => {
        if (!state.cooldowns || !state.cooldowns.active_cooldowns) return false;
        return service in state.cooldowns.active_cooldowns;
    }, [state.cooldowns]);

    // Get remaining cooldown seconds
    const getCooldownRemaining = useCallback((service: string): number => {
        if (!state.cooldowns || !state.cooldowns.active_cooldowns) return 0;
        const info = state.cooldowns.active_cooldowns[service];
        return info ? info.remaining_seconds : 0;
    }, [state.cooldowns]);

    // Get status summary
    const getStatusSummary = useCallback(() => {
        const summary = {
            status: (state.health?.overall || 'healthy') as HealthStatus,
            healthy: 0,
            degraded: 0,
            down: 0,
            cooldown: 0
        };

        if (!state.health) return summary;

        const countStatus = (services: Record<string, any>) => {
            Object.values(services).forEach((svc: any) => {
                switch (svc.status) {
                    case 'healthy': summary.healthy++; break;
                    case 'degraded': summary.degraded++; break;
                    case 'down': summary.down++; break;
                    case 'cooldown': summary.cooldown++; break;
                }
            });
        };

        countStatus(state.health.core);
        countStatus(state.health.external);
        countStatus(state.health.components);

        return summary;
    }, [state.health]);

    return {
        ...state,
        refresh,
        isServiceAvailable,
        isInCooldown,
        getCooldownRemaining,
        getStatusSummary
    };
};

// =============================================================================
// Convenience Hooks
// =============================================================================

/**
 * Simple hook to check if NBA API is available
 */
export const useNbaApiAvailable = (): boolean => {
    const { isServiceAvailable, isInCooldown } = useNexusHealth({ refreshInterval: 10000 });
    return isServiceAvailable('nba_api') && !isInCooldown('nba_api');
};

/**
 * Hook for monitoring cooldown countdown
 */
export const useCooldownTimer = (service: string): {
    inCooldown: boolean;
    remaining: number;
    formattedRemaining: string;
} => {
    const { isInCooldown, getCooldownRemaining } = useNexusHealth({ refreshInterval: 1000 });
    const remaining = getCooldownRemaining(service);

    const formatTime = (seconds: number): string => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        if (mins > 0) return `${mins}m ${secs}s`;
        return `${secs}s`;
    };

    return {
        inCooldown: isInCooldown(service),
        remaining,
        formattedRemaining: formatTime(remaining)
    };
};

export default useNexusHealth;
