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

interface HistoricalGame {
    gameId: string;
    nbaId?: string;
    homeTeam: string;
    awayTeam: string;
    status: string;
    startTime?: string;
    hasPbp?: boolean;
    scoreHome?: number;
    scoreAway?: number;
}

interface Props {
    activeGameId: string | null;
    onSelectGame: (gameId: string) => void;
    onSelectGameFull?: (game: HistoricalGame) => void;
    date?: string;
    isLiveMode?: boolean;
}

export function LiveGameSelector({ activeGameId, onSelectGame, onSelectGameFull, date, isLiveMode = true }: Props) {
    const [liveGames, setLiveGames] = useState<LiveGame[]>([]);
    const [historicalGames, setHistoricalGames] = useState<HistoricalGame[]>([]);
    const [loading, setLoading] = useState(true);

    // ── Live mode: poll /v1/games/live every 60s ─────────────────────────────
    useEffect(() => {
        if (!isLiveMode) return;
        setLoading(true);
        const fetchGames = async () => {
            try {
                const res = await ApiContract.executeWeb<{ games: LiveGame[] }>({
                    path: 'v1/games/live'
                });
                if (res && res.games) setLiveGames(res.games);
            } catch (e) {
                console.error('Failed to fetch live games:', e);
            } finally {
                setLoading(false);
            }
        };
        fetchGames();
        const interval = setInterval(fetchGames, 60000);
        return () => clearInterval(interval);
    }, [isLiveMode]);

    // ── Historical mode: fetch /v1/games/by-date/{date} when date changes ─────
    useEffect(() => {
        if (isLiveMode || !date) return;
        setLoading(true);
        setHistoricalGames([]);
        ApiContract.executeWeb<{ games: HistoricalGame[] }>({
        path: `v1/games/by-date/${date}`
        }).then(res => {
            const all = res?.games ?? [];
            setHistoricalGames(all);
            // Auto-select first game that has PBP data, so the feed loads immediately
            const withPbp = all.find((g: HistoricalGame) => g.hasPbp);
            if (withPbp) {
                onSelectGame(withPbp.gameId);
                if (onSelectGameFull) onSelectGameFull(withPbp);
            }
        }).catch(e => {
            console.error('Failed to fetch historical games:', e);
        }).finally(() => setLoading(false));
    }, [date, isLiveMode]);

    // ── Loading skeleton ──────────────────────────────────────────────────────
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

    // ── Live mode render ──────────────────────────────────────────────────────
    if (isLiveMode) {
        if (liveGames.length === 0) {
            return (
                <div style={{ color: '#64748b', fontSize: '13px', padding: '8px 0' }}>
                    No live games right now.
                </div>
            );
        }
        return (
            <div className="game-selector-row">
                {liveGames.map(g => {
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

    // ── Historical mode render ─────────────────────────────────────────────────
    if (historicalGames.length === 0) {
        return (
            <div style={{ color: '#64748b', fontSize: '13px', padding: '8px 0' }}>
                No games found for {date}.
            </div>
        );
    }
    return (
        <div className="game-selector-row">
            {historicalGames.map(g => {
                const isActive = g.gameId === activeGameId;
                const label = (g.awayTeam && g.homeTeam)
                    ? `${g.awayTeam} @ ${g.homeTeam}`
                    : g.gameId;
                const hasScore = g.scoreHome !== undefined && g.scoreAway !== undefined;
                return (
                    <button
                        key={g.gameId}
                        className={`game-selector-btn ${isActive ? 'active' : ''} ${!g.hasPbp ? 'no-pbp' : ''}`}
                        onClick={() => {
                            onSelectGame(g.gameId);
                            if (onSelectGameFull) onSelectGameFull(g);
                        }}
                        title={g.hasPbp ? 'Play-by-play available' : 'No play-by-play data for this game'}
                    >
                        <span className="game-btn-label">{label}</span>
                        {hasScore && (
                            <span className="game-btn-score">
                                {g.scoreAway}–{g.scoreHome}
                            </span>
                        )}
                        {g.hasPbp && <span className="pbp-available-badge">PBP</span>}
                        {g.status === 'Final' && (
                            <span className="historical-status-badge">FINAL</span>
                        )}
                    </button>
                );
            })}
        </div>
    );
}
