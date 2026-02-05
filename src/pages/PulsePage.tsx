/**
 * The Pulse Page - Live Stats Dashboard
 * ======================================
 * Uses SSE-based useLiveStats hook with gold pulse animation on stat increases.
 */
import React from 'react';
import './MatchupLabPage.css'; // Reusing glass card styles
import { useLiveStats, usePlayerPulse, LivePlayerStat, LiveGame } from '../hooks/useLiveStats';

// Player row with pulse animation
interface PlayerRowProps {
    player: LivePlayerStat;
    rank: number;
    changedPlayerIds: Set<string>;
}

const PlayerRow: React.FC<PlayerRowProps> = ({ player, rank, changedPlayerIds }) => {
    const isPulsing = usePlayerPulse(player.player_id, changedPlayerIds, 3000);

    return (
        <tr
            className={`border-b border-white/5 hover:bg-white/5 transition-colors ${rank === 1 ? 'bg-yellow-500/10' : ''
                } ${isPulsing ? 'animate-gold-pulse' : ''}`}
            style={isPulsing ? {
                boxShadow: '0 0 15px rgba(255, 215, 0, 0.5)',
                backgroundColor: 'rgba(255, 215, 0, 0.1)'
            } : undefined}
        >
            <td className="p-4 font-mono text-gray-500">#{rank}</td>
            <td className="p-4 font-bold text-white flex items-center gap-3">
                {player.name}
                {rank === 1 && <span className="text-yellow-400 animate-pulse">👑</span>}
                {isPulsing && <span className="text-yellow-400">✨</span>}
            </td>
            <td className="p-4 text-gray-400">{player.team}</td>
            <td className="p-4 text-right font-mono text-gray-300">{player.stats.pts}</td>
            <td className="p-4 text-right font-mono text-gray-300">{player.stats.reb}</td>
            <td className="p-4 text-right font-mono text-gray-300">{player.stats.ast}</td>
            <td className="p-4 text-right font-mono font-bold text-yellow-400">
                {(player.pie * 100).toFixed(1)}%
            </td>
        </tr>
    );
};

// Game chip for the ticker - now clickable for LIVE and FINAL games
interface GameChipProps {
    game: LiveGame;
    isSelected: boolean;
    onSelect: (gameId: string) => void;
}

const GameChip: React.FC<GameChipProps> = ({ game, isSelected, onSelect }) => {
    const isLive = game.status === 'LIVE';
    const isFinal = game.status === 'FINAL';
    const isClickable = isLive || isFinal; // Allow clicking on LIVE or FINAL games

    return (
        <button
            onClick={() => isClickable && onSelect(game.game_id)}
            disabled={!isClickable}
            className={`flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all
                ${isSelected
                    ? 'border-2 border-yellow-400/80 cursor-pointer'
                    : isLive
                        ? 'border-2 border-red-500/50 hover:border-red-500/70 cursor-pointer animate-pulse'
                        : isFinal
                            ? 'bg-white/5 border-2 border-green-500/30 hover:border-green-500/50 cursor-pointer'
                            : 'bg-white/5 border border-transparent opacity-50 cursor-not-allowed'
                }`}
        >
            {isLive && <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />}
            {isFinal && <span className="text-green-400 text-xs">✓</span>}
            <span className="text-gray-400">{game.home_team}</span>
            <span className="font-mono font-bold text-white">
                {game.home_score}-{game.away_score}
            </span>
            <span className="text-gray-400">{game.away_team}</span>
            {isLive && <span className="text-xs text-gray-500 ml-1">{game.clock}</span>}
            {isFinal && <span className="text-xs text-green-500/50 ml-1">FINAL</span>}
        </button>
    );
};

