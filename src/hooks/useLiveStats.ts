/**
 * useLiveStats - Real-time live game stats hook
 * =============================================
 * Connects to /live/stream SSE endpoint for real-time updates.
 * 
 * Features:
 * - Auto-reconnect on disconnect
 * - Tracks stat changes for gold pulse animation
 * - Provides top 10 leaders by in-game PIE
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useServerSentEvents } from './useServerSentEvents';

// Type definitions
export interface LivePlayerStat {
    player_id: string;
    name: string;
    team: string;
    pie: number;
    plus_minus: number;
    ts_pct: number;
    efg_pct: number;
    // Insight enrichment fields (from backend Tier 1 Refactor)
    heat_status: 'blazing' | 'hot' | 'steady' | 'cold' | 'freezing';  // Phase 3: Contextual Alpha
    efficiency_trend: 'surging' | 'steady' | 'dipping';
    // Alpha Gap context (Phase 2) - for tooltip display
    season_ts_pct: number | null;
    season_efg_pct: number | null;
    // Matchup Difficulty (Phase 3 P0)
    opponent_team: string | null;
    opponent_def_rating: number | null;
    matchup_difficulty: 'elite' | 'average' | 'soft' | null;
    // Usage Vacuum (Phase 3 P1)
    has_usage_vacuum: boolean;
    usage_bump: number | null;
    vacuum_source: string | null;
    stats: {
        pts: number;
        reb: number;
        ast: number;
        stl?: number;
        blk?: number;
    };
    min: string;
}

export interface LiveGame {
    game_id: string;
    home_team: string;
    away_team: string;
    home_score: number;
    away_score: number;
    clock: string;
    period: number;
    status: 'LIVE' | 'HALFTIME' | 'FINAL' | 'UPCOMING';
    leaders: LivePlayerStat[];
    last_updated: string;
    is_garbage_time: boolean;
}


export interface LivePulseData {
    games: LiveGame[];
    meta: {
        timestamp: string;
        game_count: number;
        update_cycle: number;
        live_count: number;
    };
    changes: Record<string, string[]>; // game_id -> player_ids with stat changes
}

export interface UseLiveStatsReturn {
    games: LiveGame[];
    leaders: LivePlayerStat[];
    liveCount: number;
    isConnected: boolean;
    isConnecting: boolean;
    error: Error | null;
    lastUpdate: string | null;
    changedPlayerIds: Set<string>;
    connect: () => void;
    disconnect: () => void;
}

const API_BASE = import.meta.env?.VITE_PULSE_API_URL || 'https://quantsight-pulse-458498663186.us-central1.run.app';

export function useLiveStats(): UseLiveStatsReturn {
    const [games, setGames] = useState<LiveGame[]>([]);
    const [liveCount, setLiveCount] = useState(0);
    const [lastUpdate, setLastUpdate] = useState<string | null>(null);
    const [changedPlayerIds, setChangedPlayerIds] = useState<Set<string>>(new Set());

    // Raw leaders from all games (before sorting/filtering)
    const [rawLeaders, setRawLeaders] = useState<LivePlayerStat[]>([]);

    // P1: useMemo for sorting - only re-sort when rawLeaders changes
    const leaders = useMemo(() => {
        return [...rawLeaders].sort((a, b) => b.pie - a.pie).slice(0, 10);
    }, [rawLeaders]);

    const handleMessage = useCallback((data: LivePulseData) => {
        if (!data || !data.games) return;

        // Update games
        setGames(data.games);
        setLiveCount(data.meta?.live_count || 0);
        setLastUpdate(data.meta?.timestamp || new Date().toISOString());

        // Aggregate all leaders across games
        const allLeaders: LivePlayerStat[] = [];
        data.games.forEach(game => {
            if (game.status === 'LIVE' && game.leaders) {
                allLeaders.push(...game.leaders);
            }
        });

        // Update raw leaders - useMemo will handle sorting
        setRawLeaders(allLeaders);

        // === PULSE DETECTION (Uses backend-provided changes) ===
        // Backend already handles delta detection with proper thresholds and cooldowns.
        // We only dampen pulses during garbage time to prevent false "buying signals".
        const changed = new Set<string>();

        // Check if any live game is in garbage time (lead > 20 in Q4)
        const isGarbageTime = data.games.some(
            g => g.status === 'LIVE' && g.is_garbage_time
        );

        // Use server-provided changes, but dampen during garbage time
        if (data.changes && !isGarbageTime) {
            Object.values(data.changes).forEach(ids => {
                ids.forEach(id => changed.add(id));
            });
        }

        setChangedPlayerIds(changed);

        // Clear pulse after 2 seconds
        if (changed.size > 0) {
            setTimeout(() => setChangedPlayerIds(new Set()), 2000);
        }
    }, []);

    const { isConnected, isConnecting, error, connect, disconnect } = useServerSentEvents({
        url: `${API_BASE}/live/stream`,
        onMessage: handleMessage,
        autoReconnect: true,
        reconnectInterval: 3000,
        maxRetries: 10
    });

    return {
        games,
        leaders,
        liveCount,
        isConnected,
        isConnecting,
        error,
        lastUpdate,
        changedPlayerIds,
        connect,
        disconnect
    };
}

/**
 * Check if a player ID had a recent stat change (for gold pulse effect).
 * Includes auto-cleanup so pulse doesn't stay stuck if backend doesn't clear.
 */
export function usePlayerPulse(playerId: string, changedPlayerIds: Set<string>, durationMs: number = 3000): boolean {
    const [isPulsing, setIsPulsing] = useState(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        const shouldPulse = changedPlayerIds.has(playerId);

        if (shouldPulse && !isPulsing) {
            // Start pulsing
            setIsPulsing(true);

            // Auto-cleanup after duration
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
            timeoutRef.current = setTimeout(() => {
                setIsPulsing(false);
            }, durationMs);
        }

        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, [playerId, changedPlayerIds, isPulsing, durationMs]);

    return isPulsing;
}

export default useLiveStats;
