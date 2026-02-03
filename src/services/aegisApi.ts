/**
 * Aegis API Service
 * Frontend interface for Aegis-Sovereign Data Router
 */

const API_BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app';

// Types
export interface AegisHealthStatus {
    status: 'healthy' | 'degraded' | 'critical' | 'down' | 'error';
    uptime: string;
    router: {
        cache_hit_rate: string;
        cache_hits: number;
        cache_misses: number;
        api_calls: number;
        offline_mode: boolean;
        integrity_failures: number;
        validation_failures: number;
    };
    rate_limiting: {
        tokens_available: number;
        max_tokens: number;
        emergency_mode: boolean;
        requests_last_minute: number;
    };
    storage: {
        writes_succeeded: number;
        writes_failed: number;
        success_rate: string;
    };
    system: {
        cpu_percent: number;
        memory_percent: number;
        available_mb: number;
    };
    analysis_mode: 'ml' | 'classic' | 'hybrid';
    vertex_engine: boolean;
}

export interface PlayerMatchup {
    player_a: {
        id: string;
        name: string;
        score: number;
    };
    player_b: {
        id: string;
        name: string;
        score: number;
    };
    advantage: 'A' | 'B' | 'EVEN' | 'UNKNOWN';
    advantage_degree: number;
    categories: Record<string, 'A' | 'B' | 'EVEN'>;
    analysis: string;
    engine_stats: {
        matchups_analyzed: number;
        cache_hits: number;
        cache_hit_rate: number;
        avg_analysis_time_ms: number;
        analysis_mode: string;
    };
}

export interface TeamMatchup {
    team_a: string;
    team_b: string;
    predicted_winner: string;
    win_probability: number;
    upset_potential: number;
    key_factors: string[];
    player_matchups: {
        player_a: string;
        player_b: string;
        advantage: string;
        advantage_degree: number;
    }[];
    engine_stats: Record<string, any>;
}

export interface AegisPlayerData {
    data: {
        player: Record<string, any>;
        current_stats: Record<string, any>;
        analytics: Record<string, any>;
        team: Record<string, any>;
    };
    meta: {
        source: 'cache' | 'api' | 'unknown';
        freshness: 'fresh' | 'warm' | 'stale' | 'live' | 'unknown';
        cached: boolean;
        offline_mode: boolean;
        latency_ms: number;
    };
}

