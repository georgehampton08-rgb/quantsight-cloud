export interface PlayerProfile {
    id: string;
    name: string;
    team: string;
    position: string;
    avatar: string;
    height: string;
    weight: string;
    experience: string;
    narrative: string; // The AI generated text
    hitProbability: number; // 0-100
    impliedOdds: number; // e.g. -110 or +150 converted to probability or raw
    stats: {
        ppg: number;
        rpg: number;
        apg: number;
        confidence: number; // 0-100
        trend: number[]; // Last 5 games
    };
}

export interface PlayerStats {
    label: string;
    value: string | number;
    subValue?: string;
    trend?: number[];
    confidence?: number;
}

export interface MatchupResult {
    defense_matrix: {
        paoa: number;
        rebound_resistance: string;
        profile: Record<string, number>;
    };
    nemesis_vector: {
        grade: string;
        status: string;
        avg_vs_opponent: number;
        delta_percent: number;
    };
    pace_friction: {
        multiplier: number;
        projected_pace: string;
    };
    insight: {
        text: string;
        type: 'success' | 'warning' | 'neutral';
    };
}

// Global Window Interface
declare global {
    interface Window {
        electronAPI: {
            ping: () => Promise<string>;
            searchPlayers: (query: string) => Promise<any[]>;
            getPlayerProfile: (id: string) => Promise<PlayerProfile>;
            checkSystemHealth: () => Promise<{ nba: 'healthy' | 'warning' | 'critical', gemini: 'healthy' | 'warning' | 'critical', database: 'healthy' | 'warning' | 'critical' }>;
            analyzeMatchup: (playerId: string, opponent: string) => Promise<MatchupResult>;
            saveKeys: (apiKey: string) => Promise<{ status: string, message: string }>;
            purgeDb: () => Promise<{ status: string, message: string }>;
            forceRefresh: (playerId: string, playerName: string, cachedLastGame: string) => Promise<any>;
            saveKaggleKeys: (username: string, key: string) => Promise<{ status: string, message: string }>;
            syncKaggle: () => Promise<{ status: string, message: string }>;
            getSchedule: () => Promise<any>;
            // New NBA Data endpoints
            getTeams: () => Promise<any>;
            getRoster: (teamId: string) => Promise<any>;
            getInjuries: () => Promise<any>;
            getPlayerStats: (playerId: string, season?: string) => Promise<any>;
            getPlayerCareer: (playerId: string) => Promise<any>;
        }
    }
}

import { ApiContract } from '../api/client';
import { normalizePlayerProfile, normalizeMatchupResult } from '../api/normalizers';

export const PlayerApi = {
    search: async (query: string) => {
        const res = await ApiContract.execute<any[]>('searchPlayers', {
            path: `players/search?q=${encodeURIComponent(query)}`
        }, [query]);
        return res.data;
    },
    getProfile: async (id: string) => {
        const res = await ApiContract.execute<PlayerProfile>('getPlayerProfile', {
            path: `players/${id}`
        }, [id]);
        return normalizePlayerProfile(res.data) as PlayerProfile;
    },
    analyzeMatchup: async (playerId: string, opponent: string) => {
        // Defensive: extract ID if opponent is accidentally passed as an object
        let opponentId: string;
        if (typeof opponent === 'object' && opponent !== null) {
            opponentId = (opponent as any).id || (opponent as any).team_id || (opponent as any).abbreviation || String(opponent);
        } else {
            opponentId = String(opponent);
        }
        const res = await ApiContract.execute<MatchupResult>('analyzeMatchup', {
            path: `matchup/analyze-player?player_id=${encodeURIComponent(playerId)}&opponent=${encodeURIComponent(opponentId)}`
        }, [playerId, opponentId]);
        return normalizeMatchupResult(res.data) as MatchupResult;
    },
    getKeyStatus: async () => {
        // Read-only check: is the server-side Gemini key configured?
        const res = await ApiContract.executeWeb<{ gemini_configured: boolean; kaggle: string }>(
            { path: 'settings/key-status' }
        );
        return res;
    },
    purgeDb: async () => {
        // Auth-gated: executeAdmin attaches Firebase Bearer token automatically
        const res = await ApiContract.executeAdmin<{ status: string; message: string; detail: string[] }>(
            { path: 'admin/cache/purge', options: { method: 'POST' } }
        );
        return res;
    },

    forceRefresh: async (playerId: string, playerName: string, cachedLastGame: string) => {
        const res = await ApiContract.execute<any>('forceRefresh', {
            path: `players/${playerId}/refresh`,
            options: {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playerName, cachedLastGame })
            }
        }, [playerId, playerName, cachedLastGame]);
        return res.data;
    }
};

