/**
 * useNexusHealth Hook
 * React hook for monitoring Nexus Hub health and cooldown states
 * 
 * NOTE: No nexusApi.ts service file exists.
 * Nexus module is offline (FEATURE_NEXUS_ENABLED = false).
 * following Dead Code Cleanup session.
 * Stub detection applied directly per Phase 1 wiring plan.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// =============================================================================
// Stubbed Types (formerly exported from nexusApi.ts)
// =============================================================================
export type HealthStatus = 'healthy' | 'degraded' | 'down' | 'cooldown';

export interface ServiceHealth {
    status: HealthStatus;
    latency_ms?: number;
    last_check?: string;
    message?: string;
    available?: boolean;
}

export interface SystemHealth {
    overall: HealthStatus;
    last_updated: string;
    uptime_seconds: number;
    version: string;
    core: { [service: string]: ServiceHealth };
    external: { [service: string]: ServiceHealth };
    components: { [component: string]: ServiceHealth };
}

export interface CooldownInfo {
    active: boolean;
    started_at: string;
    expires_at: string;
    remaining_seconds: number;
    reason: string;
    type: string;
}

export interface ActiveCooldowns {
    active_cooldowns: { [key: string]: CooldownInfo };
    count: number;
    last_checked: string;
    degraded?: boolean;
}

export interface EndpointRoute {
    path: string;
    handler: string;
    methods: string[];
    cooldown_policy?: string;
}

export interface NexusOverview {
    health: SystemHealth;
    cooldown_summary: { active: number };
    routing_matrix: { endpoints: EndpointRoute[] };
}

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

    // Fetch health data (STUBBED out per Phase 1)
    const refresh = useCallback(async () => {
        setState(prev => ({ ...prev, loading: true, error: null }));

        // Nexus is disabled via FEATURE_NEXUS_ENABLED = false
        // Return a static degraded state immediately
        const stubDate = new Date();
        const stubHealth: SystemHealth = {
            overall: 'degraded',
            last_updated: stubDate.toISOString(),
            uptime_seconds: 0,
            version: 'offline-stub',
            core: {},
            external: {},
            components: {}
        };
        const stubCooldowns: ActiveCooldowns = {
            active_cooldowns: {},
            count: 0,
            last_checked: stubDate.toISOString(),
            degraded: true,
        };
        const stubOverview: NexusOverview = {
            health: stubHealth,
            cooldown_summary: { active: 0 },
            routing_matrix: { endpoints: [] }
        };

        if (fullOverview) {
            setState(prev => ({
                ...prev,
                overview: stubOverview,
                health: stubHealth,
                loading: false,
                lastUpdated: stubDate
            }));
        } else {
            setState(prev => ({
                ...prev,
                health: stubHealth,
                cooldowns: stubCooldowns,
                loading: false,
                lastUpdated: stubDate
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
