/**
 * Nexus Hub API Service
 * Frontend interface for the Nexus Hub API Supervisor
 * 
 * Features:
 * - System overview and health monitoring
 * - Cooldown mode management
 * - Routing recommendations
 * - Late arrival handling via polling
 */

import { API_BASE } from '../config/apiConfig';

// Admin key - in production, this would be handled differently
const NEXUS_ADMIN_KEY = 'nexus_dev_key_2024';


// =============================================================================
// Types
// =============================================================================

export type HealthStatus = 'healthy' | 'degraded' | 'critical' | 'down' | 'cooldown';
export type RouteStrategy = 'direct' | 'managed' | 'fallback' | 'cooldown' | 'degraded';
export type DataSource = 'live' | 'cache' | 'fallback' | 'stale';

export interface ServiceHealth {
    name: string;
    status: HealthStatus;
    last_check: string;
    error_count: number;
    last_error: string | null;
    cooldown_until: string | null;
    response_time_ms: number | null;
    available: boolean;
}

export interface SystemHealth {
    overall: HealthStatus;
    core: Record<string, ServiceHealth>;
    external: Record<string, ServiceHealth>;
    components: Record<string, ServiceHealth>;
    cooldowns: Record<string, string>;
    timestamp: string;
}

export interface EndpointStats {
    total_endpoints: number;
    by_category: Record<string, {
        count: number;
        paths: string[];
        avg_complexity: number;
    }>;
    with_fallback: number;
    high_complexity: number;
    phase: string;
}

export interface RoutingStats {
    total_routes: number;
    direct_routes: number;
    managed_routes: number;
    fallback_routes: number;
    cooldown_routes: number;
    direct_rate: number;
    managed_rate: number;
    fallback_rate: number;
    shadow_race_stats: {
        total_requests: number;
        cache_served: number;
        live_served: number;
        late_arrivals: number;
        failures: number;
        cache_hit_rate: number;
        live_hit_rate: number;
        failure_rate: number;
        pending_requests: number;
    };
}

export interface QueueStats {
    total_submitted: number;
    total_completed: number;
    total_failed: number;
    by_priority: Record<string, number>;
    queue_depth: {
        total_pending: number;
        running: number;
        completed: number;
    };
    success_rate: number;
}

export interface ErrorStats {
    total_errors: number;
    by_code: Record<string, number>;
    by_category: Record<string, number>;
    recent_errors: Array<{
        code: string;
        message: string;
        endpoint: string;
        timestamp: string;
    }>;
}

export interface NexusOverview {
    status: string;
    uptime_seconds: number;
    endpoints: EndpointStats;
    health: SystemHealth;
    routing: RoutingStats;
    queue: QueueStats;
    errors: ErrorStats;
    timestamp: string;
}

export interface RouteDecision {
    strategy: RouteStrategy;
    target: string;
    timeout_ms: number;
    use_shadow_race: boolean;
    patience_threshold_ms: number;
    fallback: string | null;
    reason: string;
    priority: string;
    timestamp: string;
}

export interface CooldownInfo {
    expires: string;
    remaining_seconds: number;
}

export interface ActiveCooldowns {
    active_cooldowns: Record<string, CooldownInfo>;
    count: number;
}

export interface RouteMatrix {
    endpoints: Array<{
        path: string;
        category: string;
        complexity: number;
        recommended_strategy: RouteStrategy;
        timeout_ms: number;
        use_shadow_race: boolean;
        has_fallback: boolean;
    }>;
    count: number;
}

export interface LateArrival {
    request_id: string;
    endpoint: string;
    data: any;
    delay_ms: number;
}

export interface NexusError {
    code: string;
    message: string;
    endpoint: string;
    http_status: number;
    details: Record<string, any> | null;
    recovery_action: string | null;
    fallback_available: boolean;
    cooldown_seconds: number;
    timestamp: string;
}

// =============================================================================
// Helper Functions
// =============================================================================

import { ApiContract } from '../api/client';

const nexusExecute = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
    const res = await ApiContract.execute<T>(null, {
        path: path.startsWith('/') ? path.substring(1) : path,
        options: {
            ...options,
            headers: {
                'X-Admin-Key': NEXUS_ADMIN_KEY,
                'Content-Type': 'application/json',
                ...options.headers
            }
        }
    });
    return res.data;
};

// =============================================================================
// API Functions
// =============================================================================

