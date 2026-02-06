import React, { createContext, useContext, useReducer, ReactNode } from 'react';

// ============================================================================
// TYPES
// ============================================================================

export interface PlayerLiveStats {
    playerId: string;
    name: string;
    team: 'home' | 'away';
    points: number;
    assists: number;
    rebounds: number;
    pie: number; // Player Impact Estimate (0.00 - 1.00)
    usage: number; // Usage Rate (0.00 - 1.00)
    isPieLeader: boolean; // True if highest PIE on team
    trendDelta: number; // Difference from season average
}

export interface LiveGameState {
    gameId: string | null;
    clock: string; // e.g., "Q4 04:30"
    quarter: number;
    homeScore: number;
    awayScore: number;
    activePlayers: Map<string, PlayerLiveStats>;
    lastUpdate: number; // Timestamp
}

type Action =
    | { type: 'UPDATE_GAME_STATE'; payload: Partial<LiveGameState> }
    | { type: 'UPDATE_PLAYER_STATS'; payload: PlayerLiveStats }
    | { type: 'RECALCULATE_HIERARCHY' }
    | { type: 'RESET_GAME' };

// ============================================================================
// STATE MANAGEMENT logic
// ============================================================================

const initialState: LiveGameState = {
    gameId: null,
    clock: "Q1 12:00",
    quarter: 1,
    homeScore: 0,
    awayScore: 0,
    activePlayers: new Map(),
    lastUpdate: Date.now(),
};

function liveGameReducer(state: LiveGameState, action: Action): LiveGameState {
    switch (action.type) {
        case 'UPDATE_GAME_STATE':
            return { ...state, ...action.payload, lastUpdate: Date.now() };

        case 'UPDATE_PLAYER_STATS': {
            const newPlayers = new Map(state.activePlayers);
            newPlayers.set(action.payload.playerId, action.payload);
            return { ...state, activePlayers: newPlayers, lastUpdate: Date.now() };
        }

        case 'RECALCULATE_HIERARCHY': {
            // Find PIE leader for home and away teams
            let homeLeaderId: string | null = null;
            let awayLeaderId: string | null = null;
            let maxHomePie = -1;
            let maxAwayPie = -1;

            state.activePlayers.forEach((player) => {
                if (player.team === 'home' && player.pie > maxHomePie) {
                    maxHomePie = player.pie;
                    homeLeaderId = player.playerId;
                }
                if (player.team === 'away' && player.pie > maxAwayPie) {
                    maxAwayPie = player.pie;
                    awayLeaderId = player.playerId;
                }
            });

            // Update isPieLeader flag for all players
            const updatedPlayers = new Map(state.activePlayers);
            updatedPlayers.forEach((player) => {
                const isLeader =
                    (player.team === 'home' && player.playerId === homeLeaderId) ||
                    (player.team === 'away' && player.playerId === awayLeaderId);

                if (player.isPieLeader !== isLeader) {
                    updatedPlayers.set(player.playerId, { ...player, isPieLeader: isLeader });
                }
            });

            return { ...state, activePlayers: updatedPlayers, lastUpdate: Date.now() };
        }

        case 'RESET_GAME':
            return initialState;

        default:
            return state;
    }
}

// ============================================================================
// CONTEXT SETUP
// ============================================================================

interface LiveGameContextType {
    state: LiveGameState;
    dispatch: React.Dispatch<Action>;
}

const LiveGameContext = createContext<LiveGameContextType | undefined>(undefined);

export function LiveGameProvider({ children }: { children: ReactNode }) {
    const [state, dispatch] = useReducer(liveGameReducer, initialState);

    return (
        <LiveGameContext.Provider value={{ state, dispatch }}>
            {children}
        </LiveGameContext.Provider>
    );
}

export function useLiveGameStore() {
    const context = useContext(LiveGameContext);
    if (context === undefined) {
        throw new Error('useLiveGameStore must be used within a LiveGameProvider');
    }
    return context;
}
