import { Users, Shield, AlertTriangle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'

interface Injury {
    player_name: string;
    team: string;
    status: string;
    injury_type: string;
}

import { useNavigate } from 'react-router-dom'

export default function TeamCentralPage() {
    const [injuries, setInjuries] = useState<Injury[]>([]);
    const [loading, setLoading] = useState(true);
    const [teams, setTeams] = useState<any[]>([]);
    const [selectedTeam, setSelectedTeam] = useState<string>("");
    const [roster, setRoster] = useState<any[]>([]);
    const [loadingRoster, setLoadingRoster] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        const loadInitialData = async () => {
            try {
                // Load Injuries
                const injuryData = window.electronAPI?.getInjuries
                    ? await window.electronAPI.getInjuries()
                    : await (await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/injuries')).json();

                if (injuryData?.injuries) setInjuries(injuryData.injuries);

                // Load Teams
                const teamData = window.electronAPI?.getTeams
                    ? await window.electronAPI.getTeams()
                    : await (await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/teams')).json();

                if (teamData?.teams) setTeams(teamData.teams);

            } catch (error) {
                console.error('Failed to load team data:', error);
            } finally {
                setLoading(false);
            }
        };
        loadInitialData();
    }, []);

    useEffect(() => {
        if (!selectedTeam) return;



        const loadRoster = async (retryCount = 0) => {
            if (retryCount === 0) setLoadingRoster(true);
            console.log(`[TeamCentral] Loading roster for team: ${selectedTeam}, attempt ${retryCount + 1}`);
            try {
                const data = window.electronAPI?.getRoster
                    ? await window.electronAPI.getRoster(selectedTeam)
                    : await (await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/roster/${selectedTeam}`)).json();

                console.log(`[TeamCentral] Roster API response:`, data);
                console.log(`[TeamCentral] data.roster exists:`, !!data?.roster);
                console.log(`[TeamCentral] data.roster.length:`, data?.roster?.length);

                if (data?.roster && data.roster.length > 0) {
                    console.log(`[TeamCentral] Setting roster with ${data.roster.length} players`);
                    setRoster(data.roster);
                    setLoadingRoster(false);
                } else if (data?.players && data.players.length > 0) {
                    // Fallback for old API format
                    console.log(`[TeamCentral] Using fallback players field with ${data.players.length} players`);
                    setRoster(data.players);
                    setLoadingRoster(false);
                } else if (retryCount < 3) {
                    // Retry if no data and we haven't exceeded retry limit
                    const delay = Math.pow(2, retryCount) * 500; // 500ms, 1s, 2s
                    console.log(`[TeamCentral] No roster data, retrying in ${delay}ms (attempt ${retryCount + 1}/3)`);
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
                    console.log(`[TeamCentral] Fetch error, retrying in ${delay}ms (attempt ${retryCount + 1}/3)`);
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
        <div className="p-8 h-full">
            <header className="mb-8">
                <h1 className="text-3xl font-bold text-gray-100 flex items-center gap-3">
                    <Users className="w-8 h-8 text-blue-500" />
                    Team Central
                </h1>
                <p className="text-slate-400 mt-2">Rosters • Depth Charts • Defense Metrics</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in-up">
                {/* Roster & Depth Chart */}
                <div className="glass-panel rounded-xl p-6 h-[500px] flex flex-col hover:border-blue-500/30 transition-colors duration-300">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                            <Users className="w-5 h-5 text-blue-400" />
                            Active Roster
                        </h3>
                        <select
                            className="bg-slate-900 border border-slate-700 rounded px-3 py-1 text-sm text-white outline-none focus:border-blue-500 transition-all"
                            value={selectedTeam}
                            onChange={(e) => setSelectedTeam(e.target.value)}
                        >
                            <option value="">Select Team...</option>
                            {teams.map(t => (
                                <option key={t.id} value={t.id}>{t.full_name}</option>
                            ))}
                        </select>
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent bg-slate-900/30 rounded border border-slate-700">
                        {loadingRoster ? (
                            <div className="space-y-3 p-4">
                                {[1, 2, 3, 4, 5, 6].map(i => (
                                    <div key={i} className="h-10 bg-slate-800/50 rounded animate-pulse" />
                                ))}
                            </div>
                        ) : selectedTeam ? (
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs text-slate-500 uppercase bg-slate-900 sticky top-0">
                                    <tr>
                                        <th className="px-4 py-2">Pos</th>
                                        <th className="px-4 py-2">Player</th>
                                        <th className="px-4 py-2">Num</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {roster.map((player) => (
                                        <tr
                                            key={player.player_id || player.id}
                                            className="border-b border-slate-800 hover:bg-slate-800/50 cursor-pointer transition-colors"
                                            onClick={() => navigate(`/player/${player.player_id || player.id}`)}
                                        >
                                            <td className="px-4 py-2 font-mono text-blue-400">{player.position}</td>
                                            <td className="px-4 py-2 font-medium text-white flex items-center gap-2">
                                                <img src={getPlayerAvatarUrl(player.id)} className="w-6 h-6 rounded-full" alt="" />
                                                {player.name}
                                            </td>
                                            <td className="px-4 py-2 text-slate-500">{player.jersey_number || player.number || "#"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-slate-500">
                                <Users className="w-12 h-12 mb-4 opacity-20" />
                                <p>Select a team to view roster</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Defensive Bleed and Injuries */}
                <div className="space-y-6">
                    <div className="glass-panel rounded-xl p-6 hover:border-blue-500/30 transition-colors duration-300">
                        <h3 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                            <Shield className="w-5 h-5 text-red-400" />
                            Defensive Bleed
                        </h3>
                        <div className="h-40 bg-slate-900/50 rounded border border-dashed border-slate-700 flex items-center justify-center text-xs text-slate-600">
                            [Heatmap Placeholder: Points Allowed by Position]
                        </div>
                    </div>

                    <div className="glass-panel rounded-xl p-6 flex flex-col max-h-[250px] hover:border-yellow-500/30 transition-colors duration-300">
                        <h3 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2 flex-shrink-0">
                            <AlertTriangle className="w-5 h-5 text-yellow-500" />
                            Injury Report
                        </h3>
                        <div className="space-y-2 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent flex-1 min-h-0">
                            {loading ? (
                                <div className="space-y-2">
                                    {[1, 2, 3].map(i => <div key={i} className="h-8 bg-slate-800/50 rounded animate-pulse" />)}
                                </div>
                            ) : injuries.length > 0 ? (
                                <div className="space-y-2">
                                    {injuries.map((injury, idx) => (
                                        <div key={idx} className="flex justify-between text-sm p-2 bg-red-500/10 rounded border border-red-500/20">
                                            <span className="text-red-200">{injury.player_name} ({injury.team})</span>
                                            <span className="text-red-400 font-mono">{injury.status} - {injury.injury_type}</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-sm text-slate-500 text-center py-4">
                                    ✅ No injuries reported
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

