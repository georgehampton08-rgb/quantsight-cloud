import React, { useState, useEffect } from 'react';
import { ApiContract } from '../../api/client';
import './PlayByPlay.css';

interface LiveGame {
    game_id: string;
    name: string;
    status: string;
    state: string;
    is_tracked?: boolean;
}

interface Props {
    activeGameId: string | null;
    onSelectGame: (gameId: string) => void;
}

export function LiveGameSelector({ activeGameId, onSelectGame }: Props) {
    const [games, setGames] = useState<LiveGame[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchGames = async () => {
            try {
                const res = await ApiContract.executeWeb<{ games: LiveGame[] }>({
                    path: 'v1/games/live'
                });
                if (res && res.games) {
                    setGames(res.games);
                }
            } catch (e) {
                console.error('Failed to fetch live games:', e);
            } finally {
                setLoading(false);
            }
        };
        fetchGames();

        // Refresh every 60s in case a game goes live
        const interval = setInterval(fetchGames, 60000);
        return () => clearInterval(interval);
    }, []);

    if (loading) {
        return (
            <div className="game-selector-row">
                {[1, 2, 3].map(i => (
                    <div key={i} className="game-selector-btn" style={{ opacity: 0.4, width: 160, background: '#1e293b' }}>
                        &nbsp;
                    </div>
                ))}
            </div>
        );
    }

    if (games.length === 0) {
        return (
            <div style={{ color: '#64748b', fontSize: '13px', padding: '8px 0' }}>
                No games available right now.
            </div>
        );
    }

    return (
        <div className="game-selector-row">
            {games.map(g => {
                const isActive = g.game_id === activeGameId;
                const isLive = g.state === 'in';
                return (
                    <button
                        key={g.game_id}
                        className={`game-selector-btn ${isActive ? 'active' : ''}`}
                        onClick={() => onSelectGame(g.game_id)}
                    >
                        {g.name}
                        {isLive && <span className="live-dot" />}
                    </button>
                );
            })}
        </div>
    );
}
