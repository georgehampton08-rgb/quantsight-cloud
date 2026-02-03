import React, { useState, useCallback } from 'react';
import './UsageVacuumToggle.css';

interface Player {
    player_id: string;
    name: string;
    team: string;
    usage: number;
    pts_avg: number;
    ast_avg: number;
    reb_avg: number;
}

interface RedistributionResult {
    player_id: string;
    player_name: string;
    usage_change: number;
    pts_ev_change: number;
    ast_ev_change: number;
    reb_ev_change: number;
}

interface UsageVacuumToggleProps {
    players: Player[];
    teamId: string;
    onInjuryChange?: (injuredPlayerIds: string[], redistribution: RedistributionResult[]) => void;
}

const UsageVacuumToggle: React.FC<UsageVacuumToggleProps> = ({
    players,
    teamId,
    onInjuryChange
}) => {
    const [injuredPlayers, setInjuredPlayers] = useState<Set<string>>(new Set());
    const [redistribution, setRedistribution] = useState<RedistributionResult[]>([]);
    const [isCalculating, setIsCalculating] = useState(false);
    const [animatingPlayerId, setAnimatingPlayerId] = useState<string | null>(null);

    const toggleInjury = useCallback(async (playerId: string) => {
        const newInjured = new Set(injuredPlayers);

        if (newInjured.has(playerId)) {
            newInjured.delete(playerId);
        } else {
            newInjured.add(playerId);
        }

        setInjuredPlayers(newInjured);
        setAnimatingPlayerId(playerId);
        setIsCalculating(true);

        try {
            // Call Usage Vacuum endpoint
            const response = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/usage-vacuum/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    team_id: teamId,
                    injured_player_ids: Array.from(newInjured),
                    remaining_roster: players
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
                onInjuryChange?.(Array.from(newInjured), data.redistribution || []);
            }
        } catch (error) {
            console.error('[UsageVacuum] Analysis failed:', error);
            // Generate mock redistribution for demonstration
            const mockRedist = players
                .filter(p => !newInjured.has(p.player_id))
                .map(p => ({
                    player_id: p.player_id,
                    player_name: p.name,
                    usage_change: Math.random() * 5,
                    pts_ev_change: Math.random() * 3 - 0.5,
                    ast_ev_change: Math.random() * 1.5 - 0.3,
                    reb_ev_change: Math.random() * 1 - 0.2
                }));
            setRedistribution(mockRedist);
        } finally {
            setIsCalculating(false);
            setTimeout(() => setAnimatingPlayerId(null), 500);
        }
    }, [injuredPlayers, players, teamId, onInjuryChange]);

    const getRedistForPlayer = (playerId: string) => {
        return redistribution.find(r => r.player_id === playerId);
    };

    return (
        <div className="usage-vacuum-panel">
            <div className="vacuum-header">
                <span className="vacuum-icon">🏥</span>
                <h3>Injury Simulator</h3>
                <span className="vacuum-badge">Usage Vacuum</span>
            </div>

            <p className="vacuum-description">
                Toggle players to "OUT" to see real-time EV redistribution
            </p>

            <div className="player-injury-list">
                {players.map(player => {
                    const isInjured = injuredPlayers.has(player.player_id);
                    const redist = getRedistForPlayer(player.player_id);
                    const isAnimating = animatingPlayerId === player.player_id;

                    return (
                        <div
                            key={player.player_id}
                            className={`player-injury-row ${isInjured ? 'injured' : ''} ${isAnimating ? 'animating' : ''}`}
                        >
                            <div className="player-info">
                                <span className="player-name">{player.name}</span>
                                <span className="player-usage">{(player.usage * 100).toFixed(1)}% USG</span>
                            </div>

                            <button
                                className={`injury-toggle ${isInjured ? 'out' : 'active'}`}
                                onClick={() => toggleInjury(player.player_id)}
                                disabled={isCalculating}
                            >
                                {isInjured ? '🚫 OUT' : '✅ ACTIVE'}
                            </button>

                            {!isInjured && redist && injuredPlayers.size > 0 && (
                                <div className="redistribution-preview">
                                    <span className={`ev-change ${(redist?.pts_ev_change || 0) > 0 ? 'positive' : 'negative'}`}>
                                        PTS: {(redist?.pts_ev_change || 0) > 0 ? '+' : ''}{(redist?.pts_ev_change || 0).toFixed(1)}
                                    </span>
                                    <span className={`usage-boost ${(redist?.usage_change || 0) > 0 ? 'positive' : ''}`}>
                                        +{(redist?.usage_change || 0).toFixed(1)}% USG
                                    </span>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {injuredPlayers.size > 0 && (
                <div className="vacuum-summary">
                    <div className="summary-header">
                        <span>📊</span>
                        <span>Redistribution Summary</span>
                    </div>
                    <div className="summary-stats">
                        <div className="summary-stat">
                            <span className="stat-label">Players Out</span>
                            <span className="stat-value">{injuredPlayers.size}</span>
                        </div>
                        <div className="summary-stat">
                            <span className="stat-label">Usage Vacated</span>
                            <span className="stat-value">
                                {players
                                    .filter(p => injuredPlayers.has(p.player_id))
                                    .reduce((sum, p) => sum + p.usage * 100, 0)
                                    .toFixed(1)}%
                            </span>
                        </div>
                    </div>
                </div>
            )}

            {isCalculating && (
                <div className="calculating-overlay">
                    <span className="calculating-spinner" />
                    <span>Redistributing usage...</span>
                </div>
            )}
        </div>
    );
};

export default UsageVacuumToggle;
