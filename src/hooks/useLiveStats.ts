import { useState, useRef, useEffect, useMemo } from 'react';
import { ApiContract } from '../api/client';

export interface LivePlayerStat {
    player_id: string;
    name: string;
    team: string;
    pie: number;
    plus_minus: number;
    ts_pct: number;
    efg_pct: number;
    heat_status: 'blazing' | 'hot' | 'steady' | 'cold' | 'freezing';
    efficiency_trend: 'surging' | 'steady' | 'dipping';
    season_ts_pct: number | null;
    season_efg_pct: number | null;
    opponent_team: string | null;
    opponent_def_rating: number | null;
    matchup_difficulty: 'elite' | 'average' | 'soft' | null;
    has_usage_vacuum: boolean;
    usage_bump: number | null;
    vacuum_source: string | null;
    stats: {
        pts: number;
        reb: number;
        ast: number;
        stl?: number;
        blk?: number;
    };
    min: string;
}

export interface LiveGame {
    game_id: string;
    home_team: string;
    away_team: string;
    home_score: number;
    away_score: number;
    clock: string;
    period: number;
    status: 'LIVE' | 'HALFTIME' | 'FINAL' | 'UPCOMING';
    leaders: LivePlayerStat[];
    last_updated: string;
    is_garbage_time: boolean;
}

export interface UseLiveStatsReturn {
    games: LiveGame[];
    leaders: LivePlayerStat[];
    liveCount: number;
    isConnected: boolean;
    isConnecting: boolean;
    error: Error | null;
    lastUpdate: string | null;
    changedPlayerIds: Set<string>;
    connect: () => void;
    disconnect: () => void;
}

