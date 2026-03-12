/**
 * The Pulse Page - Live Stats Dashboard
 * ======================================
 * Uses SSE-based useLiveStats hook with gold pulse animation on stat increases.
 */
import React from 'react';
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
            className={`border-b border-pro-border/50 hover:bg-white/[0.03] transition-colors duration-100 ${rank === 1 ? 'bg-amber-500/5' : ''
                } ${isPulsing ? 'animate-gold-pulse' : ''}`}
            style={isPulsing ? {
                boxShadow: '0 0 15px rgba(245, 158, 11, 0.2)', // amber-500
                backgroundColor: 'rgba(245, 158, 11, 0.05)'
            } : undefined}
        >
            <td className="p-2 sm:p-4 font-mono text-pro-muted tracking-wide text-xs sm:text-xs">{String(rank).padStart(2, '0')}</td>
            <td className="p-2 sm:p-4 font-medium font-semibold tracking-normal uppercase text-pro-text flex items-center gap-2 sm:gap-3 text-sm sm:text-base whitespace-nowrap">
                {player.name}
                {isPulsing && <span className="text-amber-500 text-xs font-mono font-bold tabular-nums ml-2 animate-[data-flicker_3s_ease-in-out_infinite]">+</span>}
            </td>
            <td className="p-2 sm:p-4 text-pro-muted font-medium tracking-wide text-xs sm:text-xs hidden sm:table-cell">{player.team}</td>
            <td className="p-2 sm:p-4 text-right font-mono text-pro-text text-sm sm:text-base tabular-nums font-bold">{player.stats.pts}</td>
            <td className="p-2 sm:p-4 text-right font-mono text-pro-muted text-xs sm:text-sm tabular-nums hidden md:table-cell">{player.stats.reb}</td>
            <td className="p-2 sm:p-4 text-right font-mono text-pro-muted text-xs sm:text-sm tabular-nums hidden md:table-cell">{player.stats.ast}</td>
            <td className="p-2 sm:p-4 text-right font-mono font-bold text-amber-500 text-sm sm:text-base tabular-nums">
                {(player.pie * 100).toFixed(1)}%
            </td>
        </tr>
    );
};

