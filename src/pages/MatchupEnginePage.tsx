import React from 'react'
import { Swords, Radar, Users, User, Zap } from 'lucide-react'
import { useOrbital } from '../context/OrbitalContext'
import MatchupRadar from '../components/matchup/MatchupRadar'
import VertexMatchupCard from '../components/aegis/VertexMatchupCard'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'
import { ApiContract } from '../api/client'
import { PlayerApi } from '../services/playerApi'

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
        <div className="p-8 h-full overflow-y-auto bg-pro-bg relative z-10 w-full text-pro-text font-sans">
            
            <header className="mb-8 flex-shrink-0 relative z-10">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-medium font-bold tracking-normal uppercase text-pro-text flex items-center gap-3">
                            <Swords className="w-8 h-8 text-amber-500" />
                            Matchup Engine
                            <span className="text-xs bg-amber-500/10 text-amber-500 border border-amber-500 px-2 py-0.5 rounded-xl font-medium font-semibold uppercase tracking-wide shadow-[0_0_8px_rgba(245,158,11,0.2)]">Vertex</span>
                        </h1>
                        <p className="text-xs text-pro-muted font-mono tracking-wide mt-2 uppercase">
                            {selectedPlayer
                                ? `Analyzing: ${selectedPlayer.name} ${matchupMode === 'team' ? `vs ${opponentAbbr}` : 'H2H'}`
                                : "Head-to-Head Analysis • Radar Comparables"
                            }
                        </p>
                    </div>
                    {/* Mode Toggle */}
                    <div className="flex items-center gap-4 border-b border-pro-border pb-1">
                        <button
                            onClick={() => setMatchupMode('team')}
                            className={`flex items-center gap-2 py-2 px-1 text-xs font-medium font-semibold tracking-normal uppercase transition-all duration-100 border-b-2 ${matchupMode === 'team'
                                ? 'border-amber-500 text-amber-500 shadow-[0_4px_12px_rgba(245,158,11,0.2)]'
                                : 'border-transparent text-pro-muted hover:text-pro-text'
                                }`}
                        >
                            <Users className="w-4 h-4" /> Team
                        </button>
                        <button
                            onClick={() => setMatchupMode('player')}
                            className={`flex items-center gap-2 py-2 px-1 text-xs font-medium font-semibold tracking-normal uppercase transition-all duration-100 border-b-2 ${matchupMode === 'player'
                                ? 'border-amber-500 text-amber-500 shadow-[0_4px_12px_rgba(245,158,11,0.2)]'
                                : 'border-transparent text-pro-muted hover:text-pro-text'
                                }`}
                        >
                            <User className="w-4 h-4" /> Player
                        </button>
                    </div>
                </div>
            </header>

            {selectedPlayer ? (
                <div className="flex-1 min-h-0 overflow-y-auto space-y-6 animate-in fade-in duration-500 relative bg-pro-surface border border-pro-border p-4 sm:p-8 z-10" >
                    
                    {matchupMode === 'team' ? (
                        /* Team vs Player Mode */
                        <div className="flex flex-col h-full">
                            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
                                <div className="flex items-center gap-4 w-full sm:w-auto relative z-10">
                                    <img src={getPlayerAvatarUrl(selectedPlayer?.id)} className="w-12 h-12 sm:w-16 sm:h-16 rounded-xl border border-pro-border object-cover flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <h2 className="text-xl sm:text-2xl font-medium font-bold tracking-normal uppercase text-pro-text truncate">{selectedPlayer?.name || 'Unknown Player'}</h2>
                                        <div className="flex items-center gap-2 mt-1">
                                            <span className="text-pro-muted font-medium font-semibold tracking-wide text-xs sm:text-xs uppercase flex-shrink-0">VS</span>
                                            <select
                                                value={opponentId}
                                                onChange={(e) => {
                                                    const team = teams.find(t => t.id === e.target.value);
                                                    setOpponentId(e.target.value);
                                                    setOpponentAbbr(team?.abbreviation || 'OPP');
                                                }}
                                                className="bg-pro-bg border border-pro-border rounded-xl text-xs sm:text-sm text-pro-text font-medium tracking-wide uppercase px-2 py-1 outline-none focus:border-blue-500 w-full sm:w-auto overflow-hidden text-ellipsis whitespace-nowrap transition-colors"
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
                                <div className="text-left sm:text-right w-full sm:w-auto bg-white/[0.02] border border-pro-border p-3 sm:px-4 sm:py-2 rounded-xl relative z-10">
                                    <div className="text-xs sm:text-xs text-pro-muted font-medium tracking-wide font-semibold uppercase mb-1">System Logic</div>
                                    <div className="text-amber-500 font-mono tracking-wide text-sm sm:text-sm animate-[data-flicker_3s_ease-in-out_infinite]">
                                        {loading ? "COMPUTING..." : "LIVE ANALYSIS ACTIVE"}
                                    </div>
                                </div>
                            </div>

                            <div className="flex-1 min-h-0 flex items-center justify-center -mx-4 sm:mx-0 relative z-10">
                                {loading ? (
                                    <div className="text-amber-500 text-xs font-mono tracking-wide font-bold uppercase animate-pulse p-8">Running Simulation...</div>
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
                            <div className="flex items-center justify-between border-b border-pro-border/50 pb-4">
                                <h3 className="text-lg font-medium font-bold tracking-normal uppercase text-pro-text flex items-center gap-2">
                                    <Zap className="w-5 h-5 text-amber-500" />
                                    Head-to-Head Comparison
                                </h3>
                                <div className="text-xs font-mono tracking-wide text-pro-muted uppercase">
                                    Powered by Vertex Engine
                                </div>
                            </div>

                            {/* Opponent Player Search */}
                            <div className="bg-white/[0.02] rounded-xl p-4 border border-pro-border relative z-20">
                                <label className="text-xs font-medium font-semibold tracking-wide text-pro-muted uppercase mb-2 block">
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
                                    className="w-full bg-pro-bg border border-pro-border rounded-xl px-3 py-2 text-pro-text placeholder-pro-muted/50 font-medium tracking-wide uppercase outline-none focus:border-amber-500 transition-colors"
                                />
                                {searchResults.length > 0 && (
                                    <div className="mt-2 max-h-48 overflow-y-auto bg-pro-bg rounded-xl border border-pro-border shadow-[0_4px_12px_rgba(0,0,0,0.5)] absolute w-[calc(100%-2rem)] left-4 z-50">
                                        {searchResults.slice(0, 5).map((player: any) => (
                                            <button
                                                key={player.id}
                                                onClick={() => {
                                                    setOpponentPlayerId(player.id);
                                                    setOpponentSearch(player.name);
                                                    setSearchResults([]);
                                                }}
                                                className="w-full px-3 py-2 text-left hover:bg-white/[0.05] text-pro-text text-xs font-medium tracking-wide uppercase transition-colors"
                                            >
                                                {player?.name || 'Unknown'} <span className="text-pro-muted ml-2">[{player?.team || 'N/A'}]</span>
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
                                <div className="h-48 flex items-center justify-center border border-dashed border-pro-border/50 rounded-xl bg-white/[0.01]">
                                    <p className="text-pro-muted text-xs font-medium tracking-wide uppercase">Search and select an opponent player to begin H2H analysis</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center h-[60vh] text-pro-muted bg-pro-surface rounded-xl border border-pro-border relative" >
                    
                    <Radar className="w-16 h-16 mb-4 opacity-50 text-amber-500 animate-pulse" />
                    <h2 className="text-xl font-medium font-bold tracking-wide uppercase block text-pro-text mb-2 animate-[data-flicker_3s_ease-in-out_infinite]">Awaiting Contenders</h2>
                    <p className="text-xs font-mono tracking-wide uppercase">Select a player from the Command Center or Team Central to initialize analysis.</p>
                </div>
            )}
        </div>
    )
}
