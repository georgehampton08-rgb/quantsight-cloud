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
                console.error("Failed to fetch live games:", e);
            } finally {
                setLoading(false);
            }
        };
        fetchGames();

        // Refresh schedule every minute just in case
        const interval = setInterval(fetchGames, 60000);
        return () => clearInterval(interval);
    }, []);

    if (loading) return <div style={{ color: '#94a3b8' }}>Loading schedule...</div>;
    if (games.length === 0) return <div style={{ color: '#94a3b8' }}>No active games right now.</div>;

    return (
        <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', padding: '10px 0', marginBottom: '20px' }}>
            {games.map(g => {
                const isActive = g.game_id === activeGameId;
                return (
                    <button
                        key={g.game_id}
                        onClick={() => onSelectGame(g.game_id)}
                        style={{
                            padding: '10px 16px',
                            borderRadius: '8px',
                            background: isActive ? '#38bdf8' : '#1e293b',
                            color: isActive ? '#0f172a' : '#f8fafc',
                            border: isActive ? 'none' : '1px solid rgba(255,255,255,0.1)',
                            cursor: 'pointer',
                            fontWeight: 600,
                            flexShrink: 0
                        }}
                    >
                        {g.name}
                        {g.state === 'in' && <span style={{ marginLeft: '8px', color: isActive ? '#ef4444' : '#ef4444' }}>•</span>}
                    </button>
                );
            })}
        </div>
    );
}