export function useLiveStats(): UseLiveStatsReturn {
    const [games, setGames] = useState<LiveGame[]>([]);
    const [liveCount, setLiveCount] = useState(0);
    const [lastUpdate, setLastUpdate] = useState<string | null>(null);
    const [changedPlayerIds, setChangedPlayerIds] = useState<Set<string>>(new Set());
    const [rawLeaders, setRawLeaders] = useState<LivePlayerStat[]>([]);

    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<Error | null>(null);

    const prevStatsRef = useRef<Record<string, number>>({});
    const pollIntervalRef = useRef<any>(null);
    const isMounted = useRef(false);

    const leaders = useMemo(() => {
        return [...rawLeaders].sort((a, b) => b.pie - a.pie).slice(0, 10);
    }, [rawLeaders]);

    const connect = () => {
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        setIsConnecting(true);
        fetchPulseData();
        pollIntervalRef.current = setInterval(fetchPulseData, 12000);
    };

    const disconnect = () => {
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        setIsConnected(false);
        setIsConnecting(false);
    };

    const fetchPulseData = async () => {
        if (!isMounted.current) return;
        try {
            // 1. Fetch Schedule
            const schedResponse = await ApiContract.pulse<any>({ path: 'schedule' });

            if (!schedResponse || !schedResponse.games) {
                throw new Error("Invalid schedule format");
            }

            const scheduleGames = schedResponse.games;

            let currentLiveCount = 0;
            const updatedGames: LiveGame[] = [];
            let allLeaders: LivePlayerStat[] = [];

            const changed = new Set<string>();
            const newStatsRef: Record<string, number> = {};

            for (const schedGame of scheduleGames) {
                const isLive = schedGame.status === 2 || schedGame.status === 'LIVE' || schedGame.status === 'HALFTIME';
                const isDone = schedGame.status === 3 || schedGame.status === 'FINAL';
                const statusLabel = isLive ? 'LIVE' : (isDone ? 'FINAL' : 'UPCOMING');
                if (isLive) currentLiveCount++;

                let gameLeaders: LivePlayerStat[] = [];
                const parsedGameId = (schedGame.game_id || schedGame.gameId);

                // 2. Fetch Boxscores for any active or final games
                if (isLive || isDone) {
                    try {
                        const boxRes = await ApiContract.pulse<any>({ path: `pulse/boxscore/${parsedGameId}` });
                        if (boxRes && (boxRes.home || boxRes.away)) {
                            const homePlayers = boxRes.home || [];
                            const awayPlayers = boxRes.away || [];
                            const allGamePlayers = [...homePlayers, ...awayPlayers];

                            // Calculate game totals for PIE (Proxy for EFF)
                            let totalPts = 0, totalReb = 0, totalAst = 0;
                            allGamePlayers.forEach((p: any) => {
                                totalPts += p.pts || 0;
                                totalReb += p.reb || 0;
                                totalAst += p.ast || 0;
                            });

                            allGamePlayers.forEach((p: any) => {
                                const minVal = p.min || p.minutes || "0:00";
                                if (minVal === "0:00" || minVal === "0") return;

                                const pPts = p.pts || 0;
                                const pReb = p.reb || 0;
                                const pAst = p.ast || 0;
                                const pBlk = p.blk || 0;
                                const pStl = p.stl || 0;
                                const pFga = p.fga || 0;
                                const pFgm = p.fgm || 0;
                                const pFta = p.fta || 0;
                                const pFtm = p.ftm || 0;
                                const pTov = p.tov || 0;

                                // Proxy efficiency score for Pie mapping
                                const effScore = (pPts + pReb + pAst + pStl + pBlk - (pFga - pFgm) - (pFta - pFtm) - pTov);
                                // A rough PIE equivalent based on proxy weight
                                const calcPie = totalPts > 0 ? (effScore / (totalPts + totalAst + totalReb)) || 0 : 0;
                                // Add 0.05 to pie to make the UI look similar to real PIE scale logic
                                const adjPie = Math.max(0, calcPie * 1.5);

                                const playerId = p.player_id || p.id;

                                // Check for changes
                                if (isLive && prevStatsRef.current[playerId] !== undefined && prevStatsRef.current[playerId] !== pPts) {
                                    changed.add(playerId);
                                }
                                newStatsRef[playerId] = pPts;

                                const statObj: LivePlayerStat = {
                                    player_id: playerId,
                                    name: p.player_name || p.name,
                                    team: homePlayers.includes(p) ? (schedGame.home || schedGame.home_team) : (schedGame.away || schedGame.away_team),
                                    pie: adjPie,
                                    plus_minus: p.plus_minus || 0,
                                    ts_pct: pFga > 0 ? (pPts / (2 * (pFga + 0.44 * pFta))) : 0,
                                    efg_pct: pFga > 0 ? ((pFgm + 0.5 * (p.fg3m || 0)) / pFga) : 0,
                                    heat_status: 'steady',
                                    efficiency_trend: 'steady',
                                    season_ts_pct: null,
                                    season_efg_pct: null,
                                    opponent_team: homePlayers.includes(p) ? (schedGame.away || schedGame.away_team) : (schedGame.home || schedGame.home_team),
                                    opponent_def_rating: null,
                                    matchup_difficulty: null,
                                    has_usage_vacuum: false,
                                    usage_bump: null,
                                    vacuum_source: null,
                                    stats: {
                                        pts: pPts,
                                        reb: pReb,
                                        ast: pAst,
                                        stl: pStl,
                                        blk: pBlk
                                    },
                                    min: minVal
                                };

                                gameLeaders.push(statObj);
                            });
                        }
                    } catch (err) {
                        console.error('Failed fetching box score for game', parsedGameId, err);
                    }
                }

                gameLeaders.sort((a, b) => b.pie - a.pie);
                const gameObj: LiveGame = {
                    game_id: parsedGameId,
                    home_team: schedGame.home || schedGame.home_team,
                    away_team: schedGame.away || schedGame.away_team,
                    home_score: schedGame.home_score || 0,
                    away_score: schedGame.away_score || 0,
                    clock: schedGame.clock || (isDone ? 'Final' : ''),
                    period: schedGame.period || 0,
                    status: statusLabel as any,
                    leaders: gameLeaders.slice(0, 5),
                    last_updated: new Date().toISOString(),
                    is_garbage_time: false
                };

                updatedGames.push(gameObj);

                // Only push live and final players to the main leaderboard list
                if (isLive || isDone) {
                    allLeaders.push(...gameLeaders);
                }
            }

            if (!isMounted.current) return;

            setGames(updatedGames);
            setLiveCount(currentLiveCount);
            setRawLeaders(allLeaders);
            setLastUpdate(new Date().toISOString());
            setIsConnected(true);
            setIsConnecting(false);
            setError(null);

            if (changed.size > 0) {
                setChangedPlayerIds(changed);
                setTimeout(() => {
                    if (isMounted.current) setChangedPlayerIds(new Set());
                }, 2000);
            }

            prevStatsRef.current = newStatsRef;

        } catch (err: any) {
            console.error('Pulse poll error', err);
            if (isMounted.current) {
                setError(err);
                setIsConnected(false);
                setIsConnecting(false);
            }
        }
    };

    useEffect(() => {
        isMounted.current = true;
        connect();
        return () => {
            isMounted.current = false;
            disconnect();
        };
    }, []);

    return {
        games,
        leaders,
        liveCount,
        isConnected,
        isConnecting,
        error,
        lastUpdate,
        changedPlayerIds,
        connect,
        disconnect
    };
}

export function usePlayerPulse(playerId: string, changedPlayerIds: Set<string>, durationMs: number = 3000): boolean {
    const [isPulsing, setIsPulsing] = useState(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        const shouldPulse = changedPlayerIds.has(playerId);

        if (shouldPulse && !isPulsing) {
            setIsPulsing(true);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            timeoutRef.current = setTimeout(() => {
                setIsPulsing(false);
            }, durationMs);
        }
        return () => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
        };
    }, [playerId, changedPlayerIds, isPulsing, durationMs]);

    return isPulsing;
}

export default useLiveStats;
