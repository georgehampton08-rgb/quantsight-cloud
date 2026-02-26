/**
 * ApiContract Layer (Phase 1A)
 * Centralized transport router for Electron IPC, Web Fetch, and Fallback policies.
 */

// Opt-in switch for fallback when Electron IPC lacks specific mappings (e.g., Aegis/Nexus)
export const ALLOW_WEB_FALLBACK_IN_ELECTRON = true;

// Hardcoded fallback for now, but configured cleanly for env override
const FALLBACK_BASE_URL = 'https://quantsight-cloud-458498663186.us-central1.run.app';
const VITE_API_URL = import.meta.env?.VITE_API_URL || FALLBACK_BASE_URL;
const VITE_PULSE_API_URL = import.meta.env?.VITE_PULSE_API_URL || 'https://quantsight-pulse-458498663186.us-central1.run.app';

// Track if we've already warned about fallback to avoid console/toast spam
let hasWarnedFallbackSession = false;

export class OfflineFallbackFailedError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'OfflineFallbackFailedError';
    }
}

export type TransportMode = 'ipc' | 'web';

export interface ApiResponse<T> {
    data: T;
    _meta: {
        transport: TransportMode;
        requestId?: string;
        timestamp: number;
    };
}

export interface WebSpec {
    path: string;
    options?: RequestInit;
}

export const ApiContract = {
    /**
     * Executes a request safely, determining transport based on environment and availability.
     */
    async execute<T>(ipcMethod: string | null, webSpec: WebSpec, args: any[] = []): Promise<ApiResponse<T>> {
        const _meta = { timestamp: Date.now() } as any;

        // 1. Try IPC Direct mapping
        if (ipcMethod && window.electronAPI && typeof (window.electronAPI as any)[ipcMethod] === 'function') {
            try {
                const data = await (window.electronAPI as any)[ipcMethod](...args);
                _meta.transport = 'ipc';
                return { data, _meta };
            } catch (error) {
                console.error(`[ApiContract] IPC method '${ipcMethod}' failed:`, error);
                throw error;
            }
        }

        // 2. Validate Fallback Guards if inside Electron
        if (window.electronAPI) {
            if (!ALLOW_WEB_FALLBACK_IN_ELECTRON) {
                throw new Error(`[ApiContract] Desktop mode expects parity. No IPC mapping for '${ipcMethod}'. Fallback Disabled.`);
            }
            if (!hasWarnedFallbackSession) {
                console.warn(`[ApiContract] Desktop is using Cloud fallback for missing IPC method '${ipcMethod || 'unknown'}' (Path: ${webSpec.path})`);

                // Fire telemetry to Vanguard so we can monitor IPC deterioration without the user noticing
                fetch(`${VITE_API_URL}/vanguard/telemetry/ipc-fallback`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        missingMethod: ipcMethod,
                        path: webSpec.path,
                        timestamp: Date.now()
                    })
                }).catch(() => { /* Silent failure for telemetry */ });

                hasWarnedFallbackSession = true;
            }
        }

        // 3. Fallback to Web Protocol
        try {
            const data = await ApiContract.executeWeb<T>(webSpec);
            _meta.transport = 'web';
            return { data, _meta };
        } catch (error) {
            if (window.electronAPI) {
                console.warn(`[ApiContract] Web Fallback failed for ${webSpec.path}. Network may be offline. Swallowing error and holding until SSE buffer reconnects.`);
                // Return a never-resolving promise to hold the UI pending state without crashing
                return new Promise<ApiResponse<T>>(() => { });
            }
            throw error;
        }
    },

    /**
     * Raw web fetcher.
     */
    async executeWeb<T>(spec: WebSpec): Promise<T> {
        const cleanPath = spec.path.startsWith('/') ? spec.path.substring(1) : spec.path;
        const res = await fetch(`${VITE_API_URL}/${cleanPath}`, spec.options);
        if (!res.ok) {
            throw new Error(`HTTP Error ${res.status}: ${res.statusText}`);
        }
        return res.json();
    },

    /**
     * Specialized execution pathway specifically for Live Pulse streams.
     * Hard-wires the request to VITE_PULSE_API_URL instead of the standard URL
     * since main API instances no longer serve long-lived 503 connections.
     */
    async pulse<T>(spec: WebSpec): Promise<T> {
        const cleanPath = spec.path.startsWith('/') ? spec.path.substring(1) : spec.path;
        console.log(`[ApiContract] Routing Pulse Request to: ${VITE_PULSE_API_URL}/${cleanPath}`);
        const res = await fetch(`${VITE_PULSE_API_URL}/${cleanPath}`, spec.options);
        if (!res.ok) {
            throw new Error(`Pulse Error ${res.status}: ${res.statusText}`);
        }
        return res.json();
    },

    /**
     * Shadow Race Caching Strategy.
     * Preserves exact original behavior, including `nexus:late-arrival` emission down to the millisecond logic.
     */
    async executeShadowRace<T>(
        livePath: string,
        cachePath: string,
        patienceMs: number = 800,
        ipcMethodLive: string | null = null,
        argsLive: any[] = []
    ): Promise<any> {
        const startTime = Date.now();
        const requestId = `sr_${startTime}_${Math.random().toString(36).slice(2, 8)}`;

        // Map live execution through our main executor
        const liveRequest = ApiContract.execute<T>(ipcMethodLive, { path: livePath }, argsLive).then(res => res.data);

        const timeoutPromise = new Promise<never>((_, reject) => {
            setTimeout(() => reject(new Error('PATIENCE_EXCEEDED')), patienceMs);
        });

        try {
            const data = await Promise.race([liveRequest, timeoutPromise]);
            return {
                data,
                source: 'live',
                lateArrivalPending: false,
                executionTimeMs: Date.now() - startTime,
                requestId
            };
        } catch (error: any) {
            if (error.message === 'PATIENCE_EXCEEDED') {
                console.log(`[ShadowRace] Patience ${patienceMs}ms exceeded`);

                // Keep live running, emit event when it lands
                liveRequest
                    .then(lateData => {
                        console.log(`[ShadowRace] Late arrival for ${requestId}`);
                        // Explicitly PRESERVING unconsumed event for future architecture/devtools
                        window.dispatchEvent(new CustomEvent('nexus:late-arrival', {
                            detail: { requestId, data: lateData, delayMs: Date.now() - startTime }
                        }));
                    })
                    .catch(e => console.warn('[ShadowRace] Background live request failed', e));

                // Try optimistic cache grab
                try {
                    const cacheData = await ApiContract.executeWeb<T>({ path: cachePath });
                    return {
                        data: cacheData,
                        source: 'cache',
                        lateArrivalPending: true,
                        executionTimeMs: Date.now() - startTime,
                        requestId
                    };
                } catch (cacheError) {
                    if (window.electronAPI) {
                        console.warn(`[ApiContract] Shadow Race Cache Web Fallback failed. Swallowing error and holding until SSE buffer reconnects.`);
                        return new Promise<any>(() => { });
                    }
                    return {
                        data: null,
                        source: 'timeout',
                        lateArrivalPending: true,
                        executionTimeMs: Date.now() - startTime,
                        error: 'Simulation timed out - cache unreadable',
                        requestId
                    };
                }
            }

            // Hard fatal error (not timeout)
            return {
                data: null,
                source: 'error',
                lateArrivalPending: false,
                executionTimeMs: Date.now() - startTime,
                error: error.message,
                requestId
            };
        }
    }
};

