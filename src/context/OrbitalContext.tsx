import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { PlayerProfile } from '../services/playerApi';

// Local type definition (no longer using mock data)
interface NBATeam {
    id: string;
    name: string;
    abbreviation: string;
}

import { SimulationResult } from '../services/aegisApi';

interface NBATeam {
    id: string;
    name: string;
    abbreviation: string;
}

interface OrbitalContextType {
    selectedPlayer: PlayerProfile | null;
    setSelectedPlayer: (player: PlayerProfile | null) => void;
    activeTeam: NBATeam | null;
    setActiveTeam: (team: NBATeam | null) => void;
    simulationResult: SimulationResult | null;
    setSimulationResult: (result: SimulationResult | null) => void;
}

const OrbitalContext = createContext<OrbitalContextType | undefined>(undefined);

export function OrbitalProvider({ children }: { children: ReactNode }) {
    // Try to hydrate from localStorage on initial mount
    const getInitialPlayer = () => {
        try {
            const stored = localStorage.getItem('quantsight_context');
            if (stored) {
                const parsed = JSON.parse(stored);
                // Check version and timestamp validity (within 24 hours)
                if (parsed.version === '1.0' && parsed.selectedPlayer) {
                    const storedTime = new Date(parsed.timestamp).getTime();
                    const now = new Date().getTime();
                    const hoursDiff = (now - storedTime) / (1000 * 60 * 60);

                    if (hoursDiff < 24 && isNaN(hoursDiff) === false) {
                        console.log('[ORBITAL] Hydrated context from localStorage:', parsed.selectedPlayer?.name);
                        return parsed.selectedPlayer || null;
                    }
                }
            }
        } catch (e) {
            console.warn('[ORBITAL] Failed to hydrate from localStorage, clearing:', e);
            // Clear corrupted localStorage
            try {
                localStorage.removeItem('quantsight_context');
            } catch { }
        }
        return null;
    };

    const [selectedPlayer, setSelectedPlayer] = useState<PlayerProfile | null>(getInitialPlayer);
    const [activeTeam, setActiveTeam] = useState<NBATeam | null>(null);
    const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);

    // Persist to localStorage whenever selectedPlayer changes
    useEffect(() => {
        if (selectedPlayer) {
            const contextData = {
                version: '1.0',
                selectedPlayer: {
                    id: selectedPlayer.id,
                    name: selectedPlayer.name,
                    avatar: selectedPlayer.avatar,
                    team: selectedPlayer.team,
                    position: selectedPlayer.position
                },
                timestamp: new Date().toISOString()
            };
            try {
                localStorage.setItem('quantsight_context', JSON.stringify(contextData));
                console.log('[ORBITAL] Persisted context to localStorage');
            } catch (e) {
                console.warn('[ORBITAL] Failed to persist to localStorage:', e);
            }
        }
    }, [selectedPlayer]);

    return (
        <OrbitalContext.Provider value={{
            selectedPlayer,
            setSelectedPlayer,
            activeTeam,
            setActiveTeam,
            simulationResult,
            setSimulationResult
        }}>
            {children}
        </OrbitalContext.Provider>
    );
}

export function useOrbital() {
    const context = useContext(OrbitalContext);
    if (context === undefined) {
        throw new Error('useOrbital must be used within an OrbitalProvider');
    }
    return context;
}