const PulsePage: React.FC = () => {
    const {
        games,
        leaders,
        liveCount,
        isConnected,
        isConnecting,
        lastUpdate,
        changedPlayerIds
    } = useLiveStats();

    // State for selected game (null = show all live games)
    const [selectedGameId, setSelectedGameId] = React.useState<string | null>(null);

    // Sort games: LIVE first, then FINAL
    const sortedGames = [...games].sort((a, b) => {
        const order = { 'LIVE': 0, 'HALFTIME': 1, 'FINAL': 2, 'UPCOMING': 3 };
        return (order[a.status] || 4) - (order[b.status] || 4);
    });

    // Get selected game or first live game
    const featuredGame = selectedGameId
        ? games.find(g => g.game_id === selectedGameId)
        : games.find(g => g.status === 'LIVE');

    // Filter leaders by selected game and split by home/away teams
    const { homePlayers, awayPlayers } = React.useMemo(() => {
        let allLeaders = leaders;

        // If game selected, filter to that game's players
        if (selectedGameId) {
            const game = games.find(g => g.game_id === selectedGameId);
            if (game) {
                allLeaders = game.leaders || [];
            }
        }

        // Filter to players with points > 0
        const scoringPlayers = allLeaders.filter(p => p.stats.pts > 0);

        // Split by team (if we have a featured game)
        if (featuredGame) {
            const home = scoringPlayers
                .filter(p => p.team === featuredGame.home_team)
                .sort((a, b) => b.pie - a.pie);
            const away = scoringPlayers
                .filter(p => p.team === featuredGame.away_team)
                .sort((a, b) => b.pie - a.pie);
            return { homePlayers: home, awayPlayers: away };
        }

        return {
            homePlayers: scoringPlayers.sort((a, b) => b.pie - a.pie),
            awayPlayers: []
        };
    }, [selectedGameId, games, leaders, featuredGame]);

    return (
        <div className="matchup-lab-page h-full overflow-y-auto p-8">
            <header className="lab-header mb-8">
                <div className="header-content">
                    <div className="header-title">
                        <span className="lab-icon text-red-500 animate-pulse">❤️</span>
                        <h1>The Pulse</h1>
                        <span className={`ai-badge ${isConnected
                            ? 'bg-green-500/20 text-green-400 border-green-500/30'
                            : isConnecting
                                ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
                                : 'bg-red-500/20 text-red-400 border-red-500/30'
                            } border`}>
                            <span className={`inline-block w-2 h-2 rounded-full mr-2 ${isConnected ? 'bg-green-500' : isConnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
                                }`} />
                            {isConnected ? 'LIVE SSE' : isConnecting ? 'CONNECTING...' : 'DISCONNECTED'}
                        </span>
                    </div>
                    {lastUpdate && (
                        <div className="text-xs text-gray-500 mt-2">
                            Last update: {new Date(lastUpdate).toLocaleTimeString()}
                        </div>
                    )}
                </div>
            </header>

            {/* Game Ticker */}
            {games.length > 0 && (
                <div className="flex gap-3 overflow-x-auto pb-4 mb-6">
                    {sortedGames.map(game => (
                        <GameChip
                            key={game.game_id}
                            game={game}
                            isSelected={selectedGameId === game.game_id}
                            onSelect={setSelectedGameId}
                        />
                    ))}
                </div>
            )}

            <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">

                {/* LEFT COLUMN: Featured Live Game */}
                <div className="lg:col-span-4 flex flex-col gap-6">
                    <div className="glass-card p-6 relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-red-500 to-transparent opacity-50" />

                        <div className="flex justify-between items-center mb-6">
                            <span className="text-gray-400 font-mono text-sm">
                                {liveCount} LIVE GAME{liveCount !== 1 ? 'S' : ''}
                            </span>
                            <span className="live-pill px-3 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-bold border border-red-500/30 flex items-center gap-2">
                                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                                SSE ACTIVE
                            </span>
                        </div>

                        {featuredGame ? (
                            <>
                                <div className="text-center mb-8">
                                    <div className="text-5xl font-bold font-mono tracking-tighter text-white mb-2">
                                        {featuredGame.clock}
                                    </div>
                                    <div className="text-gray-400 text-sm tracking-widest uppercase">
                                        Q{featuredGame.period}
                                    </div>
                                </div>

                                <div className="flex justify-between items-center px-4 mb-8">
                                    <div className="text-center">
                                        <div className="text-4xl font-bold text-white mb-1">{featuredGame.home_score}</div>
                                        <div className="text-lg text-gray-400 font-bold">{featuredGame.home_team}</div>
                                    </div>
                                    <div className="text-2xl font-mono text-gray-600">vs</div>
                                    <div className="text-center">
                                        <div className="text-4xl font-bold text-white mb-1">{featuredGame.away_score}</div>
                                        <div className="text-lg text-gray-400 font-bold">{featuredGame.away_team}</div>
                                    </div>
                                </div>

                                <div className="bg-white/5 rounded-lg p-4 text-center">
                                    <div className="text-xs text-gray-500 uppercase mb-1">Differential</div>
                                    <div className={`text-2xl font-bold font-mono ${Math.abs(featuredGame.home_score - featuredGame.away_score) <= 5
                                        ? 'text-yellow-400 animate-pulse'
                                        : 'text-white'
                                        }`}>
                                        {Math.abs(featuredGame.home_score - featuredGame.away_score)} PTS
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="text-center py-8 text-gray-500">
                                <div className="text-4xl mb-4">🏀</div>
                                <div>No live games right now</div>
                            </div>
                        )}
                    </div>

                    {/* Connection Status Card */}
                    <div className="glass-card p-4 opacity-75">
                        <div className="text-xs text-gray-500 font-mono mb-2 uppercase border-b border-white/5 pb-2">
                            SSE Connection Status
                        </div>
                        <div className="text-sm space-y-1">
                            <div className="flex justify-between">
                                <span className="text-gray-500">Stream:</span>
                                <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
                                    {isConnected ? 'Connected' : 'Disconnected'}
                                </span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">Games Cached:</span>
                                <span className="text-gray-300">{games.length}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-500">Leaders Tracked:</span>
                                <span className="text-gray-300">{leaders.length}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* RIGHT COLUMN: Live Alpha Leaderboard */}
                <div className="lg:col-span-8">
                    <div className="glass-card h-full flex flex-col">
                        <div className="card-header p-6 border-b border-white/10 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <span className="text-2xl">⚡</span>
                                <h2 className="text-xl font-bold text-white">Live Alpha Leaderboard</h2>
                            </div>
                            <div className="text-xs text-gray-400 bg-white/5 px-3 py-1 rounded-full">
                                SORTED BY: <span className="text-yellow-400 font-bold">IN-GAME PIE</span>
                            </div>
                        </div>

                        <div className="p-0 overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b border-white/5 text-gray-400 text-xs uppercase tracking-wider">
                                        <th className="p-4 font-medium">Rank</th>
                                        <th className="p-4 font-medium">Player</th>
                                        <th className="p-4 font-medium">Team</th>
                                        <th className="p-4 font-medium text-right">PTS</th>
                                        <th className="p-4 font-medium text-right">REB</th>
                                        <th className="p-4 font-medium text-right">AST</th>
                                        <th className="p-4 font-medium text-right text-yellow-500">PIE %</th>
                                    </tr>
                                </thead>
                                <tbody className="text-sm">
                                    {/* HOME TEAM SECTION */}
                                    {featuredGame && homePlayers.length > 0 && (
                                        <>
                                            <tr className="bg-blue-500/10 border-b border-blue-500/20">
                                                <td colSpan={7} className="p-2 text-blue-400 font-black text-xs uppercase tracking-widest">
                                                    🏠 {featuredGame.home_team} (HOME)
                                                </td>
                                            </tr>
                                            {homePlayers.map((player, idx) => (
                                                <PlayerRow
                                                    key={player.player_id}
                                                    player={player}
                                                    rank={idx + 1}
                                                    changedPlayerIds={changedPlayerIds}
                                                />
                                            ))}
                                        </>
                                    )}

                                    {/* AWAY TEAM SECTION */}
                                    {featuredGame && awayPlayers.length > 0 && (
                                        <>
                                            <tr className="bg-orange-500/10 border-b border-orange-500/20">
                                                <td colSpan={7} className="p-2 text-orange-400 font-black text-xs uppercase tracking-widest">
                                                    ✈️ {featuredGame.away_team} (AWAY)
                                                </td>
                                            </tr>
                                            {awayPlayers.map((player, idx) => (
                                                <PlayerRow
                                                    key={player.player_id}
                                                    player={player}
                                                    rank={idx + 1}
                                                    changedPlayerIds={changedPlayerIds}
                                                />
                                            ))}
                                        </>
                                    )}

                                    {/* NO DATA MESSAGE */}
                                    {homePlayers.length === 0 && awayPlayers.length === 0 && (
                                        <tr>
                                            <td colSpan={7} className="p-8 text-center text-gray-500">
                                                {isConnected
                                                    ? 'Waiting for scoring plays...'
                                                    : 'Establish link to begin stream'}
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default PulsePage;
