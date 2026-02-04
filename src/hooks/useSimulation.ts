/**
 * useSimulation Hook
 * React hook for running Aegis Monte Carlo simulations
 */

import { useState, useCallback } from 'react';
import { AegisApi, SimulationResult } from '../services/aegisApi';
import { getCachedSimulation } from '../services/prefetchService';

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

        // Check cache first
        const cached = getCachedSimulation(playerId, targetOpponent);
        if (cached) {
            setSimulation(cached);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const result = await AegisApi.runSimulation(playerId, targetOpponent, {
                ptsLine,
                rebLine,
                astLine
            });

            if (result.error) {
                // Partial result with error
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
            // Step 1: Refresh player data (incremental fetch from NBA API)
            console.log(`[useSimulation] Refreshing data for player ${playerId}...`);
            const refreshResult = await AegisApi.refreshPlayerData(playerId);

            setRefreshStatus({
                message: refreshResult.message,
                gamesAdded: refreshResult.games_added
            });

            console.log(`[useSimulation] Refresh complete: ${refreshResult.games_added} games added, days_rest=${refreshResult.days_rest}`);

            // Step 2: Run simulation with force_fresh=true to bypass cache
            const result = await AegisApi.runSimulation(playerId, targetOpponent, {
                ptsLine,
                rebLine,
                astLine,
                forceFresh: true
            });

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
