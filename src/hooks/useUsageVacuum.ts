import { useState, useCallback } from 'react';

interface RedistributionResult {
    player_id: string;
    player_name: string;
    usage_change: number;
    pts_ev_change: number;
    ast_ev_change: number;
    reb_ev_change: number;
}

interface UseUsageVacuumReturn {
    toggleInjury: (playerId: string) => Promise<void>;
    injuredPlayers: Set<string>;
    redistribution: RedistributionResult[];
    isCalculating: boolean;
    error: Error | null;
    reset: () => void;
}

export function useUsageVacuum(
    teamId: string,
    roster: { player_id: string; name: string; usage: number }[]
): UseUsageVacuumReturn {
    const [injuredPlayers, setInjuredPlayers] = useState<Set<string>>(new Set());
    const [redistribution, setRedistribution] = useState<RedistributionResult[]>([]);
    const [isCalculating, setIsCalculating] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const reset = useCallback(() => {
        setInjuredPlayers(new Set());
        setRedistribution([]);
        setError(null);
    }, []);

    const toggleInjury = useCallback(async (playerId: string) => {
        const newInjured = new Set(injuredPlayers);

        if (newInjured.has(playerId)) {
            newInjured.delete(playerId);
        } else {
            newInjured.add(playerId);
        }

        setInjuredPlayers(newInjured);
        setIsCalculating(true);
        setError(null);

        try {
            const response = await fetch('http://localhost:5000/usage-vacuum/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    team_id: teamId,
                    injured_player_ids: Array.from(newInjured),
                    remaining_roster: roster
                        .filter(p => !newInjured.has(p.player_id))
                        .map(p => ({
                            player_id: p.player_id,
                            name: p.name,
                            usage: p.usage
                        }))
                })
            });

            if (response.ok) {
                const data = await response.json();
                setRedistribution(data.redistribution || []);
            } else {
                throw new Error('Failed to calculate redistribution');
            }
        } catch (err) {
            setError(err as Error);
            console.error('[UsageVacuum] Error:', err);
        } finally {
            setIsCalculating(false);
        }
    }, [injuredPlayers, teamId, roster]);

    return {
        toggleInjury,
        injuredPlayers,
        redistribution,
        isCalculating,
        error,
        reset
    };
}

export default useUsageVacuum;
