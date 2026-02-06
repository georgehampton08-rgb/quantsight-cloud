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

export const PlayerApi = {
    search: async (query: string) => {
        if (window.electronAPI) {
            return window.electronAPI.searchPlayers(query);
        }
        // Browser fallback
        try {
            const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/players/search?q=${encodeURIComponent(query)}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return res.json();
        } catch (error) {
            console.error(`[PlayerApi] search failed for query "${query}":`, error);
            throw error;
        }
    },
    getProfile: async (id: string) => {
        if (window.electronAPI) {
            return window.electronAPI.getPlayerProfile(id);
        }
        // Browser fallback
        try {
            const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/players/${id}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return res.json();
        } catch (error) {
            console.error(`[PlayerApi] getProfile failed for ID "${id}":`, error);
            throw error;
        }
    },
    analyzeMatchup: async (playerId: string, opponent: string) => {
        if (window.electronAPI) {
            return window.electronAPI.analyzeMatchup(playerId, opponent);
        }
        // Browser fallback
        try {
            const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/matchup/${playerId}/${opponent}`);
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return res.json();
        } catch (error) {
            console.error(`[PlayerApi] analyzeMatchup failed for player "${playerId}" vs "${opponent}":`, error);
            throw error;
        }
    },
    saveKeys: async (apiKey: string) => {
        if (window.electronAPI) {
            return window.electronAPI.saveKeys(apiKey);
        }
        // Browser fallback
        try {
            const res = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/settings/keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ gemini_api_key: apiKey })
            });
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return res.json();
        } catch (error) {
            console.error('[PlayerApi] saveKeys failed:', error);
            throw error;
        }
    },
    saveKaggleKeys: async (username: string, key: string) => {
        if (window.electronAPI) {
            return window.electronAPI.saveKaggleKeys(username, key);
        }
        // Browser fallback - would need backend endpoint
        throw new Error('Kaggle keys not supported in browser mode');
    },
    syncKaggle: async () => {
        if (window.electronAPI) {
            return window.electronAPI.syncKaggle();
        }
        // Browser fallback - would need backend endpoint
        throw new Error('Kaggle sync not supported in browser mode');
    },
    purgeDb: async () => {
        if (window.electronAPI) {
            return window.electronAPI.purgeDb();
        }
        // Browser fallback - would need backend endpoint
        throw new Error('DB purge not supported in browser mode');
    },
    forceRefresh: async (playerId: string, playerName: string, cachedLastGame: string) => {
        if (window.electronAPI) {
            return window.electronAPI.forceRefresh(playerId, playerName, cachedLastGame);
        }
        // Browser fallback - call backend directly
        try {
            const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/players/${playerId}/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playerName, cachedLastGame })
            });
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            return res.json();
        } catch (error) {
            console.error(`[PlayerApi] forceRefresh failed for ${playerId}:`, error);
            throw error;
        }
    }
};

