/**
 * The Pulse Page - Live Stats Dashboard
 * ======================================
 * Uses SSE-based useLiveStats hook with gold pulse animation on stat increases.
 */
import React from 'react';
import { useLiveStats, usePlayerPulse, LivePlayerStat, LiveGame } from '../hooks/useLiveStats';
import CornerBrackets from '../components/common/CornerBrackets';

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
            className={`border-b border-cyber-border/50 hover:bg-white/[0.03] transition-colors duration-100 ${rank === 1 ? 'bg-cyber-gold/5' : ''
                } ${isPulsing ? 'animate-gold-pulse' : ''}`}
            style={isPulsing ? {
                boxShadow: '0 0 15px rgba(245, 158, 11, 0.2)', // cyber-gold
                backgroundColor: 'rgba(245, 158, 11, 0.05)'
            } : undefined}
        >
            <td className="p-2 sm:p-4 font-mono text-cyber-muted tracking-widest text-xs sm:text-xs">{String(rank).padStart(2, '0')}</td>
            <td className="p-2 sm:p-4 font-display font-600 tracking-[0.05em] uppercase text-cyber-text flex items-center gap-2 sm:gap-3 text-sm sm:text-base whitespace-nowrap">
                {player.name}
                {isPulsing && <span className="text-cyber-gold text-xs font-mono font-bold tabular-nums ml-2 animate-[data-flicker_3s_ease-in-out_infinite]">+</span>}
            </td>
            <td className="p-2 sm:p-4 text-cyber-muted font-display tracking-widest text-xs sm:text-xs hidden sm:table-cell">{player.team}</td>
            <td className="p-2 sm:p-4 text-right font-mono text-cyber-text text-sm sm:text-base tabular-nums font-bold">{player.stats.pts}</td>
            <td className="p-2 sm:p-4 text-right font-mono text-cyber-muted text-xs sm:text-sm tabular-nums hidden md:table-cell">{player.stats.reb}</td>
            <td className="p-2 sm:p-4 text-right font-mono text-cyber-muted text-xs sm:text-sm tabular-nums hidden md:table-cell">{player.stats.ast}</td>
            <td className="p-2 sm:p-4 text-right font-mono font-bold text-cyber-gold text-sm sm:text-base tabular-nums">
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
            className={`flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-sm border cursor-pointer transition-all duration-100 ${isActive ? 'border-cyber-blue bg-cyber-blue/10 shadow-[0_0_10px_rgba(34,211,238,0.2)]' :
                    isLive ? 'bg-cyber-green/5 border-cyber-green/40 hover:bg-cyber-green/10 text-cyber-green' :
                        'bg-cyber-surface border-cyber-border hover:bg-white/[0.05] text-cyber-muted hover:text-cyber-text'
                }`}
        >
            {isLive && <span className="w-1.5 h-1.5 bg-cyber-green opacity-80 rounded-none animate-pulse" />}
            <span className="font-display font-600 tracking-widest text-[10px] uppercase">{game.away_team}</span>
            <span className="font-mono font-bold text-cyber-text text-sm">
                {game.away_score}-{game.home_score}
            </span>
            <span className="font-display font-600 tracking-widest text-[10px] uppercase">{game.home_team}</span>
            {isLive && game.period > 0 && (
                <span className="text-[10px] text-cyber-green font-mono font-bold ml-1 bg-cyber-green/10 px-1.5 py-0.5 border border-cyber-green">
                    {periodLabel} {game.clock}
                </span>
            )}
            {isFinal && (
                <span className="text-[10px] text-cyber-muted font-mono ml-1">FNL</span>
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
        <div className="h-full flex flex-col p-4 sm:p-8 bg-cyber-bg relative z-10 w-full">
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                 style={{
                   backgroundImage: 'linear-gradient(#00ff88 1px, transparent 1px), linear-gradient(90deg, #00ff88 1px, transparent 1px)',
                   backgroundSize: '32px 32px',
                 }} />

            <header className="mb-6 sm:mb-8 flex-shrink-0 relative z-10">
                <div className="header-content">
                    <div className="header-title flex flex-col sm:flex-row items-center gap-2 sm:gap-4">
                        <div className="flex items-center gap-3">
                            <h1 className="text-3xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text">The Pulse</h1>
                        </div>
                        <span className={`px-2.5 py-1 text-[10px] font-display font-600 tracking-[0.2em] uppercase border whitespace-nowrap ${isConnected
                            ? 'bg-cyber-green/5 text-cyber-green border-cyber-green'
                            : isConnecting
                                ? 'bg-cyber-gold/5 text-cyber-gold border-cyber-gold'
                                : 'bg-cyber-red/5 text-cyber-red border-cyber-red'
                            }`}>
                            <span className={`inline-block w-1.5 h-1.5 rounded-none mr-1.5 ${isConnected ? 'bg-cyber-green' : isConnecting ? 'bg-cyber-gold animate-pulse' : 'bg-cyber-red'
                                }`} />
                            {isConnected ? 'LIVE FEED' : isConnecting ? 'CONNECTING...' : 'DISCONNECTED'}
                        </span>
                    </div>
                    {lastUpdate && (
                        <div className="text-[10px] uppercase font-mono tracking-widest text-cyber-muted mt-2 text-center sm:text-right w-full sm:w-auto">
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
                        <div className="relative bg-cyber-surface p-6 overflow-hidden animate-[stagger-reveal_0.2s_cubic-bezier(0.2,0,0,1)_forwards]" style={{ border: '1px solid #1a2332' }}>
                            <CornerBrackets />
                            <div className="absolute inset-x-0 top-0 h-px bg-cyber-green/20 animate-[scan-line_4s_linear_infinite]" />

                            <div className="flex justify-between items-center mb-6 relative z-10 border-b border-cyber-border/50 pb-3">
                                <span className="text-cyber-muted font-mono tracking-widest text-[10px] uppercase">
                                    {liveCount} LIVE GAME{liveCount !== 1 ? 'S' : ''}
                                </span>
                                <span className="px-3 py-1 bg-cyber-green/10 text-cyber-green text-[10px] font-display font-600 tracking-[0.2em] uppercase border border-cyber-green flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-cyber-green rounded-none shadow-[0_0_8px_rgba(0,255,136,0.8)] animate-[signal-pulse_2s_ease-in-out_infinite]" />
                                    LIVE POLL
                                </span>
                            </div>

                            {featuredGame ? (
                                <div className="relative z-10">
                                    <div className="text-center mb-8">
                                        <div className="text-5xl font-bold font-mono tabular-nums tracking-tighter text-cyber-text mb-2">
                                            {featuredGame.clock}
                                        </div>
                                        <div className="text-cyber-muted text-[10px] font-display font-600 tracking-[0.2em] uppercase">
                                            {featuredGame.status === 'UPCOMING' ? 'STARTING SOON' : `Q${featuredGame.period}`}
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-center px-4 mb-8">
                                        <div className="text-center">
                                            <div className="text-4xl font-bold font-mono tabular-nums text-cyber-green mb-1">{featuredGame.status === 'UPCOMING' ? '-' : featuredGame.home_score}</div>
                                            <div className="text-lg font-display font-700 tracking-[0.08em] uppercase text-cyber-muted">{featuredGame.home_team}</div>
                                        </div>
                                        <div className="text-2xl font-mono text-cyber-muted">VS</div>
                                        <div className="text-center">
                                            <div className="text-4xl font-bold font-mono tabular-nums text-cyber-green mb-1">{featuredGame.status === 'UPCOMING' ? '-' : featuredGame.away_score}</div>
                                            <div className="text-lg font-display font-700 tracking-[0.08em] uppercase text-cyber-muted">{featuredGame.away_team}</div>
                                        </div>
                                    </div>

                                    <div className="border border-cyber-border bg-white/[0.02] p-4 text-center">
                                        <div className="text-[10px] text-cyber-muted font-display tracking-[0.2em] font-600 uppercase mb-1">{featuredGame.status === 'UPCOMING' ? 'Status' : 'Differential'}</div>
                                        <div className={`text-2xl font-bold font-mono tabular-nums tracking-widest ${featuredGame.status !== 'UPCOMING' && Math.abs(featuredGame.home_score - featuredGame.away_score) <= 5
                                            ? 'text-cyber-gold animate-[data-flicker_3s_ease-in-out_infinite]'
                                            : 'text-cyber-text'
                                            }`}>
                                            {featuredGame.status === 'UPCOMING' ? 'UPCOMING' : `${Math.abs(featuredGame.home_score - featuredGame.away_score)}`}
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-8 text-cyber-muted flex flex-col items-center justify-center gap-4 relative z-10">
                                    <div className="relative w-12 h-12 flex items-center justify-center">
                                        <CornerBrackets color="#1a2332" size={14} />
                                        <span className="font-mono text-[10px] tracking-[0.3em]">NULL</span>
                                    </div>
                                    <div className="font-display font-600 text-xs tracking-[0.15em] uppercase">No live games right now</div>
                                </div>
                            )}
                        </div>

                        {/* Connection Status Card */}
                        <div className="relative bg-cyber-surface p-4 opacity-75 transition-opacity" style={{ border: '1px solid #1a2332' }}>
                            <CornerBrackets />
                            <div className="text-[10px] text-cyber-muted font-display font-600 tracking-[0.2em] uppercase border-b border-cyber-border pb-2 mb-3">
                                Connection Status
                            </div>
                            <div className="text-sm space-y-1">
                                <div className="flex justify-between font-mono tracking-widest uppercase text-[10px]">
                                    <span className="text-cyber-muted">Stream:</span>
                                    <span className={isConnected ? 'text-cyber-green' : 'text-cyber-red'}>
                                        {isConnected ? 'Connected' : 'Disconnected'}
                                    </span>
                                </div>
                                <div className="flex justify-between font-mono tracking-widest uppercase text-[10px]">
                                    <span className="text-cyber-muted">Games Cached:</span>
                                    <span className="text-cyber-text tabular-nums">{games.length}</span>
                                </div>
                                <div className="flex justify-between font-mono tracking-widest uppercase text-[10px]">
                                    <span className="text-cyber-muted">Leaders Tracked:</span>
                                    <span className="text-cyber-text tabular-nums">{leaders.length}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* RIGHT COLUMN: Live Alpha Leaderboard */}
                    <div className="lg:col-span-8">
                        <div className="relative bg-cyber-surface h-full flex flex-col" style={{ border: '1px solid #1a2332' }}>
                            <CornerBrackets />
                            <div className="p-6 border-b border-cyber-border flex justify-between items-center relative z-10">
                                <div className="flex items-center gap-3">
                                    <h2 className="text-xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text">Live Alpha Leaderboard</h2>
                                </div>
                                <div className="text-[10px] text-cyber-muted bg-white/[0.02] px-3 py-1 font-display tracking-[0.2em] font-600 uppercase border border-cyber-border">
                                    SORTED BY: <span className="text-cyber-gold ml-1 animate-[data-flicker_3s_ease-in-out_infinite]">IN-GAME PIE</span>
                                </div>
                            </div>

                            <div className="p-0 overflow-x-auto scrollbar-premium w-full relative z-10">
                                <table className="w-full text-left border-collapse min-w-full">
                                    <thead>
                                        <tr className="border-b border-cyber-border/50 text-cyber-muted text-[10px] font-display font-600 tracking-[0.2em] uppercase">
                                            <th className="p-2 sm:p-4">Rank</th>
                                            <th className="p-2 sm:p-4 sticky left-0 z-10 bg-cyber-surface shadow-[4px_0_12px_rgba(0,0,0,0.5)]">Player</th>
                                            <th className="p-2 sm:p-4 hidden sm:table-cell">Team</th>
                                            <th className="p-2 sm:p-4 text-right">PTS</th>
                                            <th className="p-2 sm:p-4 text-right hidden md:table-cell">REB</th>
                                            <th className="p-2 sm:p-4 text-right hidden md:table-cell">AST</th>
                                            <th className="p-2 sm:p-4 text-right text-cyber-gold">PIE %</th>
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
                                                <td colSpan={7} className="p-8 text-center text-cyber-muted font-display font-600 tracking-[0.1em] uppercase text-xs">
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
