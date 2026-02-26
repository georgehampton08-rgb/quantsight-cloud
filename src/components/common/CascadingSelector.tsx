import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, Map, Users, Loader2 } from 'lucide-react';
import { ApiContract } from '../../api/client';

// Types for real data structure
interface NBATeam {
    id: string;
    name: string;
    abbreviation: string;
}

interface NBADivision {
    name: string;
    teams: NBATeam[];
}

interface NBAConference {
    name: string;
    divisions: NBADivision[];
}

interface Player {
    player_id: string;
    name: string;
    position?: string;
    jersey_number?: string;
    status?: string;
}

export default function CascadingSelector() {
    const [isOpen, setIsOpen] = useState(false);
    const [conferences, setConferences] = useState<NBAConference[]>([]);
    const [activeDivision, setActiveDivision] = useState<string | null>(null);
    const [activeTeam, setActiveTeam] = useState<NBATeam | null>(null);
    const [teamPlayers, setTeamPlayers] = useState<Player[]>([]);
    const [loading, setLoading] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    // Load teams on mount
    useEffect(() => {
        const loadTeams = async () => {
            try {
                const res = await ApiContract.execute<any>('getTeams', { path: 'teams' });
                const data = res.data;

                if (data && data.conferences) {
                    console.log(`[CascadingSelector] Loaded ${data.conferences.length} conferences`);
                    setConferences(data.conferences);
                }
            } catch (error) {
                console.error('[CascadingSelector] Failed to load teams:', error);
            }
        };
        loadTeams();
    }, []);

    // Load roster when team is hovered
    const handleTeamHover = async (team: NBATeam) => {
        setActiveTeam(team);
        setLoading(true);
        try {
            const res = await ApiContract.execute<any>('getRoster', { path: `roster/${team.id}` }, [team.id]);
            const data = res.data;

            if (data && data.roster) {
                setTeamPlayers(data.roster);
            } else {
                setTeamPlayers([]);
            }
        } catch (error) {
            console.error('[CascadingSelector] Failed to load roster:', error);
            setTeamPlayers([]);
        } finally {
            setLoading(false);
        }
    };

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handlePlayerClick = (player: Player) => {
        setIsOpen(false);
        navigate(`/player/${player.player_id}`);
    };

    return (
        <div className="relative z-50 mr-4" ref={containerRef}>
            {/* Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`
                    flex items-center gap-2 px-4 py-2 rounded-lg border transition-all duration-300
                    ${isOpen
                        ? 'bg-financial-accent/20 border-financial-accent text-financial-accent'
                        : 'bg-slate-800/50 border-slate-600 text-slate-300 hover:bg-slate-700/50 hover:border-slate-500'}
                `}
            >
                <Map className="w-4 h-4" />
                <span className="font-medium text-sm tracking-wide">Select Context</span>
                <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Mega Menu Overlay */}
            {isOpen && (
                <div className="absolute top-full left-0 mt-3 w-[800px] h-[500px] bg-slate-900/95 backdrop-blur-xl border border-slate-700 rounded-xl shadow-2xl flex overflow-hidden animate-in fade-in zoom-in-95 duration-200 z-[100]">

                    {/* Column 1: Structure (Conference/Division) */}
                    <div className="w-1/4 border-r border-slate-700/50 flex flex-col bg-slate-900/50">
                        <div className="p-3 text-xs uppercase font-bold text-slate-500 bg-black/20 tracking-wider">Divisions</div>
                        <div className="overflow-y-auto flex-1 p-2 space-y-4">
                            {conferences.map((conf) => (
                                <div key={conf.name}>
                                    <div className="text-[10px] text-slate-600 font-bold uppercase mb-1 px-2">{conf.name}</div>
                                    {conf.divisions.map((div) => (
                                        <div key={div.name}>
                                            <button
                                                onClick={() => setActiveDivision(div.name)}
                                                className={`
                                                    w-full text-left px-3 py-1.5 text-xs rounded transition-all
                                                    ${activeDivision === div.name
                                                        ? 'bg-financial-accent text-white font-medium'
                                                        : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}
                                                `}
                                            >
                                                {div.name}
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Column 2: Teams */}
                    <div className="w-1/4 border-r border-slate-700/50 flex flex-col bg-slate-900/30">
                        <div className="p-3 text-xs uppercase font-bold text-slate-500 bg-black/20 tracking-wider">Teams</div>
                        <div className="overflow-y-auto flex-1 p-2">
                            {activeDivision && conferences.map((conf) =>
                                conf.divisions
                                    .filter((div) => div.name === activeDivision)
                                    .map((div) =>
                                        div.teams.map((team) => (
                                            <button
                                                key={team.id}
                                                onMouseEnter={() => handleTeamHover(team)}
                                                className={`
                                                    w-full flex items-center gap-2 px-3 py-2 rounded mb-1 text-left transition-all
                                                    ${activeTeam?.id === team.id
                                                        ? 'bg-financial-accent/20 border border-financial-accent text-financial-accent'
                                                        : 'hover:bg-slate-800 text-slate-300'}
                                                `}
                                            >
                                                <div className="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold">
                                                    {team.abbreviation}
                                                </div>
                                                <span className="text-sm">{team.name}</span>
                                            </button>
                                        ))
                                    )
                            )}
                        </div>
                    </div>

                    {/* Column 3:Roster (Starters/Rotation/Bench) */}
                    <div className="w-1/2 flex flex-col bg-slate-900/10">
                        <div className="p-3 text-xs uppercase font-bold text-slate-500 bg-black/20 tracking-wider flex items-center gap-2">
                            <Users className="w-3.5 h-3.5" />
                            Roster
                        </div>
                        <div className="overflow-y-auto flex-1 p-4">
                            {loading ? (
                                <div className="flex items-center justify-center h-full">
                                    <Loader2 className="w-6 h-6 animate-spin text-financial-accent" />
                                </div>
                            ) : teamPlayers.length > 0 ? (
                                <div className="space-y-1">
                                    {teamPlayers.map((player) => (
                                        <button
                                            key={player.player_id}
                                            onClick={() => handlePlayerClick(player)}
                                            className="w-full flex items-center justify-between px-3 py-2 rounded hover:bg-slate-800/50 text-left transition-all group"
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-financial-accent to-purple-600 flex items-center justify-center text-white text-xs font-bold">
                                                    {player.jersey_number || '?'}
                                                </div>
                                                <div>
                                                    <div className="text-sm font-medium text-slate-200 group-hover:text-financial-accent transition-colors">
                                                        {player.name}
                                                    </div>
                                                    <div className="text-xs text-slate-500">
                                                        {player.position || 'N/A'}
                                                    </div>
                                                </div>
                                            </div>
                                            {player.status && player.status !== 'active' && (
                                                <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                                                    {player.status}
                                                </span>
                                            )}
                                        </button>
                                    ))}
                                </div>
                            ) : activeTeam ? (
                                <div className="text-center text-slate-500 text-sm mt-20">
                                    No roster data available for {activeTeam.name}
                                </div>
                            ) : (
                                <div className="text-center text-slate-500 text-sm mt-20">
                                    Select a team to view roster
                                </div>
                            )}
                        </div>
                    </div>

                </div>
            )}
        </div>
    );
}
