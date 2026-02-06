import React from 'react'
import { Swords, Radar, Users, User, Zap } from 'lucide-react'
import { useOrbital } from '../context/OrbitalContext'
import MatchupRadar from '../components/matchup/MatchupRadar'
import VertexMatchupCard from '../components/aegis/VertexMatchupCard'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'

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
                let data;
                if (window.electronAPI?.getTeams) {
                    data = await window.electronAPI.getTeams();
                } else {
                    const res = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/teams');
                    data = await res.json();
                }
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
                // Determine API source
                let data;
                if (window.electronAPI?.analyzeMatchup) {
                    data = await window.electronAPI.analyzeMatchup(selectedPlayer.id, opponentId);
                } else {
                    const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/matchup/analyze?player_id=${selectedPlayer.id}&opponent=${opponentId}`);
                    data = await res.json();
                }
                setAnalysis(data);

                // Fetch REAL radar dimensions from the API (not hardcoded!)
                try {
                    const radarRes = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/radar/${selectedPlayer.id}?opponent_id=${opponentId}`);
                    const radarResult = await radarRes.json();
                    if (radarResult.player_stats && radarResult.opponent_defense) {
                        setRadarData({
                            player: radarResult.player_stats,
                            opponent: radarResult.opponent_defense,
                            formulas: radarResult.formulas_used || []
                        });
                        console.log('[RADAR] Loaded real dimensions for opponent:', opponentId, radarResult);
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
        <div className="p-8 h-full overflow-y-auto">
            <header className="mb-8 flex-shrink-0">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-100 flex items-center gap-3">
                            <Swords className="w-8 h-8 text-orange-500" />
                            Matchup Engine
                            <span className="text-xs bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded-full uppercase tracking-wider">Vertex</span>
                        </h1>
                        <p className="text-slate-400 mt-2">
                            {selectedPlayer
                                ? `Analyzing: ${selectedPlayer.name} ${matchupMode === 'team' ? `vs ${opponentAbbr}` : 'H2H'}`
                                : "Head-to-Head Analysis • Radar Comparables"
                            }
                        </p>
                    </div>
                    {/* Mode Toggle */}
                    <div className="flex items-center gap-2 bg-slate-800 p-1 rounded-lg">
                        <button
                            onClick={() => setMatchupMode('team')}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${matchupMode === 'team'
                                ? 'bg-orange-500/20 text-orange-400'
                                : 'text-slate-400 hover:text-white'
                                }`}
                        >
                            <Users className="w-4 h-4" /> Team
                        </button>
                        <button
                            onClick={() => setMatchupMode('player')}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${matchupMode === 'player'
                                ? 'bg-orange-500/20 text-orange-400'
                                : 'text-slate-400 hover:text-white'
                                }`}
                        >
                            <User className="w-4 h-4" /> Player
                        </button>
                    </div>
                </div>
            </header>

            {selectedPlayer ? (
                <div className="space-y-6 animate-in fade-in duration-500 border border-slate-700/50 rounded-xl p-8 bg-slate-900/30">
                    {matchupMode === 'team' ? (
                        /* Team vs Player Mode */
                        <>
                            <div className="flex justify-between items-center mb-6">
                                <div className="flex items-center gap-4">
                                    <img src={getPlayerAvatarUrl(selectedPlayer?.id)} className="w-16 h-16 rounded-full border-2 border-financial-accent object-cover" />
                                    <div>
                                        <h2 className="text-2xl font-bold text-white">{selectedPlayer?.name || 'Unknown Player'}</h2>
                                        <div className="flex items-center gap-2 mt-1">
                                            <span className="text-slate-400 text-sm">VS</span>
                                            <select
                                                value={opponentId}
                                                onChange={(e) => {
                                                    const team = teams.find(t => t.id === e.target.value);
                                                    setOpponentId(e.target.value);
                                                    setOpponentAbbr(team?.abbreviation || 'OPP');
                                                }}
                                                className="bg-slate-800 border border-slate-700 rounded text-sm text-financial-accent px-2 py-1 outline-none focus:border-financial-accent max-h-48 overflow-y-auto"
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
                                <div className="text-right">
                                    <div className="text-xs text-slate-500 uppercase">System Logic</div>
                                    <div className="text-orange-400 font-bold">
                                        {loading ? "Computing..." : "Live Analysis Active"}
                                    </div>
                                </div>
                            </div>

                            <div className="h-[400px] flex items-center justify-center">
                                {loading ? (
                                    <div className="text-financial-accent animate-pulse">Running Simulation...</div>
                                ) : analysis ? (
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
                                ) : (
                                    <div className="text-red-400">Analysis Data Unavailable</div>
                                )}
                            </div>
                        </>
                    ) : (
                        /* Player vs Player Mode - H2H */
                        <div className="space-y-6">
                            <div className="flex items-center justify-between">
                                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                                    <Zap className="w-5 h-5 text-orange-400" />
                                    Head-to-Head Comparison
                                </h3>
                                <div className="text-xs text-slate-500">
                                    Powered by Vertex Engine
                                </div>
                            </div>

                            {/* Opponent Player Search */}
                            <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
                                <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block">
                                    Select Opponent Player
                                </label>
                                <input
                                    type="text"
                                    value={opponentSearch}
                                    onChange={(e) => {
                                        setOpponentSearch(e.target.value);
                                        // Search for players - use correct endpoint
                                        if (e.target.value.length > 2) {
                                            fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/players/search?q=${encodeURIComponent(e.target.value)}`)
                                                .then(res => res.json())
                                                .then(data => setSearchResults(Array.isArray(data) ? data : []))
                                                .catch(() => setSearchResults([]));
                                        } else {
                                            setSearchResults([]);
                                        }
                                    }}
                                    placeholder="Search for a player..."
                                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white placeholder-slate-500 outline-none focus:border-orange-500 transition-colors"
                                />
                                {searchResults.length > 0 && (
                                    <div className="mt-2 max-h-48 overflow-y-auto bg-slate-900 rounded border border-slate-700">
                                        {searchResults.slice(0, 5).map((player: any) => (
                                            <button
                                                key={player.id}
                                                onClick={() => {
                                                    setOpponentPlayerId(player.id);
                                                    setOpponentSearch(player.name);
                                                    setSearchResults([]);
                                                }}
                                                className="w-full px-3 py-2 text-left hover:bg-slate-800 text-slate-300 text-sm transition-colors"
                                            >
                                                {player?.name || 'Unknown'} <span className="text-slate-500">• {player?.team || 'N/A'}</span>
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
                                <div className="h-48 flex items-center justify-center border border-dashed border-slate-700 rounded-xl bg-slate-900/30">
                                    <p className="text-slate-500 text-sm">Search and select an opponent player to begin H2H analysis</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center h-[60vh] text-slate-500 bg-slate-800/30 rounded-xl border border-dashed border-slate-700">
                    <Radar className="w-16 h-16 mb-4 opacity-20 text-orange-500 animate-pulse" />
                    <h2 className="text-xl font-medium text-slate-400 mb-2">Awaiting Contenders</h2>
                    <p className="text-sm">Select a player from the Command Center or Team Central to initialize analysis.</p>
                </div>
            )}
        </div>
    )
}
