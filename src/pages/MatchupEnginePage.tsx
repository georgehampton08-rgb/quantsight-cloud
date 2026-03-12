import React from 'react'
import { Swords, Radar, Users, User, Zap } from 'lucide-react'
import { useOrbital } from '../context/OrbitalContext'
import MatchupRadar from '../components/matchup/MatchupRadar'
import VertexMatchupCard from '../components/aegis/VertexMatchupCard'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'
import { ApiContract } from '../api/client'
import { PlayerApi } from '../services/playerApi'
import CornerBrackets from '../components/common/CornerBrackets'

interface RadarDimensions {
    scoring: number;
    playmaking: number;
    rebounding: number;
    defense: number;
    pace: number;
}

export default function MatchupEnginePage() {
    const { selectedPlayer } = useOrbital();
    const [analysis, setAnalysis] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(false);
    const [opponentId, setOpponentId] = React.useState<string>("");
    const [opponentAbbr, setOpponentAbbr] = React.useState("GSW");
    const [teams, setTeams] = React.useState<{ id: string, abbreviation: string, full_name: string }[]>([]);
    const [matchupMode, setMatchupMode] = React.useState<'team' | 'player'>('team');
    const [opponentPlayerId, setOpponentPlayerId] = React.useState<string | null>(null);
    const [opponentSearch, setOpponentSearch] = React.useState('');
    const [searchResults, setSearchResults] = React.useState<any[]>([]);

    // Radar dimensions from API (real math!)
    const [radarData, setRadarData] = React.useState<{
        player: RadarDimensions | null;
        opponent: RadarDimensions | null;
        formulas: string[];
    }>({ player: null, opponent: null, formulas: [] });

    // Fetch all teams on mount
    React.useEffect(() => {
        const loadTeams = async () => {
            try {
                const res = await ApiContract.execute<any>('getTeams', { path: 'teams' });
                const data = res.data;
                if (data?.teams) {
                    setTeams(data.teams);
                }
            } catch (error) {
                console.error("Failed to load teams:", error);
            }
        };
        loadTeams();
    }, []);

    React.useEffect(() => {
        if (!selectedPlayer?.id || !opponentId) return;

        const loadAnalysis = async () => {
            setLoading(true);
            try {
                const data = await PlayerApi.analyzeMatchup(selectedPlayer.id, opponentId);
                setAnalysis(data);

                // Fetch REAL radar dimensions from the API
                try {
                    const base = import.meta.env.VITE_API_URL || '';
                    const radarRes = await fetch(`${base}/radar/${selectedPlayer.id}?opponent_id=${opponentId}`);
                    if (radarRes.ok) {
                        const radarResult = await radarRes.json();
                        if (radarResult.player_stats && radarResult.opponent_defense) {
                            setRadarData({
                                player: radarResult.player_stats,
                                opponent: radarResult.opponent_defense,
                                formulas: radarResult.formulas_used || []
                            });
                        }
                    }
                } catch (radarErr) {
                    console.warn('[RADAR] Failed to load real dimensions, using defaults:', radarErr);
                }
            } catch (error) {
                console.error("Matchup analysis failed:", error);
            } finally {
                setLoading(false);
            }
        };

        loadAnalysis();
    }, [selectedPlayer?.id, opponentId]);

    return (
        <div className="p-8 h-full overflow-y-auto bg-cyber-bg relative z-10 w-full text-cyber-text font-sans">
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                 style={{
                   backgroundImage: 'linear-gradient(#00ff88 1px, transparent 1px), linear-gradient(90deg, #00ff88 1px, transparent 1px)',
                   backgroundSize: '32px 32px',
                 }} />
            <header className="mb-8 flex-shrink-0 relative z-10">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text flex items-center gap-3">
                            <Swords className="w-8 h-8 text-cyber-gold" />
                            Matchup Engine
                            <span className="text-[10px] bg-cyber-gold/10 text-cyber-gold border border-cyber-gold px-2 py-0.5 rounded-none font-display font-600 uppercase tracking-[0.2em] shadow-[0_0_8px_rgba(245,158,11,0.2)]">Vertex</span>
                        </h1>
                        <p className="text-[10px] text-cyber-muted font-mono tracking-[0.2em] mt-2 uppercase">
                            {selectedPlayer
                                ? `Analyzing: ${selectedPlayer.name} ${matchupMode === 'team' ? `vs ${opponentAbbr}` : 'H2H'}`
                                : "Head-to-Head Analysis • Radar Comparables"
                            }
                        </p>
                    </div>
                    {/* Mode Toggle */}
                    <div className="flex items-center gap-4 border-b border-cyber-border pb-1">
                        <button
                            onClick={() => setMatchupMode('team')}
                            className={`flex items-center gap-2 py-2 px-1 text-[10px] font-display font-600 tracking-[0.12em] uppercase transition-all duration-100 border-b-2 ${matchupMode === 'team'
                                ? 'border-cyber-gold text-cyber-gold shadow-[0_4px_12px_rgba(245,158,11,0.2)]'
                                : 'border-transparent text-cyber-muted hover:text-cyber-text'
                                }`}
                        >
                            <Users className="w-4 h-4" /> Team
                        </button>
                        <button
                            onClick={() => setMatchupMode('player')}
                            className={`flex items-center gap-2 py-2 px-1 text-[10px] font-display font-600 tracking-[0.12em] uppercase transition-all duration-100 border-b-2 ${matchupMode === 'player'
                                ? 'border-cyber-gold text-cyber-gold shadow-[0_4px_12px_rgba(245,158,11,0.2)]'
                                : 'border-transparent text-cyber-muted hover:text-cyber-text'
                                }`}
                        >
                            <User className="w-4 h-4" /> Player
                        </button>
                    </div>
                </div>
            </header>

            {selectedPlayer ? (
                <div className="flex-1 min-h-0 overflow-y-auto space-y-6 animate-in fade-in duration-500 relative bg-cyber-surface border border-cyber-border p-4 sm:p-8 z-10" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    {matchupMode === 'team' ? (
                        /* Team vs Player Mode */
                        <div className="flex flex-col h-full">
                            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
                                <div className="flex items-center gap-4 w-full sm:w-auto relative z-10">
                                    <img src={getPlayerAvatarUrl(selectedPlayer?.id)} className="w-12 h-12 sm:w-16 sm:h-16 rounded-none border border-cyber-border object-cover flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <h2 className="text-xl sm:text-2xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text truncate">{selectedPlayer?.name || 'Unknown Player'}</h2>
                                        <div className="flex items-center gap-2 mt-1">
                                            <span className="text-cyber-muted font-display font-600 tracking-widest text-[10px] sm:text-xs uppercase flex-shrink-0">VS</span>
                                            <select
                                                value={opponentId}
                                                onChange={(e) => {
                                                    const team = teams.find(t => t.id === e.target.value);
                                                    setOpponentId(e.target.value);
                                                    setOpponentAbbr(team?.abbreviation || 'OPP');
                                                }}
                                                className="bg-cyber-bg border border-cyber-border rounded-none text-xs sm:text-sm text-cyber-text font-display tracking-widest uppercase px-2 py-1 outline-none focus:border-cyber-blue w-full sm:w-auto overflow-hidden text-ellipsis whitespace-nowrap transition-colors"
                                            >
                                                <option value="">Select Team...</option>
                                                {teams.length > 0 ? (
                                                    teams.map((team) => (
                                                        <option key={team.id} value={team.id}>
                                                            {team.full_name}
                                                        </option>
                                                    ))
                                                ) : (
                                                    <>
                                                        <option value="1610612744">Warriors</option>
                                                        <option value="1610612738">Celtics</option>
                                                        <option value="1610612747">Lakers</option>
                                                    </>
                                                )}
                                            </select>
                                        </div>
                                    </div>
                                </div>
                                <div className="text-left sm:text-right w-full sm:w-auto bg-white/[0.02] border border-cyber-border p-3 sm:px-4 sm:py-2 rounded-none relative z-10">
                                    <div className="text-[10px] sm:text-[10px] text-cyber-muted font-display tracking-[0.2em] font-600 uppercase mb-1">System Logic</div>
                                    <div className="text-cyber-gold font-mono tracking-widest text-sm sm:text-sm animate-[data-flicker_3s_ease-in-out_infinite]">
                                        {loading ? "COMPUTING..." : "LIVE ANALYSIS ACTIVE"}
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 min-h-0 flex items-center justify-center -mx-4 sm:mx-0 relative z-10">
                                {loading ? (
                                    <div className="text-cyber-gold text-xs font-mono tracking-[0.2em] font-bold uppercase animate-pulse p-8">Running Simulation...</div>
                                ) : analysis ? (
                                    <div className="w-full max-w-full overflow-hidden h-full min-h-[300px] flex items-center justify-center">
                                        <MatchupRadar
                                            playerStats={radarData.player || {
                                                scoring: 50,
                                                playmaking: 50,
                                                rebounding: 50,
                                                defense: 50,
                                                pace: 50
                                            }}
                                            opponentDefense={radarData.opponent || {
                                                scoring: 50,
                                                playmaking: 50,
                                                rebounding: 50,
                                                defense: 50,
                                                pace: 50
                                            }}
                                        />
                                    </div>
                                ) : (
                                    <div className="text-red-400 p-8">Analysis Data Unavailable</div>
                                )}
                            </div>
                        </div>
                    ) : (
                        /* Player vs Player Mode - H2H */
                        <div className="space-y-6 flex flex-col h-full relative z-10">
                            <div className="flex items-center justify-between border-b border-cyber-border/50 pb-4">
                                <h3 className="text-lg font-display font-700 tracking-[0.08em] uppercase text-cyber-text flex items-center gap-2">
                                    <Zap className="w-5 h-5 text-cyber-gold" />
                                    Head-to-Head Comparison
                                </h3>
                                <div className="text-[10px] font-mono tracking-widest text-cyber-muted uppercase">
                                    Powered by Vertex Engine
                                </div>
                            </div>

                            {/* Opponent Player Search */}
                            <div className="bg-white/[0.02] rounded-none p-4 border border-cyber-border relative z-20">
                                <label className="text-[10px] font-display font-600 tracking-[0.2em] text-cyber-muted uppercase mb-2 block">
                                    Select Opponent Player
                                </label>
                                <input
                                    type="text"
                                    value={opponentSearch}
                                    onChange={(e) => {
                                        setOpponentSearch(e.target.value);
                                        // Search for players - use correct endpoint
                                        if (e.target.value.length > 2) {
                                            PlayerApi.search(e.target.value)
                                                .then(data => setSearchResults(Array.isArray(data) ? data : []))
                                                .catch(() => setSearchResults([]));
                                        } else {
                                            setSearchResults([]);
                                        }
                                    }}
                                    placeholder="SEARCH FOR A PLAYER..."
                                    className="w-full bg-cyber-bg border border-cyber-border rounded-none px-3 py-2 text-cyber-text placeholder-cyber-muted/50 font-display tracking-widest uppercase outline-none focus:border-cyber-gold transition-colors"
                                />
                                {searchResults.length > 0 && (
                                    <div className="mt-2 max-h-48 overflow-y-auto bg-cyber-bg rounded-none border border-cyber-border shadow-[0_4px_12px_rgba(0,0,0,0.5)] absolute w-[calc(100%-2rem)] left-4 z-50">
                                        {searchResults.slice(0, 5).map((player: any) => (
                                            <button
                                                key={player.id}
                                                onClick={() => {
                                                    setOpponentPlayerId(player.id);
                                                    setOpponentSearch(player.name);
                                                    setSearchResults([]);
                                                }}
                                                className="w-full px-3 py-2 text-left hover:bg-white/[0.05] text-cyber-text text-xs font-display tracking-widest uppercase transition-colors"
                                            >
                                                {player?.name || 'Unknown'} <span className="text-cyber-muted ml-2">[{player?.team || 'N/A'}]</span>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Player vs Player Card */}
                            {opponentPlayerId && (
                                <VertexMatchupCard
                                    playerAId={selectedPlayer.id}
                                    playerBId={opponentPlayerId}
                                    onClose={() => setOpponentPlayerId(null)}
                                />
                            )}

                            {!opponentPlayerId && (
                                <div className="h-48 flex items-center justify-center border border-dashed border-cyber-border/50 rounded-none bg-white/[0.01]">
                                    <p className="text-cyber-muted text-xs font-display tracking-[0.2em] uppercase">Search and select an opponent player to begin H2H analysis</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center h-[60vh] text-cyber-muted bg-cyber-surface rounded-none border border-cyber-border relative" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <Radar className="w-16 h-16 mb-4 opacity-50 text-cyber-gold animate-pulse" />
                    <h2 className="text-xl font-display font-700 tracking-[0.1em] uppercase block text-cyber-text mb-2 animate-[data-flicker_3s_ease-in-out_infinite]">Awaiting Contenders</h2>
                    <p className="text-xs font-mono tracking-widest uppercase">Select a player from the Command Center or Team Central to initialize analysis.</p>
                </div>
            )}
        </div>
    )
}