// Game chip for the ticker
const GameChip: React.FC<{ game: LiveGame; isActive?: boolean; onClick?: () => void }> = ({ game, isActive, onClick }) => {
    const isLive = game.status === 'LIVE';
    const isFinal = game.status === 'FINAL';
    const periodLabel = game.period > 4 ? `OT${game.period - 4}` : `Q${game.period}`;

    return (
        <div
            onClick={onClick}
            className={`flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-sm border cursor-pointer transition-all duration-100 ${isActive ? 'border-blue-500 bg-blue-500/10 shadow-[0_0_10px_rgba(34,211,238,0.2)]' :
                    isLive ? 'bg-emerald-500/5 border-emerald-500/40 hover:bg-emerald-500/10 text-emerald-500' :
                        'bg-pro-surface border-pro-border hover:bg-white/[0.05] text-pro-muted hover:text-pro-text'
                }`}
        >
            {isLive && <span className="w-1.5 h-1.5 bg-emerald-500 opacity-80 rounded-xl animate-pulse" />}
            <span className="font-medium font-semibold tracking-wide text-xs uppercase">{game.away_team}</span>
            <span className="font-mono font-bold text-pro-text text-sm">
                {game.away_score}-{game.home_score}
            </span>
            <span className="font-medium font-semibold tracking-wide text-xs uppercase">{game.home_team}</span>
            {isLive && game.period > 0 && (
                <span className="text-xs text-emerald-500 font-mono font-bold ml-1 bg-emerald-500/10 px-1.5 py-0.5 border border-emerald-500">
                    {periodLabel} {game.clock}
                </span>
            )}
            {isFinal && (
                <span className="text-xs text-pro-muted font-mono ml-1">FNL</span>
            )}
        </div>
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

    const [selectedGameId, setSelectedGameId] = React.useState<string | null>(null);

    // Sort games: LIVE first
    const sortedGames = [...games].sort((a, b) => {
        const order = { 'LIVE': 0, 'HALFTIME': 1, 'UPCOMING': 2, 'FINAL': 3 };
        return (order[a.status] || 4) - (order[b.status] || 4);
    });

    // Featured game: selected > first live > first upcoming
    const featuredGame = selectedGameId
        ? games.find(g => g.game_id === selectedGameId)
        : games.find(g => g.status === 'LIVE' || g.status === 'HALFTIME') || games.find(g => g.status === 'UPCOMING');

    return (
        <div className="h-full flex flex-col p-4 sm:p-8 bg-pro-bg relative z-10 w-full">
            

            <header className="mb-6 sm:mb-8 flex-shrink-0 relative z-10">
                <div className="header-content">
                    <div className="header-title flex flex-col sm:flex-row items-center gap-2 sm:gap-4">
                        <div className="flex items-center gap-3">
                            <h1 className="text-3xl font-medium font-bold tracking-normal uppercase text-pro-text">The Pulse</h1>
                        </div>
                        <span className={`px-2.5 py-1 text-xs font-medium font-semibold tracking-wide uppercase border whitespace-nowrap ${isConnected
                            ? 'bg-emerald-500/5 text-emerald-500 border-emerald-500'
                            : isConnecting
                                ? 'bg-amber-500/5 text-amber-500 border-amber-500'
                                : 'bg-red-500/5 text-red-500 border-red-500'
                            }`}>
                            <span className={`inline-block w-1.5 h-1.5 rounded-xl mr-1.5 ${isConnected ? 'bg-emerald-500' : isConnecting ? 'bg-amber-500 animate-pulse' : 'bg-red-500'
                                }`} />
                            {isConnected ? 'LIVE FEED' : isConnecting ? 'CONNECTING...' : 'DISCONNECTED'}
                        </span>
                    </div>
                    {lastUpdate && (
                        <div className="text-xs uppercase font-mono tracking-wide text-pro-muted mt-2 text-center sm:text-right w-full sm:w-auto">
                            Last update: {new Date(lastUpdate).toLocaleTimeString()}
                        </div>
                    )}
                </div>
            </header>

            <div className="flex-1 min-h-0 flex flex-col w-full max-w-7xl mx-auto relative z-10">
                {/* Game Ticker */}
                {games.length > 0 && (
                    <div className="flex gap-3 overflow-x-auto pb-4 mb-4 sm:mb-6 flex-shrink-0 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                        {sortedGames.map(game => (
                            <GameChip
                                key={game.game_id}
                                game={game}
                                isActive={selectedGameId === game.game_id}
                                onClick={() => setSelectedGameId(
                                    selectedGameId === game.game_id ? null : game.game_id
                                )}
                            />
                        ))}
                    </div>
                )}

                <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 sm:gap-8 flex-1 min-h-0 overflow-y-auto pr-2 pb-8">

                    {/* LEFT COLUMN: Featured Live Game */}
                    <div className="lg:col-span-4 flex flex-col gap-6">
                        <div className="relative bg-pro-surface p-6 overflow-hidden animate-[stagger-reveal_0.2s_cubic-bezier(0.2,0,0,1)_forwards]" >
                            
                            <div className="absolute inset-x-0 top-0 h-px bg-emerald-500/20 animate-[scan-line_4s_linear_infinite]" />

                            <div className="flex justify-between items-center mb-6 relative z-10 border-b border-pro-border/50 pb-3">
                                <span className="text-pro-muted font-mono tracking-wide text-xs uppercase">
                                    {liveCount} LIVE GAME{liveCount !== 1 ? 'S' : ''}
                                </span>
                                <span className="px-3 py-1 bg-emerald-500/10 text-emerald-500 text-xs font-medium font-semibold tracking-wide uppercase border border-emerald-500 flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-emerald-500 rounded-xl shadow-[0_0_8px_rgba(0,255,136,0.8)] animate-[signal-pulse_2s_ease-in-out_infinite]" />
                                    LIVE POLL
                                </span>
                            </div>

                            {featuredGame ? (
                                <div className="relative z-10">
                                    <div className="text-center mb-8">
                                        <div className="text-5xl font-bold font-mono tabular-nums tracking-tighter text-pro-text mb-2">
                                            {featuredGame.clock}
                                        </div>
                                        <div className="text-pro-muted text-xs font-medium font-semibold tracking-wide uppercase">
                                            {featuredGame.status === 'UPCOMING' ? 'STARTING SOON' : `Q${featuredGame.period}`}
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-center px-4 mb-8">
                                        <div className="text-center">
                                            <div className="text-4xl font-bold font-mono tabular-nums text-emerald-500 mb-1">{featuredGame.status === 'UPCOMING' ? '-' : featuredGame.home_score}</div>
                                            <div className="text-lg font-medium font-bold tracking-normal uppercase text-pro-muted">{featuredGame.home_team}</div>
                                        </div>
                                        <div className="text-2xl font-mono text-pro-muted">VS</div>
                                        <div className="text-center">
                                            <div className="text-4xl font-bold font-mono tabular-nums text-emerald-500 mb-1">{featuredGame.status === 'UPCOMING' ? '-' : featuredGame.away_score}</div>
                                            <div className="text-lg font-medium font-bold tracking-normal uppercase text-pro-muted">{featuredGame.away_team}</div>
                                        </div>
                                    </div>

                                    <div className="border border-pro-border bg-white/[0.02] p-4 text-center">
                                        <div className="text-xs text-pro-muted font-medium tracking-wide font-semibold uppercase mb-1">{featuredGame.status === 'UPCOMING' ? 'Status' : 'Differential'}</div>
                                        <div className={`text-2xl font-bold font-mono tabular-nums tracking-wide ${featuredGame.status !== 'UPCOMING' && Math.abs(featuredGame.home_score - featuredGame.away_score) <= 5
                                            ? 'text-amber-500 animate-[data-flicker_3s_ease-in-out_infinite]'
                                            : 'text-pro-text'
                                            }`}>
                                            {featuredGame.status === 'UPCOMING' ? 'UPCOMING' : `${Math.abs(featuredGame.home_score - featuredGame.away_score)}`}
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-8 text-pro-muted flex flex-col items-center justify-center gap-4 relative z-10">
                                    <div className="relative w-12 h-12 flex items-center justify-center">
                                        
                                        <span className="font-mono text-xs tracking-[0.3em]">NULL</span>
                                    </div>
                                    <div className="font-medium font-semibold text-xs tracking-wide uppercase">No live games right now</div>
                                </div>
                            )}
                        </div>

                        {/* Connection Status Card */}
                        <div className="relative bg-pro-surface p-4 opacity-75 transition-opacity" >
                            
                            <div className="text-xs text-pro-muted font-medium font-semibold tracking-wide uppercase border-b border-pro-border pb-2 mb-3">
                                Connection Status
                            </div>
                            <div className="text-sm space-y-1">
                                <div className="flex justify-between font-mono tracking-wide uppercase text-xs">
                                    <span className="text-pro-muted">Stream:</span>
                                    <span className={isConnected ? 'text-emerald-500' : 'text-red-500'}>
                                        {isConnected ? 'Connected' : 'Disconnected'}
                                    </span>
                                </div>
                                <div className="flex justify-between font-mono tracking-wide uppercase text-xs">
                                    <span className="text-pro-muted">Games Cached:</span>
                                    <span className="text-pro-text tabular-nums">{games.length}</span>
                                </div>
                                <div className="flex justify-between font-mono tracking-wide uppercase text-xs">
                                    <span className="text-pro-muted">Leaders Tracked:</span>
                                    <span className="text-pro-text tabular-nums">{leaders.length}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* RIGHT COLUMN: Live Alpha Leaderboard */}
                    <div className="lg:col-span-8">
                        <div className="relative bg-pro-surface h-full flex flex-col" >
                            
                            <div className="p-6 border-b border-pro-border flex justify-between items-center relative z-10">
                                <div className="flex items-center gap-3">
                                    <h2 className="text-xl font-medium font-bold tracking-normal uppercase text-pro-text">Live Alpha Leaderboard</h2>
                                </div>
                                <div className="text-xs text-pro-muted bg-white/[0.02] px-3 py-1 font-medium tracking-wide font-semibold uppercase border border-pro-border">
                                    SORTED BY: <span className="text-amber-500 ml-1 animate-[data-flicker_3s_ease-in-out_infinite]">IN-GAME PIE</span>
                                </div>
                            </div>

                            <div className="p-0 overflow-x-auto scrollbar-premium w-full relative z-10">
                                <table className="w-full text-left border-collapse min-w-full">
                                    <thead>
                                        <tr className="border-b border-pro-border/50 text-pro-muted text-xs font-medium font-semibold tracking-wide uppercase">
                                            <th className="p-2 sm:p-4">Rank</th>
                                            <th className="p-2 sm:p-4 sticky left-0 z-10 bg-pro-surface shadow-[4px_0_12px_rgba(0,0,0,0.5)]">Player</th>
                                            <th className="p-2 sm:p-4 hidden sm:table-cell">Team</th>
                                            <th className="p-2 sm:p-4 text-right">PTS</th>
                                            <th className="p-2 sm:p-4 text-right hidden md:table-cell">REB</th>
                                            <th className="p-2 sm:p-4 text-right hidden md:table-cell">AST</th>
                                            <th className="p-2 sm:p-4 text-right text-amber-500">PIE %</th>
                                        </tr>
                                    </thead>
                                    <tbody className="text-sm">
                                        {leaders.map((leader, idx) => (
                                            <PlayerRow
                                                key={leader.player_id}
                                                player={leader}
                                                rank={idx + 1}
                                                changedPlayerIds={changedPlayerIds}
                                            />
                                        ))}
                                        {leaders.length === 0 && (
                                            <tr>
                                                <td colSpan={7} className="p-8 text-center text-pro-muted font-medium font-semibold tracking-wide uppercase text-xs">
                                                    {isConnected
                                                        ? 'Waiting for live game data...'
                                                        : 'Feed not connected'}
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
        </div>
    );
};

export default PulsePage;
