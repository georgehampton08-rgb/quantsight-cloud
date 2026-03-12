import { Users, Shield, AlertTriangle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'
import { ApiContract } from '../api/client'
import CornerBrackets from '../components/common/CornerBrackets'

interface Injury {
    player_name: string;
    team: string;
    status: string;
    injury_type: string;
}

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
                const resInjuries = await ApiContract.execute<any>('getInjuries', { path: 'injuries' });
                const injuryData = resInjuries.data;

                if (injuryData?.injuries) setInjuries(injuryData.injuries);

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
    }, []);

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
        <div className="p-4 sm:p-8 h-full flex flex-col items-center bg-cyber-bg font-sans relative z-10 w-full overflow-y-auto">
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                 style={{
                   backgroundImage: 'linear-gradient(#00ff88 1px, transparent 1px), linear-gradient(90deg, #00ff88 1px, transparent 1px)',
                   backgroundSize: '32px 32px',
                 }} />
            <div className="w-full max-w-7xl flex flex-col h-full min-h-0 relative z-10">
                <header className="mb-6 sm:mb-8 flex-shrink-0">
                    <h1 className="text-2xl sm:text-3xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text flex items-center gap-3">
                        <Users className="w-6 h-6 sm:w-8 sm:h-8 text-cyber-blue" />
                        Team Central
                    </h1>
                    <p className="text-[10px] text-cyber-muted tracking-[0.2em] font-mono mt-2 uppercase">Rosters • Depth Charts • Defense Metrics</p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in-up flex-1 min-h-0">
                    {/* Roster & Depth Chart */}
                    <div className="bg-cyber-surface border border-cyber-border rounded-none p-4 sm:p-6 min-h-[400px] lg:h-full lg:min-h-[500px] flex flex-col relative transition-colors duration-300 shadow-none z-10" style={{ border: '1px solid #1a2332' }}>
                        <CornerBrackets />
                        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-4 relative z-10">
                            <h3 className="text-lg font-display font-700 tracking-[0.08em] uppercase text-cyber-text flex items-center gap-2">
                                <Users className="w-5 h-5 text-cyber-blue" />
                                Active Roster
                            </h3>
                            <select
                                className="bg-cyber-bg border border-cyber-border rounded-none px-3 py-2 sm:py-1 text-[10px] font-mono tracking-widest text-cyber-text outline-none focus:border-cyber-blue transition-all w-full sm:w-auto uppercase"
                                value={selectedTeam}
                                onChange={(e) => setSelectedTeam(e.target.value)}
                            >
                                <option value="">SELECT TEAM...</option>
                                {teams.map(t => (
                                    <option key={t.id} value={t.id}>{t.full_name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="flex-1 overflow-y-auto pr-2 scrollbar-premium bg-white/[0.02] border border-cyber-border rounded-none min-h-0 relative z-10">
                            {loadingRoster ? (
                                <div className="space-y-3 p-4">
                                    {[1, 2, 3, 4, 5, 6].map(i => (
                                        <div key={i} className="h-10 bg-cyber-blue/10 border border-cyber-blue/20 rounded-none animate-pulse" />
                                    ))}
                                </div>
                            ) : selectedTeam ? (
                                <table className="w-full text-sm text-left border-collapse">
                                    <thead className="text-[10px] text-cyber-muted font-display font-600 tracking-[0.2em] uppercase bg-cyber-surface sticky top-0 z-10 shadow-[0_4px_12px_rgba(0,0,0,0.5)]">
                                        <tr>
                                            <th className="px-2 sm:px-4 py-3 border-b border-cyber-border/50">Pos</th>
                                            <th className="px-2 sm:px-4 py-3 border-b border-cyber-border/50">Player</th>
                                            <th className="px-2 sm:px-4 py-3 hidden sm:table-cell border-b border-cyber-border/50">Num</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {roster.map((player) => (
                                            <tr
                                                key={player.player_id || player.id}
                                                className="border-b border-cyber-border/50 hover:bg-white/[0.05] cursor-pointer transition-colors"
                                                onClick={() => navigate(`/player/${player.player_id || player.id}`)}
                                            >
                                                <td className="px-2 sm:px-4 py-3 font-mono text-[10px] tracking-widest text-cyber-blue">{player.position}</td>
                                                <td className="px-2 sm:px-4 py-3 font-display font-600 uppercase tracking-widest text-cyber-text text-xs flex items-center gap-3">
                                                    <img src={getPlayerAvatarUrl(player.id)} className="w-8 h-8 rounded-none border border-cyber-border object-cover object-top" alt="" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                                                    <span className="truncate">{player.name}</span>
                                                </td>
                                                <td className="px-2 sm:px-4 py-3 text-cyber-muted font-mono text-xs hidden sm:table-cell">{player.jersey_number || player.number || "#"}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-cyber-muted font-display tracking-[0.1em] uppercase">
                                    <Users className="w-12 h-12 mb-4 opacity-50 text-cyber-blue" />
                                    <p className="text-xs">Select a team to view roster</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Defensive Bleed and Injuries */}
                    <div className="space-y-6">
                        <div className="bg-cyber-surface border border-cyber-border rounded-none p-6 relative transition-colors duration-300 shadow-none z-10" style={{ border: '1px solid #1a2332' }}>
                            <CornerBrackets />
                            <h3 className="text-lg font-display font-700 tracking-[0.08em] uppercase text-cyber-text mb-4 flex items-center gap-2 relative z-10">
                                <Shield className="w-5 h-5 text-cyber-red" />
                                Defensive Bleed
                            </h3>
                            <div className="h-40 bg-white/[0.02] rounded-none border border-dashed border-cyber-border/50 flex items-center justify-center text-[10px] font-mono tracking-widest uppercase text-cyber-muted relative z-10">
                                [HEATMAP PLACEHOLDER: POINTS ALLOWED BY POSITION]
                            </div>
                        </div>

                        <div className="bg-cyber-surface border border-cyber-border rounded-none p-6 flex flex-col max-h-[250px] relative transition-colors duration-300 shadow-none z-10" style={{ border: '1px solid #1a2332' }}>
                            <CornerBrackets />
                            <h3 className="text-lg font-display font-700 tracking-[0.08em] uppercase text-cyber-text mb-4 flex items-center gap-2 flex-shrink-0 relative z-10">
                                <AlertTriangle className="w-5 h-5 text-cyber-gold" />
                                Injury Report
                            </h3>
                            <div className="space-y-2 overflow-y-auto pr-2 scrollbar-premium flex-1 min-h-0 relative z-10">
                                {loading ? (
                                    <div className="space-y-2">
                                        {[1, 2, 3].map(i => <div key={i} className="h-8 bg-cyber-gold/10 border border-cyber-gold/20 rounded-none animate-pulse" />)}
                                    </div>
                                ) : injuries.length > 0 ? (
                                    <div className="space-y-2">
                                        {injuries.map((injury, idx) => (
                                            <div key={idx} className="flex justify-between items-center text-xs p-2 bg-cyber-red/10 border-l-2 border-cyber-red transition-colors hover:bg-cyber-red/20">
                                                <span className="text-cyber-text font-display font-600 uppercase">{injury.player_name} <span className="text-cyber-muted ml-1 font-mono text-[9px] tracking-widest">[{injury.team}]</span></span>
                                                <span className="text-cyber-red font-mono text-[9px] tracking-widest uppercase">{injury.status} // {injury.injury_type}</span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-[10px] font-mono tracking-widest text-cyber-muted text-center py-4 uppercase border border-dashed border-cyber-border/50 mt-2 bg-white/[0.02]">
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
