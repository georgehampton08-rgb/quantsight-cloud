/**
 * Prefetch Service
 * Hover-triggered data hydration for instant page loads
 */

import { AegisApi, SimulationResult } from './aegisApi';

// Prefetch cache (in-memory LRU-style)
const prefetchCache = new Map<string, {
    data: any;
    timestamp: number;
    type: 'player' | 'simulation';
}>();

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const MAX_CACHE_SIZE = 50;

/**
 * Clean expired entries from cache
 */
function cleanCache() {
    const now = Date.now();
    for (const [key, value] of prefetchCache.entries()) {
        if (now - value.timestamp > CACHE_TTL_MS) {
            prefetchCache.delete(key);
        }
    }

    // LRU eviction if over size
    if (prefetchCache.size > MAX_CACHE_SIZE) {
        const oldest = [...prefetchCache.entries()]
            .sort((a, b) => a[1].timestamp - b[1].timestamp)[0];
        if (oldest) prefetchCache.delete(oldest[0]);
    }
}

/**
 * Prefetch player profile on hover
 */
export async function prefetchPlayer(playerId: string): Promise<void> {
    const cacheKey = `player:${playerId}`;

    // Skip if already cached
    if (prefetchCache.has(cacheKey)) {
        const cached = prefetchCache.get(cacheKey)!;
        if (Date.now() - cached.timestamp < CACHE_TTL_MS) {
            return;
        }
    }

    try {
        const data = await AegisApi.getPlayer(playerId);
        prefetchCache.set(cacheKey, {
            data,
            timestamp: Date.now(),
            type: 'player'
        });
        cleanCache();
        console.log(`[PREFETCH] Cached player ${playerId}`);
    } catch (e) {
        console.warn(`[PREFETCH] Failed to prefetch player ${playerId}`, e);
    }
}

/**
 * Prefetch simulation for a player vs opponent
 */
export async function prefetchSimulation(
    playerId: string,
    opponentId: string
): Promise<void> {
    const cacheKey = `sim:${playerId}:${opponentId}`;

    if (prefetchCache.has(cacheKey)) {
        const cached = prefetchCache.get(cacheKey)!;
        if (Date.now() - cached.timestamp < CACHE_TTL_MS) {
            return;
        }
    }

    try {
        const data = await AegisApi.runSimulation(playerId, opponentId);
        prefetchCache.set(cacheKey, {
            data,
            timestamp: Date.now(),
            type: 'simulation'
        });
        cleanCache();
        console.log(`[PREFETCH] Cached simulation ${playerId} vs ${opponentId}`);
    } catch (e) {
        console.warn(`[PREFETCH] Failed to prefetch simulation`, e);
    }
}

/**
 * Get cached player data (returns null if not cached)
 */
export function getCachedPlayer(playerId: string): any | null {
    const cacheKey = `player:${playerId}`;
    const cached = prefetchCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
        console.log(`[PREFETCH] Cache hit for player ${playerId}`);
        return cached.data;
    }

    return null;
}

/**
 * Get cached simulation data
 */
export function getCachedSimulation(
    playerId: string,
    opponentId: string
): SimulationResult | null {
    const cacheKey = `sim:${playerId}:${opponentId}`;
    const cached = prefetchCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
        console.log(`[PREFETCH] Cache hit for simulation ${playerId} vs ${opponentId}`);
        return cached.data as SimulationResult;
    }

    return null;
}

/**
 * Hook-style prefetch on hover (debounced)
 */
let hoverTimeout: NodeJS.Timeout | null = null;

export function onPlayerHover(playerId: string, delay: number = 200): void {
    if (hoverTimeout) clearTimeout(hoverTimeout);

    hoverTimeout = setTimeout(() => {
        prefetchPlayer(playerId);
    }, delay);
}

export function onPlayerHoverEnd(): void {
    if (hoverTimeout) {
        clearTimeout(hoverTimeout);
        hoverTimeout = null;
    }
}

/**
 * Clear all prefetch cache
 */
export function clearPrefetchCache(): void {
    prefetchCache.clear();
    console.log('[PREFETCH] Cache cleared');
}

/**
 * Get cache statistics
 */
export function getPrefetchStats(): { size: number; entries: string[] } {
    return {
        size: prefetchCache.size,
        entries: [...prefetchCache.keys()]
    };
}

export default {
    prefetchPlayer,
    prefetchSimulation,
    getCachedPlayer,
    getCachedSimulation,
    onPlayerHover,
    onPlayerHoverEnd,
    clearPrefetchCache,
    getPrefetchStats
};
