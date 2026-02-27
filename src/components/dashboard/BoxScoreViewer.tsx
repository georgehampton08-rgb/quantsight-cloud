import React, { useEffect, useState, useCallback } from 'react';
import { Focus, User, Activity, Crosshair, ChevronRight } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

interface BoxScorePlayer {
    player_id: string;
    player_name: string;
    team_abbreviation: string;
    start_position: string | null;
    min: string | null;
    pts: number;
    reb: number;
    ast: number;
    stl: number;
    blk: number;
    tov: number;
    fgm: number;
    fga: number;
    fg3m: number;
    fg3a: number;
    ftm: number;
    fta: number;
    plus_minus: number;
}

interface BoxScoreGame {
    gameId: string;
    game_id?: string;
    game_date?: string;
    matchup?: string;
    home: string;
    away: string;
    home_team?: string | any;
    away_team?: string | any;
    home_score: number;
    away_score: number;
    status: string;
    volatility?: string;
}

export function BoxScoreViewerContent() {
    const [loading, setLoading] = useState(false);
    const [games, setGames] = useState<BoxScoreGame[]>([]);
    const [selectedGame, setSelectedGame] = useState<string | null>(null);
    const [boxScores, setBoxScores] = useState<{
        home: BoxScorePlayer[],
        away: BoxScorePlayer[],
        game_info?: BoxScoreGame
    } | null>(null);

    // Fetch tonight's games to populate the selector
    const loadGames = useCallback(async () => {
        setLoading(true);
        try {
            const res = await ApiContract.execute<{ games: BoxScoreGame[] }>(null, {
                path: 'schedule'
            });
            if (res.data?.games) {
                setGames(res.data.games);
                // Auto-select first game with a score if available
                const firstStarted = res.data.games.find(g => g.status === 'LIVE' || g.status === 'FINAL');
                if (firstStarted) {
                    setSelectedGame(firstStarted.gameId || firstStarted.game_id || null);
                } else if (res.data.games.length > 0) {
                    setSelectedGame(res.data.games[0].gameId || res.data.games[0].game_id || null);
                }
            }
        } catch (e) {
            console.error("Failed to load schedule", e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadGames();
    }, [loadGames]);

    // Fetch box score when a game is selected
    useEffect(() => {
        const loadBoxScore = async () => {
            if (!selectedGame) return;
            setLoading(true);
            try {
                // Determine if we need to fetch live pulse data or standard box score
                // We'll try pulse first since it's the new standard
                let liveDataUrl = `pulse/boxscore/${selectedGame}`;
                // Fallback or generic endpoint if pulse fails? 
                // For now, assume the backend has a unified boxscore endpoint or pulse

                const res = await ApiContract.execute<any>(null, {
                    path: liveDataUrl
                });

                if (res.data) {
                    setBoxScores(res.data);
                }
            } catch (e) {
                console.warn(`Failed to fetch pulse boxscore for ${selectedGame}, trying fallback...`, e);
                // Try legacy /boxscore/{game_id} if it exists, or just clear
                try {
                    const fallback = await ApiContract.execute<any>(null, {
                        path: `boxscore/${selectedGame}`
                    });
                    if (fallback.data && fallback.data.home_team) {
                        setBoxScores({
                            home: fallback.data.home_team.players || [],
                            away: fallback.data.away_team.players || [],
                            game_info: {
                                gameId: fallback.data.game_id || selectedGame,
                                game_id: fallback.data.game_id || selectedGame,
                                home_team: fallback.data.home_team.abbreviation,
                                away_team: fallback.data.away_team.abbreviation,
                                home: fallback.data.home_team.abbreviation,
                                away: fallback.data.away_team.abbreviation,
                                home_score: games.find(g => (g.game_id || g.gameId) === selectedGame)?.home_score || 0,
                                away_score: games.find(g => (g.game_id || g.gameId) === selectedGame)?.away_score || 0,
                                status: games.find(g => (g.game_id || g.gameId) === selectedGame)?.status || 'FINAL',
                                game_date: '',
                                matchup: ''
                            }
                        });
                    } else {
                        setBoxScores(fallback.data); // in case already shaped correctly
                    }
                } catch (e2) {
                    console.error("Fallback boxscore fetch failed", e2);
                    setBoxScores(null);
                }
            } finally {
                setLoading(false);
            }
        };

        if (selectedGame) {
            loadBoxScore();
        }
    }, [selectedGame]);

    const renderPlayerRow = (p: BoxScorePlayer) => {
        const dnp = p.min === null || p.min === "0:00" || p.min === "";
        const efficiency = dnp ? 0 : (p.pts + p.reb + p.ast + p.stl + p.blk - (p.fga - p.fgm) - (p.fta - p.ftm) - p.tov);
        const getPtsColor = (pts: number) => pts >= 30 ? 'text-emerald-400 font-bold' : pts >= 20 ? 'text-emerald-500/80 font-bold' : 'text-slate-300';

        return (
            <tr key={p.player_id} className="bg-slate-900/40 hover:bg-slate-800/60 transition-colors border-b border-slate-800/50 last:border-0 group">
                <td className="px-3 py-2 sm:px-4 sm:py-3 whitespace-nowrap sticky left-0 z-10 bg-slate-900/90 group-hover:bg-slate-800/90 backdrop-blur-sm shadow-[4px_0_8px_rgba(0,0,0,0.1)] transition-colors border-r border-slate-800/30">
                    <div className="flex items-center gap-2">
                        {p.start_position && <span className="text-[10px] bg-slate-800 text-slate-400 px-1 py-0.5 rounded font-bold w-6 text-center">{p.start_position}</span>}
                        <span className={`text-xs sm:text-sm font-bold ${dnp ? 'text-slate-500' : 'text-slate-200'}`}>{p.player_name}</span>
                    </div>
                </td>
                {dnp ? (
                    <td colSpan={8} className="px-4 py-3 text-xs text-slate-500 italic text-center uppercase tracking-widest">
                        Did Not Play / Active
                    </td>
                ) : (
                    <>
                        <td className="px-3 py-2 sm:px-4 sm:py-3 text-center text-xs text-slate-400 font-mono">{p.min}</td>
                        <td className={`px-3 py-2 sm:px-4 sm:py-3 text-center text-xs sm:text-sm ${getPtsColor(p.pts)}`}>{p.pts}</td>
                        <td className="px-3 py-2 sm:px-4 sm:py-3 text-center text-xs sm:text-sm text-slate-300">{p.reb}</td>
                        <td className="px-3 py-2 sm:px-4 sm:py-3 text-center text-xs sm:text-sm text-slate-300">{p.ast}</td>
                        <td className="px-3 py-2 sm:px-4 sm:py-3 text-center text-xs text-slate-400 font-mono hidden sm:table-cell">{p.fgm}/{p.fga}</td>
                        <td className="px-3 py-2 sm:px-4 sm:py-3 text-center text-xs text-slate-400 font-mono hidden md:table-cell">{p.fg3m}/{p.fg3a}</td>
                        <td className={`px-3 py-2 sm:px-4 sm:py-3 text-center text-xs sm:text-sm font-bold ${p.plus_minus > 0 ? 'text-emerald-400' : p.plus_minus < 0 ? 'text-red-400' : 'text-slate-500'}`}>
                            {p.plus_minus > 0 ? `+${p.plus_minus}` : p.plus_minus}
                        </td>
                        <td className="px-3 py-2 sm:px-4 sm:py-3 text-center text-xs text-slate-500 font-mono">{efficiency}</td>
                    </>
                )}
            </tr>
        );
    };

    return (
        <div className="h-full flex flex-col space-y-4">
            {/* Game Selector Strip */}
            <div className="flex gap-2.5 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-slate-700 hover:scrollbar-thumb-slate-600">
                {games.map(game => (
                    <button
                        key={(game.game_id || game.gameId)}
                        onClick={() => setSelectedGame((game.game_id || game.gameId))}
                        className={`flex-shrink-0 px-4 py-3 border rounded-xl flex flex-col items-center gap-1 transition-all min-w-[140px] ${selectedGame === (game.game_id || game.gameId)
                            ? 'bg-indigo-900/30 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.2)]'
                            : 'bg-slate-800/40 border-slate-700/50 hover:bg-slate-800/80 hover:border-slate-500/50 text-slate-400'
                            }`}
                    >
                        <div className="flex items-center gap-3 w-full justify-between px-1">
                            <span className={`font-black text-sm ${selectedGame === (game.game_id || game.gameId) ? 'text-white' : ''}`}>{game.away || game.away_team}</span>
                            <span className={`text-[10px] px-1.5 py-[1px] rounded font-bold uppercase tracking-wider ${game.status === 'LIVE' ? 'bg-red-500/20 text-red-400 animate-pulse' :
                                game.status === 'FINAL' ? 'bg-slate-700/50 text-slate-400' :
                                    'bg-emerald-500/10 text-emerald-500'
                                }`}>
                                {game.status === 'LIVE' ? 'LIVE' : game.status === 'FINAL' ? 'FNL' : 'UP'}
                            </span>
                            <span className={`font-black text-sm ${selectedGame === (game.game_id || game.gameId) ? 'text-white' : ''}`}>{game.home || game.home_team}</span>
                        </div>
                        <div className="flex items-center justify-between w-full px-2 mt-1">
                            <span className={`font-mono text-sm ${game.away_score > game.home_score ? 'text-emerald-400 font-bold' : ''}`}>{game.away_score || '-'}</span>
                            <span className="text-slate-600 text-[10px]">vs</span>
                            <span className={`font-mono text-sm ${game.home_score > game.away_score ? 'text-emerald-400 font-bold' : ''}`}>{game.home_score || '-'}</span>
                        </div>
                    </button>
                ))}
            </div>

            {/* Box Score Content */}
            {loading ? (
                <div className="flex-1 flex flex-col items-center justify-center p-12 bg-slate-900/30 border border-slate-800 rounded-2xl">
                    <Activity className="w-8 h-8 text-indigo-400 animate-spin mb-4" />
                    <div className="text-sm font-mono text-slate-400 tracking-widest uppercase">Hydrating Telemetry...</div>
                </div>
            ) : !boxScores ? (
                <div className="flex-1 flex flex-col items-center justify-center p-12 bg-slate-900/30 border border-slate-800 rounded-2xl text-slate-500">
                    <Focus className="w-12 h-12 mb-4 opacity-50" />
                    <p className="font-medium text-lg text-slate-400">Box Score Data Unavailable</p>
                    <p className="text-sm mt-2 max-w-sm text-center">
                        Telemetry has not hydrated for this matchup yet. If the game is live, ensure Pulse Sync is active.
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 flex-1 min-h-0">

                    {/* AWAY TEAM */}
                    <div className="flex flex-col bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl">
                        <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700/50 flex justify-between items-center">
                            <h3 className="text-lg font-black text-white tracking-widest">{boxScores.game_info?.away_team || 'AWAY'}</h3>
                            <span className="text-2xl font-mono text-emerald-400 font-bold">{boxScores.game_info?.away_score}</span>
                        </div>
                        <div className="overflow-x-auto flex-1 h-[400px] xl:h-auto overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
                            <table className="w-full text-left relative">
                                <thead className="text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-900/90 sticky top-0 z-20 shadow-sm backdrop-blur-md border-b border-slate-700/50">
                                    <tr>
                                        <th className="px-3 py-3 sm:px-4 sticky left-0 z-30 bg-slate-900/95 backdrop-blur-sm shadow-[4px_0_8px_rgba(0,0,0,0.1)] border-r border-slate-800/30">Player</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">MIN</th>
                                        <th className="px-3 py-3 sm:px-4 text-center text-slate-200">PTS</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">REB</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">AST</th>
                                        <th className="px-3 py-3 sm:px-4 text-center hidden sm:table-cell">FG</th>
                                        <th className="px-3 py-3 sm:px-4 text-center hidden md:table-cell">3PT</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">+/-</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">EFF</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {boxScores.away.map(renderPlayerRow)}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* HOME TEAM */}
                    <div className="flex flex-col bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl">
                        <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700/50 flex justify-between items-center">
                            <h3 className="text-lg font-black text-white tracking-widest">{boxScores.game_info?.home_team || 'HOME'}</h3>
                            <span className="text-2xl font-mono text-emerald-400 font-bold">{boxScores.game_info?.home_score}</span>
                        </div>
                        <div className="overflow-x-auto flex-1 h-[400px] xl:h-auto overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
                            <table className="w-full text-left relative">
                                <thead className="text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-900/90 sticky top-0 z-20 shadow-sm backdrop-blur-md border-b border-slate-700/50">
                                    <tr>
                                        <th className="px-3 py-3 sm:px-4 sticky left-0 z-30 bg-slate-900/95 backdrop-blur-sm shadow-[4px_0_8px_rgba(0,0,0,0.1)] border-r border-slate-800/30">Player</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">MIN</th>
                                        <th className="px-3 py-3 sm:px-4 text-center text-slate-200">PTS</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">REB</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">AST</th>
                                        <th className="px-3 py-3 sm:px-4 text-center hidden sm:table-cell">FG</th>
                                        <th className="px-3 py-3 sm:px-4 text-center hidden md:table-cell">3PT</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">+/-</th>
                                        <th className="px-3 py-3 sm:px-4 text-center">EFF</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {boxScores.home.map(renderPlayerRow)}
                                </tbody>
                            </table>
                        </div>
                    </div>

                </div>
            )}
        </div>
    );
}

export const BoxScoreViewer = () => (
    <SectionErrorBoundary fallbackMessage="BoxScore Matrix Viewer offline">
        <BoxScoreViewerContent />
    </SectionErrorBoundary>
);