export const NexusApi = {
    /**
     * Get complete Nexus Hub system overview
     */
    getOverview: async (): Promise<NexusOverview> => {
        try {
            return await nexusExecute<NexusOverview>('nexus/overview');
        } catch (error) {
            console.error('[Nexus] Overview failed:', error);
            throw error;
        }
    },

    /**
     * Get unified system health with cooldown status
     */
    getHealth: async (): Promise<SystemHealth> => {
        try {
            return await nexusExecute<SystemHealth>('nexus/health');
        } catch (error) {
            console.error('[Nexus] Health check failed:', error);
            throw error;
        }
    },

    /**
     * Get active cooldown states
     */
    getCooldowns: async (): Promise<ActiveCooldowns> => {
        try {
            return await nexusExecute<ActiveCooldowns>('nexus/cooldowns');
        } catch (error) {
            console.error('[Nexus] Cooldowns fetch failed:', error);
            throw error;
        }
    },

    /**
     * Get routing matrix for all endpoints
     */
    getRouteMatrix: async (): Promise<RouteMatrix> => {
        try {
            return await nexusExecute<RouteMatrix>('nexus/route-matrix');
        } catch (error) {
            console.error('[Nexus] Route matrix failed:', error);
            throw error;
        }
    },

    /**
     * Get routing recommendation for a specific path
     */
    getRouteRecommendation: async (path: string): Promise<RouteDecision> => {
        try {
            const cleanPath = path.startsWith('/') ? path.slice(1) : path;
            return await nexusExecute<RouteDecision>(`nexus/recommend/${cleanPath}`);
        } catch (error) {
            console.error('[Nexus] Route recommendation failed:', error);
            throw error;
        }
    },

    /**
     * Manually put a service in cooldown mode
     */
    enterCooldown: async (service: string, duration: number = 60): Promise<{ status: string; message: string }> => {
        try {
            return await nexusExecute<{ status: string; message: string }>(`nexus/cooldown/${encodeURIComponent(service)}?duration=${duration}`, {
                method: 'POST'
            });
        } catch (error) {
            console.error('[Nexus] Enter cooldown failed:', error);
            throw error;
        }
    },

    /**
     * Manually exit a service from cooldown mode
     */
    exitCooldown: async (service: string): Promise<{ status: string; message: string }> => {
        try {
            return await nexusExecute<{ status: string; message: string }>(`nexus/cooldown/${encodeURIComponent(service)}`, {
                method: 'DELETE'
            });
        } catch (error) {
            console.error('[Nexus] Exit cooldown failed:', error);
            throw error;
        }
    },

    /**
     * Check if service is in cooldown
     */
    isInCooldown: async (service: string): Promise<boolean> => {
        try {
            const cooldowns = await NexusApi.getCooldowns();
            return service in cooldowns.active_cooldowns;
        } catch {
            return false;
        }
    },

    /**
     * Get remaining cooldown seconds for a service
     */
    getCooldownRemaining: async (service: string): Promise<number> => {
        try {
            const cooldowns = await NexusApi.getCooldowns();
            const info = cooldowns.active_cooldowns[service];
            return info ? info.remaining_seconds : 0;
        } catch {
            return 0;
        }
    }
};

// =============================================================================
// Shadow-Race Pattern Support
// =============================================================================

/**
 * Result from Shadow-Race execution
 */
export interface ShadowRaceResult<T> {
    data: T | null;
    source: DataSource;
    lateArrivalPending: boolean;
    executionTimeMs: number;
    error?: string;
    requestId?: string;
}

/**
 * Execute a request with Shadow-Race pattern
 * Returns cached data quickly while live continues in background
 */
export const executeShadowRace = async <T>(
    liveRequest: () => Promise<T>,
    cacheRequest: () => Promise<T>,
    patienceMs: number = 800
): Promise<ShadowRaceResult<T>> => {
    const startTime = Date.now();
    const requestId = `sr_${startTime}_${Math.random().toString(36).slice(2, 8)}`;

    // Create race between live request and timeout
    const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('PATIENCE_EXCEEDED')), patienceMs);
    });

    try {
        // Try live first with patience timeout
        const data = await Promise.race([liveRequest(), timeoutPromise]);
        return {
            data,
            source: 'live',
            lateArrivalPending: false,
            executionTimeMs: Date.now() - startTime,
            requestId
        };
    } catch (error: any) {
        if (error.message === 'PATIENCE_EXCEEDED') {
            // Patience exceeded - serve cache, live continues in background
            console.log('[ShadowRace] Patience exceeded, serving cache');

            // Don't await live - let it complete in background
            liveRequest()
                .then(lateData => {
                    console.log(`[ShadowRace] Late arrival for ${requestId}`, lateData);
                    // Emit event for real-time updates
                    window.dispatchEvent(new CustomEvent('nexus:late-arrival', {
                        detail: { requestId, data: lateData }
                    }));
                })
                .catch(err => {
                    console.warn(`[ShadowRace] Live request failed: ${err}`);
                });

            try {
                const cacheData = await cacheRequest();
                return {
                    data: cacheData,
                    source: 'cache',
                    lateArrivalPending: true,
                    executionTimeMs: Date.now() - startTime,
                    requestId
                };
            } catch (cacheError: any) {
                return {
                    data: null,
                    source: 'fallback',
                    lateArrivalPending: false,
                    executionTimeMs: Date.now() - startTime,
                    error: `Both live and cache failed: ${cacheError.message}`,
                    requestId
                };
            }
        }

        // Live request failed for other reason
        return {
            data: null,
            source: 'fallback',
            lateArrivalPending: false,
            executionTimeMs: Date.now() - startTime,
            error: error.message,
            requestId
        };
    }
};

// =============================================================================
// Error Handling Utilities
// =============================================================================

/**
 * Parse and enhance error from Nexus API response
 */
export const parseNexusError = (response: any): NexusError | null => {
    if (response?.error) {
        return response.error as NexusError;
    }
    return null;
};

/**
 * Check if we should use fallback based on error
 */
export const shouldUseFallback = (error: NexusError): boolean => {
    return error.fallback_available && !error.cooldown_seconds;
};

/**
 * Get user-friendly error message
 */
export const getUserErrorMessage = (error: NexusError): string => {
    if (error.recovery_action) {
        return `${error.message}. ${error.recovery_action}`;
    }
    return error.message;
};

export default NexusApi;
