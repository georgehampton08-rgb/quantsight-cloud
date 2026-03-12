/**
 * InjuryPanel — compact injury report for two teams playing today.
 * Fetches from GET /v1/games/injuries/team/{tricode}
 * Shows stacked pills: status badge + player name + injury label.
 * Silently hides itself if fetch fails or no injuries exist.
 */
import React, { useEffect, useState } from 'react';
import { API_BASE } from '../../config/apiConfig';

interface InjuryRecord {
    playerId: string;
    playerName: string;
    position: string;
    status: string;
    injuryType: string;
    comment?: string;
    teamTricode: string;
    espnId?: string;
}

interface TeamInjuries {
    tricode: string;
    injuries: InjuryRecord[];
    updatedAt?: string;
}

interface Props {
    homeTeam: string;
    awayTeam: string;
}

const STATUS_STYLES: Record<string, string> = {
    Out:         'bg-red-500/20 text-red-400 border-red-500/30',
    Questionable:'bg-amber-500/20 text-amber-400 border-amber-500/30',
    Doubtful:    'bg-orange-500/20 text-orange-400 border-orange-500/30',
    'Day-To-Day':'bg-yellow-500/15 text-yellow-400 border-yellow-500/25',
    Probable:    'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
};

const statusStyle = (s: string) =>
    STATUS_STYLES[s] ?? 'bg-slate-700/40 text-slate-400 border-slate-600/30';

async function fetchTeamInjuries(tricode: string): Promise<InjuryRecord[]> {
    try {
        const res = await fetch(`${API_BASE}/v1/games/injuries/team/${tricode}`);
        if (!res.ok) return [];
        const d = await res.json();
        return (d.injuries as InjuryRecord[]) ?? [];
    } catch {
        return [];
    }
}

function TeamInjuryList({ team }: { team: TeamInjuries }) {
    if (!team.injuries.length) return null;
    return (
        <div className="flex flex-col gap-1.5">
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest px-1">
                {team.tricode} Injuries
            </div>
            <div className="flex flex-col gap-1">
                {team.injuries.map((inj) => (
                    <div
                        key={inj.playerId}
                        className="flex items-center gap-2 px-2 py-1.5 bg-slate-900/50 rounded-lg border border-slate-800/60"
                    >
                        {/* Status badge */}
                        <span className={`flex-shrink-0 text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wide ${statusStyle(inj.status)}`}>
                            {inj.status === 'Day-To-Day' ? 'DTD' : inj.status.charAt(0)}
                        </span>
                        {/* Player headshot — ESPN CDN primary, NBA CDN fallback */}
                        <img
                            src={inj.espnId
                                ? `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${inj.espnId}.png&w=64&h=46&scale=crop&cquality=40`
                                : `https://cdn.nba.com/headshots/nba/latest/260x190/${inj.playerId}.png`}
                            alt={inj.playerName}
                            className="w-6 h-5 object-cover rounded flex-shrink-0 opacity-80"
                            onError={(e) => {
                                const img = e.target as HTMLImageElement;
                                if (img.src.includes('espncdn') && inj.playerId) {
                                    img.src = `https://cdn.nba.com/headshots/nba/latest/260x190/${inj.playerId}.png`;
                                } else {
                                    img.style.display = 'none';
                                }
                            }}
                        />
                        {/* Name + injury */}
                        <div className="flex flex-col min-w-0">
                            <span className="text-[11px] font-semibold text-slate-200 truncate leading-tight">
                                {inj.playerName}
                            </span>
                            {inj.injuryType && (
                                <span className="text-[10px] text-slate-500 truncate leading-tight">
                                    {inj.injuryType}
                                </span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

export function InjuryPanel({ homeTeam, awayTeam }: Props) {
    const [home, setHome] = useState<TeamInjuries | null>(null);
    const [away, setAway] = useState<TeamInjuries | null>(null);

    useEffect(() => {
        if (!homeTeam || !awayTeam) return;
        setHome(null);
        setAway(null);

        fetchTeamInjuries(homeTeam).then(inj => {
            if (inj.length) setHome({ tricode: homeTeam, injuries: inj });
        });
        fetchTeamInjuries(awayTeam).then(inj => {
            if (inj.length) setAway({ tricode: awayTeam, injuries: inj });
        });
    }, [homeTeam, awayTeam]);

    // Only render if there's at least one injury
    if (!home && !away) return null;

    return (
        <div className="px-3 py-3 bg-slate-900/40 border border-slate-800/60 rounded-xl">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <span className="text-sm">🏥</span>
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
                    Injury Report
                </span>
                <span className="text-[9px] text-slate-600 ml-auto">via ESPN</span>
            </div>

            {/* Two-column or single-column list */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {away && <TeamInjuryList team={away} />}
                {home && <TeamInjuryList team={home} />}
            </div>
        </div>
    );
}