// API Functions
export const AegisApi = {
    /**
     * Get Aegis system health and statistics
     */
    getHealth: async (): Promise<AegisHealthStatus> => {
        try {
            const res = await fetch(`${API_BASE}/aegis/health`);
            return await res.json();
        } catch (error) {
            console.error('Aegis health check failed:', error);
            return {
                status: 'error',
                uptime: 'N/A',
                router: { cache_hit_rate: '0%', cache_hits: 0, cache_misses: 0, api_calls: 0, offline_mode: true, integrity_failures: 0, validation_failures: 0 },
                rate_limiting: { tokens_available: 0, max_tokens: 0, emergency_mode: false, requests_last_minute: 0 },
                storage: { writes_succeeded: 0, writes_failed: 0, success_rate: '0%' },
                system: { cpu_percent: 0, memory_percent: 0, available_mb: 0 },
                analysis_mode: 'classic',
                vertex_engine: false
            };
        }
    },

    /**
     * Get player data via Aegis router (with caching, rate limiting)
     */
    getPlayer: async (playerId: string, season: string = '2024-25'): Promise<AegisPlayerData> => {
        try {
            const res = await fetch(`${API_BASE}/aegis/player/${playerId}?season=${season}`);
            if (!res.ok) throw new Error(`Aegis player fetch failed: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error(`[AegisApi] getPlayer failed for ${playerId}:`, error);
            throw error;
        }
    },

    /**
     * Get player stats via Aegis router
     */
    getPlayerStats: async (playerId: string, season: string = '2024-25'): Promise<any> => {
        try {
            const res = await fetch(`${API_BASE}/aegis/player/${playerId}/stats?season=${season}`);
            if (!res.ok) throw new Error(`Aegis stats fetch failed: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error(`[AegisApi] getPlayerStats failed for ${playerId}:`, error);
            throw error;
        }
    },

    /**
     * Compare two players head-to-head
     */
    getPlayerMatchup: async (playerAId: string, playerBId: string, season: string = '2024-25'): Promise<PlayerMatchup> => {
        try {
            const res = await fetch(`${API_BASE}/aegis/matchup/player/${playerAId}/vs/${playerBId}?season=${season}`);
            if (!res.ok) throw new Error(`Player matchup failed: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error(`[AegisApi] getPlayerMatchup failed for ${playerAId} vs ${playerBId}:`, error);
            throw error;
        }
    },

    /**
     * Compare two teams in full matchup analysis
     */
    getTeamMatchup: async (teamAId: string, teamBId: string, season: string = '2024-25'): Promise<TeamMatchup> => {
        try {
            const res = await fetch(`${API_BASE}/aegis/matchup/team/${teamAId}/vs/${teamBId}?season=${season}`);
            if (!res.ok) throw new Error(`Team matchup failed: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error(`[AegisApi] getTeamMatchup failed for ${teamAId} vs ${teamBId}:`, error);
            throw error;
        }
    },

    /**
     * Get detailed Aegis statistics
     */
    getStats: async (): Promise<any> => {
        try {
            const res = await fetch(`${API_BASE}/aegis/stats`);
            if (!res.ok) throw new Error(`Aegis stats failed: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error('[AegisApi] getStats failed:', error);
            throw error;
        }
    },

    /**
     * Refresh player data by fetching new game logs incrementally
     * Use this when Force Refresh is clicked
     */
    refreshPlayerData: async (playerId: string, season: string = '2024-25'): Promise<{
        player_id: string;
        status: string;
        message: string;
        games_added: number;
        days_rest: number | null;
        new_last_game: string | null;
        execution_time_ms: number;
    }> => {
        try {
            const res = await fetch(`${API_BASE}/player-data/refresh/${playerId}?season=${season}&invalidate_cache=true`, {
                method: 'POST'
            });
            if (!res.ok) throw new Error(`Data refresh failed: ${res.status}`);
            return await res.json();
        } catch (error) {
            console.error(`[AegisApi] refreshPlayerData failed for ${playerId}:`, error);
            throw error;
        }
    },

    /**
     * Run Monte Carlo simulation for a player
     * Returns Floor/EV/Ceiling projections with confidence scores
     */
    runSimulation: async (
        playerId: string,
        opponentId: string,
        options?: {
            gameDate?: string;
            ptsLine?: number;
            rebLine?: number;
            astLine?: number;
            forceFresh?: boolean;
        }
    ): Promise<SimulationResult> => {
        const params = new URLSearchParams({
            opponent_id: opponentId
        });

        if (options?.gameDate) params.append('game_date', options.gameDate);
        if (options?.ptsLine) params.append('pts_line', String(options.ptsLine));
        if (options?.rebLine) params.append('reb_line', String(options.rebLine));
        if (options?.astLine) params.append('ast_line', String(options.astLine));
        if (options?.forceFresh) params.append('force_fresh', 'true');

        const res = await fetch(`${API_BASE}/aegis/simulate/${playerId}?${params}`);
        if (!res.ok) throw new Error(`Simulation failed: ${res.status}`);
        return await res.json();
    },

    /**
     * Run simulation with Shadow-Race pattern (Patient Data Handling)
     * 
     * Returns cached data immediately if live takes > patienceMs,
     * while live request continues in background.
     * 
     * @param playerId - Player to simulate
     * @param opponentId - Opponent team ID
     * @param options - Simulation options
     * @param patienceMs - Max time to wait for live before serving cache (default: 800ms)
     * @returns PatientSimulationResult with source info and late arrival tracking
     */
    runPatientSimulation: async (
        playerId: string,
        opponentId: string,
        options?: {
            gameDate?: string;
            ptsLine?: number;
            rebLine?: number;
            astLine?: number;
            forceFresh?: boolean;
        },
        patienceMs: number = 800
    ): Promise<PatientSimulationResult> => {
        const startTime = Date.now();
        const requestId = `sim_${playerId}_${startTime}`;

        const params = new URLSearchParams({
            opponent_id: opponentId
        });

        if (options?.gameDate) params.append('game_date', options.gameDate);
        if (options?.ptsLine) params.append('pts_line', String(options.ptsLine));
        if (options?.rebLine) params.append('reb_line', String(options.rebLine));
        if (options?.astLine) params.append('ast_line', String(options.astLine));
        if (options?.forceFresh) params.append('force_fresh', 'true');

        // Live request promise
        const liveRequest = fetch(`${API_BASE}/aegis/simulate/${playerId}?${params}`)
            .then(res => {
                if (!res.ok) throw new Error(`Simulation failed: ${res.status}`);
                return res.json();
            });

        // Patience timeout
        const patienceTimeout = new Promise<never>((_, reject) => {
            setTimeout(() => reject(new Error('PATIENCE_EXCEEDED')), patienceMs);
        });

        try {
            // Race live vs patience
            const data = await Promise.race([liveRequest, patienceTimeout]);
            return {
                data,
                source: 'live',
                lateArrivalPending: false,
                executionTimeMs: Date.now() - startTime,
                requestId
            };
        } catch (error: any) {
            if (error.message === 'PATIENCE_EXCEEDED') {
                console.log(`[ShadowRace] Patience ${patienceMs}ms exceeded for player ${playerId}`);

                // Don't cancel live - let it complete in background
                liveRequest
                    .then(data => {
                        console.log(`[ShadowRace] Late arrival for ${requestId}`);
                        // Store for later retrieval or emit event
                        window.dispatchEvent(new CustomEvent('nexus:late-arrival', {
                            detail: { requestId, playerId, data, delayMs: Date.now() - startTime }
                        }));
                    })
                    .catch(() => { }); // Ignore background errors

                // Try to get cached data
                try {
                    const cacheRes = await fetch(`${API_BASE}/cache/simulation/${playerId}`);
                    if (cacheRes.ok) {
                        const cacheData = await cacheRes.json();
                        return {
                            data: cacheData,
                            source: 'cache',
                            lateArrivalPending: true,
                            executionTimeMs: Date.now() - startTime,
                            requestId
                        };
                    }
                } catch { }

                // No cache available - wait a bit longer for live
                try {
                    const data = await Promise.race([
                        liveRequest,
                        new Promise<never>((_, reject) =>
                            setTimeout(() => reject(new Error('FINAL_TIMEOUT')), 2000)
                        )
                    ]);
                    return {
                        data,
                        source: 'live',
                        lateArrivalPending: false,
                        executionTimeMs: Date.now() - startTime,
                        requestId
                    };
                } catch {
                    return {
                        data: null,
                        source: 'timeout',
                        lateArrivalPending: true,
                        executionTimeMs: Date.now() - startTime,
                        requestId,
                        error: 'Simulation timed out - no cache available'
                    };
                }
            }

            // Other error
            return {
                data: null,
                source: 'error',
                lateArrivalPending: false,
                executionTimeMs: Date.now() - startTime,
                requestId,
                error: error.message
            };
        }
    },

    // Get radar chart dimensions (real math, not hardcoded!)
    async getRadarDimensions(playerId: string, opponentId?: string): Promise<RadarResult> {
        const params = opponentId ? `?opponent_id=${opponentId}` : '';
        const res = await fetch(`${API_BASE}/radar/${playerId}${params}`);
        if (!res.ok) throw new Error(`Radar failed: ${res.status}`);
        return await res.json();
    }
};

// Patient Simulation Types (Shadow-Race pattern)
export interface PatientSimulationResult {
    data: SimulationResult | null;
    source: 'live' | 'cache' | 'timeout' | 'error';
    lateArrivalPending: boolean;
    executionTimeMs: number;
    requestId: string;
    error?: string;
}

// Radar Types
export interface RadarDimensions {
    scoring: number;
    playmaking: number;
    rebounding: number;
    defense: number;
    pace: number;
}

export interface RadarResult {
    player_id: string;
    player_name: string;
    opponent_id: string | null;
    opponent_name: string | null;
    player_stats: RadarDimensions;
    opponent_defense: RadarDimensions;
    calculated_at: string;
    formulas_used: string[];
}

// Simulation Types
export interface SimulationResult {
    player_id: string;
    opponent_id: string;
    game_date: string;
    projections: {
        floor: StatProjection;
        expected_value: StatProjection;
        ceiling: StatProjection;
    };
    confidence: {
        score: number;
        grade: 'A' | 'B' | 'C' | 'D' | 'F';
    };
    modifiers: {
        archetype: string;
        fatigue: number;
        usage_boost: number;
    };
    schedule_context: {
        is_road: boolean;
        is_b2b: boolean;
        days_rest: number;
        modifier: number;
    };
    game_mode: {
        blowout_pct: number;
        clutch_pct: number;
        mode: 'standard' | 'blowout' | 'clutch';
    };
    momentum: {
        consecutive_makes: number;
        consecutive_misses: number;
        hot_streak: boolean;
        cold_streak: boolean;
    };
    defender_profile: {
        primary_defender: string;
        dfg_pct: number;
        pct_plusminus: number;
        rating: string;
    };
    hit_probabilities?: Record<string, number>;
    execution_time_ms: number;
    error?: string;
}

export interface StatProjection {
    points: number;
    rebounds: number;
    assists: number;
    minutes?: number;
    threes?: number;
    steals?: number;
    blocks?: number;
    turnovers?: number;
}

export default AegisApi;
