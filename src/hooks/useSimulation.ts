/**
 * useSimulation Hook
 * React hook for running Aegis Monte Carlo simulations
 */

import { useState, useCallback } from 'react';
import { ApiContract } from '../api/client';

// Inlined from removed aegisApi.ts
interface StatProjection { points: number; rebounds: number; assists: number; threes: number;[key: string]: number; }
interface SimulationResult {
    projections: { floor: StatProjection; expected_value: StatProjection; ceiling: StatProjection; };
    confidence: { grade: string; score: number; };
    modifiers: { archetype: string; usage_boost: number; fatigue?: number; };
    execution_time_ms: number;
    schedule_context: { is_b2b: boolean; days_rest: number; modifier: number; };
    game_mode: { blowout_pct: number; clutch_pct: number; };
    momentum: { hot_streak: boolean; };
    defender_profile?: { primary_defender: string; dfg_pct: number; pct_plusminus: number; };
}

interface UseSimulationOptions {
    playerId: string;
    opponentId?: string;
    ptsLine?: number;
    rebLine?: number;
    astLine?: number;
}

interface UseSimulationReturn {
    simulation: SimulationResult | null;
    loading: boolean;
    error: string | null;
    refreshStatus: { message: string; gamesAdded: number } | null;
    runSimulation: (opponentId?: string) => Promise<void>;
    forceRefreshAndRun: (opponentId?: string) => Promise<void>;
    clearSimulation: () => void;
}

export function useSimulation({
    playerId,
    opponentId: defaultOpponentId,
    ptsLine,
    rebLine,
    astLine
}: UseSimulationOptions): UseSimulationReturn {
    const [simulation, setSimulation] = useState<SimulationResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [refreshStatus, setRefreshStatus] = useState<{ message: string; gamesAdded: number } | null>(null);

    const runSimulation = useCallback(async (opponentId?: string) => {
        const targetOpponent = opponentId || defaultOpponentId;

        if (!targetOpponent) {
            setError('No opponent specified');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const base = import.meta.env.VITE_API_URL || '';
            const params = new URLSearchParams({
                player_id: playerId,
                opponent_id: targetOpponent,
                ...(ptsLine !== undefined && { pts_line: String(ptsLine) }),
                ...(rebLine !== undefined && { reb_line: String(rebLine) }),
                ...(astLine !== undefined && { ast_line: String(astLine) }),
            });
            const res = await fetch(`${base}/aegis/simulate?${params}`);
            if (!res.ok) throw new Error(`Simulation failed: ${res.status}`);
            const result: SimulationResult & { error?: string } = await res.json();

            if (result.error) {
                setSimulation(result);
                setError(result.error);
            } else {
                setSimulation(result);
            }
        } catch (e: any) {
            setError(e.message || 'Simulation failed');
            console.error('[useSimulation] Error:', e);
        } finally {
            setLoading(false);
        }
    }, [playerId, defaultOpponentId, ptsLine, rebLine, astLine]);

    /**
     * Force refresh: Fetch fresh game data from NBA API, then run simulation
     * This is the callback for the "Re-run Simulation" button
     */
    const forceRefreshAndRun = useCallback(async (opponentId?: string) => {
        const targetOpponent = opponentId || defaultOpponentId;

        if (!targetOpponent) {
            setError('No opponent specified');
            return;
        }

        setLoading(true);
        setError(null);
        setRefreshStatus(null);

        try {
            const base = import.meta.env.VITE_API_URL || '';

            // Step 1: Refresh player data
            console.log(`[useSimulation] Refreshing data for player ${playerId}...`);
            const refreshRes = await fetch(`${base}/aegis/refresh/${playerId}`, { method: 'POST' });
            if (refreshRes.ok) {
                const refreshResult = await refreshRes.json();
                setRefreshStatus({
                    message: refreshResult.message || 'Data refreshed',
                    gamesAdded: refreshResult.games_added || 0
                });
                console.log(`[useSimulation] Refresh complete: ${refreshResult.games_added} games added`);
            }

            // Step 2: Run simulation with force_fresh flag
            const params = new URLSearchParams({
                player_id: playerId,
                opponent_id: targetOpponent,
                force_fresh: 'true',
                ...(ptsLine !== undefined && { pts_line: String(ptsLine) }),
                ...(rebLine !== undefined && { reb_line: String(rebLine) }),
                ...(astLine !== undefined && { ast_line: String(astLine) }),
            });
            const res = await fetch(`${base}/aegis/simulate?${params}`);
            if (!res.ok) throw new Error(`Simulation failed: ${res.status}`);
            const result: SimulationResult & { error?: string } = await res.json();

            if (result.error) {
                setSimulation(result);
                setError(result.error);
            } else {
                setSimulation(result);
            }
        } catch (e: any) {
            setError(e.message || 'Refresh and simulation failed');
            console.error('[useSimulation] Force refresh error:', e);
        } finally {
            setLoading(false);
        }
    }, [playerId, defaultOpponentId, ptsLine, rebLine, astLine]);

    const clearSimulation = useCallback(() => {
        setSimulation(null);
        setError(null);
        setRefreshStatus(null);
    }, []);

    return {
        simulation,
        loading,
        error,
        refreshStatus,
        runSimulation,
        forceRefreshAndRun,
        clearSimulation
    };
}

export default useSimulation;