/**
 * Normalizers (Shape Stabilizers)
 * Safely normalizes key drift to prevent frontend prop rendering errors.
 * Strictly avoids mutating existing shapes or nesting levels if not necessary.
 */
export const Normalizers = {
    profile: (raw: any) => {
        if (!raw) return raw;
        const safe = { ...raw };

        // Stabilize Identity
        if (safe.playerId && !safe.id) safe.id = safe.playerId;
        if (safe.player_id && !safe.id) safe.id = safe.player_id;

        // Stabilize Arrays
        if (safe.stats) {
            if (safe.stats.trend === null || safe.stats.trend === undefined) {
                safe.stats.trend = [];
            }
        }

        return safe;
    },

    simulation: (raw: any) => {
        if (!raw) return raw;
        const safe = { ...raw };

        // Stabilize simulation value properties (ev -> expected_value)
        if (safe.ev && !safe.expected_value) safe.expected_value = safe.ev;

        return safe;
    },

    vanguardIncidentList: (rawArray: any[]) => {
        if (!Array.isArray(rawArray)) return [];
        return rawArray.map(item => {
            const safeItem = { ...item };
            // Incident anomaly tracking only
            if (safeItem.count !== undefined && safeItem.occurrence_count === undefined) {
                safeItem.occurrence_count = safeItem.count;
            }
            return safeItem;
        });
    }
};
