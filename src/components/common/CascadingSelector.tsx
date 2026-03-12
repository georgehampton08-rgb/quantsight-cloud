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

    // Modal component natively handles backdrop clicks via onClose; custom native hook not needed
    const handlePlayerClick = (player: Player) => {
        setIsOpen(false);
        navigate(`/player/${player.player_id}`);
    };

    return (
        <div className="relative z-50 md:mr-4 w-full" ref={containerRef}>
            {/* Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`
                    flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all duration-200
                    ${isOpen
                        ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-500'
                        : 'bg-pro-surface border-pro-border text-pro-text hover:bg-white/[0.05]'}
                `}
            >
                <Map className="w-4 h-4 flex-shrink-0 opacity-70" />
                <span className="font-medium text-sm truncate">Select Context</span>
                <ChevronDown className={`w-4 h-4 transition-transform flex-shrink-0 opacity-70 ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            <Modal
                isOpen={isOpen}
                onClose={() => setIsOpen(false)}
                title="Select Context"
                icon={<Map className="w-5 h-5 text-emerald-500" />}
                maxWidth="4xl"
                bodyClassName="p-0 h-[85vh] sm:h-[600px] flex flex-col sm:flex-row bg-pro-bg overflow-hidden"
            >
                {/* Column 1: Structure (Conference/Division) */}
                <div className="w-full h-[30%] sm:h-full sm:w-1/4 border-b sm:border-b-0 sm:border-r border-pro-border flex flex-col bg-pro-surface/50">
                    <div className="py-2 px-3 sm:px-4 sm:py-3 text-xs font-semibold text-pro-muted border-b border-pro-border/50 uppercase tracking-wide sticky top-0 z-10 bg-pro-bg flex-shrink-0">Divisions</div>
                    <div className="overflow-y-auto flex-1 p-2 space-y-2 sm:space-y-4">
                        {conferences.map((conf) => (
                            <div key={conf.name}>
                                <div className="text-xs text-pro-muted font-bold uppercase mb-1 px-2">{conf.name}</div>
                                <div className="flex flex-row overflow-x-auto sm:flex-col gap-1 pb-1 sm:pb-0 hide-scrollbar">
                                    {conf.divisions.map((div) => (
                                        <button
                                            key={div.name}
                                            onClick={() => setActiveDivision(div.name)}
                                            className={`
                                                    flex-shrink-0 sm:w-full text-left px-3 py-2 text-sm rounded-lg transition-all whitespace-nowrap
                                                    ${activeDivision === div.name
                                                    ? 'bg-emerald-500/10 text-emerald-500 font-medium border border-emerald-500/20'
                                                    : 'text-pro-text hover:bg-white/[0.05] border border-transparent'}
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
                <div className="w-full h-[30%] sm:h-full sm:w-1/4 border-b sm:border-b-0 sm:border-r border-pro-border flex flex-col bg-pro-surface/30">
                    <div className="py-2 px-3 sm:px-4 sm:py-3 text-xs font-semibold text-pro-muted border-b border-pro-border/50 uppercase tracking-wide sticky top-0 z-10 bg-pro-bg flex-shrink-0">Teams</div>
                    <div className="overflow-y-auto overflow-x-hidden flex-1 p-2 grid grid-cols-2 sm:grid-cols-1 gap-1">
                        {activeDivision && conferences.map((conf) =>
                            conf.divisions
                                .filter((div) => div.name === activeDivision)
                                .map((div) =>
                                    div.teams.map((team) => (
                                        <button
                                            key={team.id}
                                            onClick={() => handleTeamHover(team)}
                                            className={`
                                                    col-span-1 flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all
                                                    ${activeTeam?.id === team.id
                                                    ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-500'
                                                    : 'hover:bg-white/[0.05] text-pro-text border border-transparent'}
                                                `}
                                        >
                                            <div className="w-8 h-8 rounded-md bg-pro-bg border border-pro-border flex-shrink-0 flex items-center justify-center text-xs font-bold text-pro-muted">
                                                {team.abbreviation}
                                            </div>
                                            <span className="text-sm font-medium truncate">{team.name}</span>
                                        </button>
                                    ))
                                )
                        )}
                        {!activeDivision && (
                            <div className="col-span-2 sm:col-span-1 text-center text-pro-muted text-sm mt-4 sm:mt-10">
                                Select a division first
                            </div>
                        )}
                    </div>
                </div>

                {/* Column 3: Roster */}
                <div className="w-full h-[40%] sm:h-full flex-1 sm:w-1/2 flex flex-col bg-pro-bg">
                    <div className="py-2 px-3 sm:px-4 sm:py-3 text-xs font-semibold text-pro-muted border-b border-pro-border/50 uppercase tracking-wide sticky top-0 z-10 flex items-center gap-2 flex-shrink-0 bg-pro-bg">
                        <Users className="w-4 h-4 opacity-70" />
                        Roster
                    </div>
                    <div className="overflow-y-auto flex-1 p-2 sm:p-4">
                        {loading ? (
                            <div className="flex items-center justify-center h-full">
                                <Loader2 className="w-6 h-6 animate-spin text-emerald-500" />
                            </div>
                        ) : teamPlayers.length > 0 ? (
                            <div className="space-y-1">
                                {teamPlayers.map((player) => (
                                    <button
                                        key={player.player_id}
                                        onClick={() => handlePlayerClick(player)}
                                        className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/[0.05] text-left transition-all group border border-transparent hover:border-pro-border/50"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-pro-surface border border-pro-border flex items-center justify-center text-pro-muted text-xs font-mono font-bold">
                                                {player.jersey_number || '?'}
                                            </div>
                                            <div>
                                                <div className="text-sm font-medium text-pro-text group-hover:text-emerald-500 transition-colors">
                                                    {player.name}
                                                </div>
                                                <div className="text-xs text-pro-muted">
                                                    {player.position || 'N/A'}
                                                </div>
                                            </div>
                                        </div>
                                        {player.status && player.status !== 'active' && (
                                            <span className="text-xs px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-500 border border-amber-500/20 font-medium tracking-wide">
                                                {player.status}
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        ) : activeTeam ? (
                            <div className="text-center text-pro-muted text-sm mt-20">
                                No roster data available for {activeTeam.name}
                            </div>
                        ) : (
                            <div className="text-center text-pro-muted text-sm mt-20">
                                Select a team to view roster
                            </div>
                        )}
                    </div>
                </div>
            </Modal>
        </div>
    );
}
