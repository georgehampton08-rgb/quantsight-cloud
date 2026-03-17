/**
 * InjuryPanel — compact injury report for two teams playing today.
 * Fetches from GET /v1/games/injuries/team/{tricode}
 * Shows stacked pills: status badge + player name + injury label.
 * Silently hides itself if fetch fails or no injuries exist.
 * Auto-refreshes every 5 minutes; manual ⟳ button available.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
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
    Out:          'bg-red-500/20 text-red-400 border-red-500/30',
    Questionable: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    Doubtful:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
    'Day-To-Day': 'bg-yellow-500/15 text-yellow-400 border-yellow-500/25',
    Probable:     'bg-emerald-500/15 text-emerald-500 border-emerald-500/25',
};

const statusStyle = (s: string) =>
    STATUS_STYLES[s] ?? 'bg-slate-700/40 text-slate-400 border-slate-600/30';

/** Returns today's date in YYYY-MM-DD using Eastern Time (NBA schedule timezone). */
function todayET(): string {
    return new Intl.DateTimeFormat('en-CA', {
        timeZone: 'America/New_York',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).format(new Date());
}

/** Format ISO timestamp to a concise local time string, e.g. "10:32 PM" */
function fmtTime(iso: string): string {
    try {
        return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
}

const REFRESH_MS = 5 * 60 * 1000; // 5 minutes

async function fetchTeamInjuries(tricode: string): Promise<{ injuries: InjuryRecord[]; updatedAt?: string }> {
    try {
        const res = await fetch(`${API_BASE}/v1/games/injuries/team/${tricode}`);
        if (!res.ok) return { injuries: [] };
        const d = await res.json();
        // Guard against stale data from a different day (ET)
        if (d.date && d.date !== todayET()) return { injuries: [] };
        return {
            injuries: (d.injuries as InjuryRecord[]) ?? [],
            updatedAt: d.updatedAt,
        };
    } catch {
        return { injuries: [] };
    }
}

function TeamInjuryList({ team }: { team: TeamInjuries }) {
    if (!team.injuries.length) return null;
    return (
        <div className="flex flex-col gap-1.5">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wide px-1">
                {team.tricode} Injuries
            </div>
            <div className="flex flex-col gap-1">
                {team.injuries.map((inj) => (
                    <div
                        key={inj.playerId}
                        className="flex items-center gap-2 px-2 py-1.5 bg-slate-900/50 rounded-lg border border-slate-800/60"
                    >
                        {/* Status badge */}
                        <span className={`flex-shrink-0 text-xs font-bold px-1.5 py-0.5 rounded border uppercase tracking-wide ${statusStyle(inj.status)}`}>
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
                                <span className="text-xs text-slate-500 truncate leading-tight">
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
    const [lastRefresh, setLastRefresh] = useState<string>('');
    const [isRefreshing, setIsRefreshing] = useState(false);

    // Keep latest tricode values accessible inside the interval callback
    const homeRef = useRef(homeTeam);
    const awayRef = useRef(awayTeam);
    homeRef.current = homeTeam;
    awayRef.current = awayTeam;

    const refresh = useCallback(async (showSpinner = false) => {
        if (!homeRef.current || !awayRef.current) return;
        if (showSpinner) setIsRefreshing(true);

        const [homeData, awayData] = await Promise.all([
            fetchTeamInjuries(homeRef.current),
            fetchTeamInjuries(awayRef.current),
        ]);

        setHome(homeData.injuries.length
            ? { tricode: homeRef.current, injuries: homeData.injuries, updatedAt: homeData.updatedAt }
            : null
        );
        setAway(awayData.injuries.length
            ? { tricode: awayRef.current, injuries: awayData.injuries, updatedAt: awayData.updatedAt }
            : null
        );
        setLastRefresh(new Date().toISOString());
        if (showSpinner) setIsRefreshing(false);
    }, []);

    // Initial load + re-load when teams change
    useEffect(() => {
        if (!homeTeam || !awayTeam) return;
        setHome(null);
        setAway(null);
        setLastRefresh('');
        refresh();
    }, [homeTeam, awayTeam, refresh]);

    // Auto-refresh every 5 minutes
    useEffect(() => {
        if (!homeTeam || !awayTeam) return;
        const id = setInterval(() => refresh(), REFRESH_MS);
        return () => clearInterval(id);
    }, [homeTeam, awayTeam, refresh]);

    // Only render if there's at least one injury
    if (!home && !away) return null;

    // Pick the most recent updatedAt from either team for the header
    const serverUpdatedAt = home?.updatedAt ?? away?.updatedAt ?? '';

    return (
        <div className="px-3 py-3 bg-slate-900/40 border border-slate-800/60 rounded-xl">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <span className="text-sm">🏥</span>
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wide">
                    Injury Report
                </span>
                {/* Refresh button */}
                <button
                    onClick={() => refresh(true)}
                    title="Refresh injury data"
                    disabled={isRefreshing}
                    style={{
                        background: 'none',
                        border: 'none',
                        cursor: isRefreshing ? 'default' : 'pointer',
                        padding: '0 2px',
                        lineHeight: 1,
                        opacity: isRefreshing ? 0.4 : 0.7,
                        transition: 'opacity 0.2s',
                    }}
                >
                    <span
                        style={{
                            display: 'inline-block',
                            fontSize: '13px',
                            color: '#94a3b8',
                            animation: isRefreshing ? 'spin 1s linear infinite' : 'none',
                        }}
                    >
                        ⟳
                    </span>
                </button>
                <span className="text-xs text-slate-600 ml-auto" title={serverUpdatedAt ? `ESPN updated: ${serverUpdatedAt}` : undefined}>
                    {lastRefresh ? `Updated ${fmtTime(lastRefresh)}` : 'via ESPN'}
                </span>
            </div>

            {/* Two-column or single-column list */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {away && <TeamInjuryList team={away} />}
                {home && <TeamInjuryList team={home} />}
            </div>
        </div>
    );
}
