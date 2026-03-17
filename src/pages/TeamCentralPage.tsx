import { Users, Shield, AlertTriangle, RefreshCw } from 'lucide-react'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'
import { ApiContract } from '../api/client'

interface Injury {
    player_name: string;
    playerName?: string;
    team: string;
    teamTricode?: string;
    status: string;
    injury_type: string;
    injuryType?: string;
}

export default function TeamCentralPage() {
    const [injuries, setInjuries] = useState<Injury[]>([]);
    const [loading, setLoading] = useState(true);
    const [teams, setTeams] = useState<any[]>([]);
    const [selectedTeam, setSelectedTeam] = useState<string>("");
    const [roster, setRoster] = useState<any[]>([]);
    const [loadingRoster, setLoadingRoster] = useState(false);
    const navigate = useNavigate();

    const REFRESH_MS = 5 * 60 * 1000;
    const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [injuryRefreshing, setInjuryRefreshing] = useState(false);
    const [injuryLastUpdated, setInjuryLastUpdated] = useState<string>('');

    const fetchInjuries = useCallback(async (showSpinner = false) => {
        if (showSpinner) setInjuryRefreshing(true);
        try {
            // Use the live ESPN injury route (same source as InjuryPanel)
            const res = await ApiContract.executeWeb<any>({ path: 'v1/games/injuries/today' });
            const flat: Injury[] = (res?.injuries ?? []).map((inj: any) => ({
                player_name: inj.playerName ?? inj.player_name ?? '',
                team: inj.teamTricode ?? inj.team ?? '',
                status: inj.status ?? '',
                injury_type: inj.injuryType ?? inj.injury_type ?? '',
            }));
            setInjuries(flat);
            setInjuryLastUpdated(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        } catch (err) {
            console.error('Failed to load injuries:', err);
        } finally {
            if (showSpinner) setInjuryRefreshing(false);
        }
    }, []);

    useEffect(() => {
        const loadInitialData = async () => {
            try {
                // Load Teams
                const resTeams = await ApiContract.execute<any>('getTeams', { path: 'teams' });
                const teamData = resTeams.data;
                if (teamData?.teams) setTeams(teamData.teams);
            } catch (error) {
                console.error('Failed to load team data:', error);
            } finally {
                setLoading(false);
            }
        };
        loadInitialData();

        // Injuries: initial load
        fetchInjuries();

        // Injuries: auto-refresh every 5 min
        refreshTimerRef.current = setInterval(() => fetchInjuries(), REFRESH_MS);
        return () => {
            if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
        };
    }, [fetchInjuries]);

    useEffect(() => {
        if (!selectedTeam) return;



        const loadRoster = async (retryCount = 0) => {
            if (retryCount === 0) setLoadingRoster(true);
            try {
                const res = await ApiContract.execute<any>('getRoster', { path: `roster/${selectedTeam}` }, [selectedTeam]);
                const data = res.data;


                if (data?.roster && data.roster.length > 0) {
                    setRoster(data.roster);
                    setLoadingRoster(false);
                } else if (data?.players && data.players.length > 0) {
                    // Fallback for old API format
                    setRoster(data.players);
                    setLoadingRoster(false);
                } else if (retryCount < 3) {
                    // Retry if no data and we haven't exceeded retry limit
                    const delay = Math.pow(2, retryCount) * 500; // 500ms, 1s, 2s
                    setTimeout(() => loadRoster(retryCount + 1), delay);
                    // Keep loading state true
                } else {
                    console.warn(`[TeamCentral] No roster data after 3 retries for ${selectedTeam}`);
                    setRoster([]);
                    setLoadingRoster(false);
                }
            } catch (error) {
                console.error("Failed to load roster:", error);
                if (retryCount < 3) {
                    const delay = Math.pow(2, retryCount) * 500;
                    setTimeout(() => loadRoster(retryCount + 1), delay);
                    // Keep loading state true
                } else {
                    setRoster([]);
                    setLoadingRoster(false);
                }
            }
        };
        loadRoster();
    }, [selectedTeam]);

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col items-center bg-pro-bg font-sans relative z-10 w-full overflow-y-auto">
            
            <div className="w-full max-w-7xl flex flex-col h-full min-h-0 relative z-10">
                <header className="mb-6 sm:mb-8 flex-shrink-0">
                    <h1 className="text-2xl sm:text-3xl font-medium font-bold tracking-normal uppercase text-pro-text flex items-center gap-3">
                        <Users className="w-6 h-6 sm:w-8 sm:h-8 text-blue-500" />
                        Team Central
                    </h1>
                    <p className="text-xs text-pro-muted tracking-wide font-mono mt-2 uppercase">Rosters • Depth Charts • Defense Metrics</p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in-up flex-1 min-h-0">
                    {/* Roster & Depth Chart */}
                    <div className="bg-pro-surface border border-pro-border rounded-xl p-4 sm:p-6 min-h-[400px] lg:h-full lg:min-h-[500px] flex flex-col relative transition-colors duration-300 shadow-sm z-10" >
                        
                        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-4 relative z-10">
                            <h3 className="text-lg font-medium font-bold tracking-normal uppercase text-pro-text flex items-center gap-2">
                                <Users className="w-5 h-5 text-blue-500" />
                                Active Roster
                            </h3>
                            <select
                                className="bg-pro-bg border border-pro-border rounded-xl px-3 py-2 sm:py-1 text-xs font-mono tracking-wide text-pro-text outline-none focus:border-blue-500 transition-all w-full sm:w-auto uppercase"
                                value={selectedTeam}
                                onChange={(e) => setSelectedTeam(e.target.value)}
                            >
                                <option value="">SELECT TEAM...</option>
                                {teams.map(t => (
                                    <option key={t.id} value={t.id}>{t.full_name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="flex-1 overflow-y-auto pr-2 scrollbar-premium bg-white/[0.02] border border-pro-border rounded-xl min-h-0 relative z-10">
                            {loadingRoster ? (
                                <div className="space-y-3 p-4">
                                    {[1, 2, 3, 4, 5, 6].map(i => (
                                        <div key={i} className="h-10 bg-blue-500/10 border border-blue-500/20 rounded-xl animate-pulse" />
                                    ))}
                                </div>
                            ) : selectedTeam ? (
                                <table className="w-full text-sm text-left border-collapse">
                                    <thead className="text-xs text-pro-muted font-medium font-semibold tracking-wide uppercase bg-pro-surface sticky top-0 z-10 shadow-[0_4px_12px_rgba(0,0,0,0.5)]">
                                        <tr>
                                            <th className="px-2 sm:px-4 py-3 border-b border-pro-border/50">Pos</th>
                                            <th className="px-2 sm:px-4 py-3 border-b border-pro-border/50">Player</th>
                                            <th className="px-2 sm:px-4 py-3 hidden sm:table-cell border-b border-pro-border/50">Num</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {roster.map((player) => (
                                            <tr
                                                key={player.player_id || player.id}
                                                className="border-b border-pro-border/50 hover:bg-white/[0.05] cursor-pointer transition-colors"
                                                onClick={() => navigate(`/player/${player.player_id || player.id}`)}
                                            >
                                                <td className="px-2 sm:px-4 py-3 font-mono text-xs tracking-wide text-blue-500">{player.position}</td>
                                                <td className="px-2 sm:px-4 py-3 font-medium font-semibold uppercase tracking-wide text-pro-text text-xs flex items-center gap-3">
                                                    <img src={getPlayerAvatarUrl(player.id)} className="w-8 h-8 rounded-xl border border-pro-border object-cover object-top" alt="" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                                                    <span className="truncate">{player.name}</span>
                                                </td>
                                                <td className="px-2 sm:px-4 py-3 text-pro-muted font-mono text-xs hidden sm:table-cell">{player.jersey_number || player.number || "#"}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-pro-muted font-medium tracking-wide uppercase">
                                    <Users className="w-12 h-12 mb-4 opacity-50 text-blue-500" />
                                    <p className="text-xs">Select a team to view roster</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Defensive Bleed and Injuries */}
                    <div className="space-y-6">
                        <div className="bg-pro-surface border border-pro-border rounded-xl p-6 relative transition-colors duration-300 shadow-sm z-10" >
                            
                            <h3 className="text-lg font-medium font-bold tracking-normal uppercase text-pro-text mb-4 flex items-center gap-2 relative z-10">
                                <Shield className="w-5 h-5 text-red-500" />
                                Defensive Bleed
                            </h3>
                            <div className="h-40 bg-white/[0.02] rounded-xl border border-dashed border-pro-border/50 flex items-center justify-center text-xs font-mono tracking-wide uppercase text-pro-muted relative z-10">
                                [HEATMAP PLACEHOLDER: POINTS ALLOWED BY POSITION]
                            </div>
                        </div>

                        <div className="bg-pro-surface border border-pro-border rounded-xl p-6 flex flex-col max-h-[250px] relative transition-colors duration-300 shadow-sm z-10" >
                            
                            <h3 className="text-lg font-medium font-bold tracking-normal uppercase text-pro-text mb-4 flex items-center gap-2 flex-shrink-0 relative z-10">
                                <AlertTriangle className="w-5 h-5 text-amber-500" />
                                Injury Report
                                <button
                                    onClick={() => fetchInjuries(true)}
                                    disabled={injuryRefreshing}
                                    title="Refresh injuries"
                                    className="ml-1 p-0.5 rounded hover:bg-white/10 transition-colors disabled:opacity-40"
                                >
                                    <RefreshCw className={`w-3 h-3 text-slate-400 ${injuryRefreshing ? 'animate-spin' : ''}`} />
                                </button>
                                {injuryLastUpdated && (
                                    <span className="text-[10px] text-slate-600 font-normal normal-case tracking-normal ml-auto">
                                        {injuryLastUpdated}
                                    </span>
                                )}
                            </h3>
                            <div className="space-y-2 overflow-y-auto pr-2 scrollbar-premium flex-1 min-h-0 relative z-10">
                                {loading ? (
                                    <div className="space-y-2">
                                        {[1, 2, 3].map(i => <div key={i} className="h-8 bg-amber-500/10 border border-amber-500/20 rounded-xl animate-pulse" />)}
                                    </div>
                                ) : injuries.length > 0 ? (
                                    <div className="space-y-2">
                                        {injuries.map((injury, idx) => (
                                            <div key={idx} className="flex justify-between items-center text-xs p-2 bg-red-500/10 border-l-2 border-red-500 transition-colors hover:bg-red-500/20">
                                                <span className="text-pro-text font-medium font-semibold uppercase">{injury.player_name} <span className="text-pro-muted ml-1 font-mono text-xs tracking-wide">[{injury.team}]</span></span>
                                                <span className="text-red-500 font-mono text-xs tracking-wide uppercase">{injury.status} // {injury.injury_type}</span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-xs font-mono tracking-wide text-pro-muted text-center py-4 uppercase border border-dashed border-pro-border/50 mt-2 bg-white/[0.02]">
                                        NO INJURIES REPORTED
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
