import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, Map, Users, Loader2 } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { Modal } from './Modal';

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

            <Modal
                isOpen={isOpen}
                onClose={() => setIsOpen(false)}
                title="Select Context"
                icon={<Map className="w-5 h-5 text-financial-accent" />}
                maxWidth="4xl"
                bodyClassName="p-0 h-[85vh] sm:h-[600px] flex flex-col sm:flex-row bg-slate-900/95 overflow-hidden"
            >
                {/* Column 1: Structure (Conference/Division) */}
                <div className="w-full h-[30%] sm:h-full sm:w-1/4 border-b sm:border-b-0 sm:border-r border-slate-700/50 flex flex-col bg-slate-900/50">
                    <div className="py-2 px-3 sm:p-3 text-[10px] sm:text-xs uppercase font-bold text-slate-500 bg-black/20 tracking-wider sticky top-0 z-10 flex-shrink-0">Divisions</div>
                    <div className="overflow-y-auto flex-1 p-2 space-y-2 sm:space-y-4 text-xs sm:text-sm">
                        {conferences.map((conf) => (
                            <div key={conf.name}>
                                <div className="text-[9px] sm:text-[10px] text-slate-600 font-bold uppercase mb-1 px-2">{conf.name}</div>
                                <div className="flex flex-row overflow-x-auto sm:flex-col gap-2 sm:gap-0 pb-1 sm:pb-0 hide-scrollbar">
                                    {conf.divisions.map((div) => (
                                        <button
                                            key={div.name}
                                            onClick={() => setActiveDivision(div.name)}
                                            className={`
                                                    flex-shrink-0 sm:w-full text-left px-3 py-1.5 text-xs rounded transition-all whitespace-nowrap
                                                    ${activeDivision === div.name
                                                    ? 'bg-financial-accent text-white font-medium'
                                                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200 bg-slate-800/50 sm:bg-transparent'}
                                                `}
                                        >
                                            {div.name}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Column 2: Teams */}
                <div className="w-full h-[30%] sm:h-full sm:w-1/4 border-b sm:border-b-0 sm:border-r border-slate-700/50 flex flex-col bg-slate-900/30">
                    <div className="py-2 px-3 sm:p-3 text-[10px] sm:text-xs uppercase font-bold text-slate-500 bg-black/20 tracking-wider sticky top-0 z-10 flex-shrink-0">Teams</div>
                    <div className="overflow-y-auto overflow-x-hidden flex-1 p-2 grid grid-cols-2 sm:grid-cols-1 gap-1">
                        {activeDivision && conferences.map((conf) =>
                            conf.divisions
                                .filter((div) => div.name === activeDivision)
                                .map((div) =>
                                    div.teams.map((team) => (
                                        <button
                                            key={team.id}
                                            onMouseEnter={() => handleTeamHover(team)}
                                            onClick={() => handleTeamHover(team)}
                                            className={`
                                                    col-span-1 flex items-center gap-2 px-2 sm:px-3 py-1.5 sm:py-2 rounded mb-0 sm:mb-1 text-left transition-all
                                                    ${activeTeam?.id === team.id
                                                    ? 'bg-financial-accent/20 border border-financial-accent text-financial-accent'
                                                    : 'hover:bg-slate-800 text-slate-300 bg-slate-800/30 sm:bg-transparent'}
                                                `}
                                        >
                                            <div className="w-6 h-6 sm:w-8 sm:h-8 rounded flex-shrink-0 bg-slate-800 flex items-center justify-center text-[10px] sm:text-xs font-bold">
                                                {team.abbreviation}
                                            </div>
                                            <span className="text-xs sm:text-sm truncate">{team.name}</span>
                                        </button>
                                    ))
                                )
                        )}
                        {!activeDivision && (
                            <div className="col-span-2 sm:col-span-1 text-center text-slate-500 text-xs sm:text-sm mt-4 sm:mt-10">
                                Select a division first
                            </div>
                        )}
                    </div>
                </div>

                {/* Column 3:Roster (Starters/Rotation/Bench) */}
                <div className="w-full h-[40%] sm:h-full flex-1 sm:w-1/2 flex flex-col bg-slate-900/10">
                    <div className="py-2 px-3 sm:p-3 text-[10px] sm:text-xs uppercase font-bold text-slate-500 bg-black/20 tracking-wider flex items-center gap-2 sticky top-0 z-10 flex-shrink-0">
                        <Users className="w-3.5 h-3.5" />
                        Roster
                    </div>
                    <div className="overflow-y-auto flex-1 p-2 sm:p-4">
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
            </Modal>
        </div>
    );
}
