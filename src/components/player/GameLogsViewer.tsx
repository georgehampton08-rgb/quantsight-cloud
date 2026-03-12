import React, { useEffect, useState, useCallback } from 'react';
import { Activity, BarChart2, ChevronDown, ShieldAlert, Crosshair } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

interface GameLog {
    GAME_ID: string;
    GAME_DATE: string;
    MATCHUP: string;
    WL: string;
    MIN: number;
    PTS: number;
    REB: number;
    AST: number;
    STL: number;
    BLK: number;
    TOV: number;
    PF?: number;
    FG_PCT: number;
    FG3_PCT: number;
    FT_PCT: number;
    PLUS_MINUS: number;
}

type GameCount = 5 | 10 | 20;

export function GameLogsViewerContent({ playerId }: { playerId: string }) {
    const [loading, setLoading] = useState(true);
    const [allLogs, setAllLogs] = useState<GameLog[]>([]);
    const [count, setCount] = useState<GameCount>(5);
    const [error, setError] = useState<string | null>(null);
    const [source, setSource] = useState<string>('');

    const loadLogs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await ApiContract.execute<{ logs: GameLog[]; source?: string }>(null, {
                path: `player-data/logs/${playerId}`
            });
            if (res.data?.logs && res.data.logs.length > 0) {
                setAllLogs(res.data.logs);
                setSource(res.data.source || '');
            } else {
                setError('No recent game logs found. Run the backfill script to populate data.');
            }
        } catch (e: any) {
            setError(e.message || 'Failed to fetch game logs.');
        } finally {
            setLoading(false);
        }
    }, [playerId]);

    useEffect(() => {
        if (playerId && playerId !== '0') loadLogs();
    }, [loadLogs, playerId]);

    if (!playerId || playerId === '0') return null;

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-12 space-y-4 border border-slate-800 rounded-xl bg-slate-900/30">
                <Activity className="w-8 h-8 text-slate-500 animate-spin" />
                <div className="text-sm text-slate-400 font-mono tracking-wide">PULLING GAME LOGS...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-6 rounded-xl border border-red-900/30 bg-red-900/10 flex items-start gap-4">
                <ShieldAlert className="w-6 h-6 text-red-500 flex-shrink-0 mt-1" />
                <div>
                    <h3 className="text-red-400 font-bold mb-1">Telemetry Fetch Failed</h3>
                    <p className="text-slate-400 text-sm">{error}</p>
                    <button onClick={loadLogs} className="mt-3 px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded transition-colors">
                        RETRY
                    </button>
                </div>
            </div>
        );
    }

    if (allLogs.length === 0) {
        return (
            <div className="p-12 text-center text-slate-500 border border-slate-800 rounded-xl bg-slate-900/30">
                Data pipeline active. Waiting for player activity to populate.
            </div>
        );
    }

    const logs = allLogs.slice(0, count);
    const availableCounts: GameCount[] = [5, 10, 20].filter(n => n <= allLogs.length) as GameCount[];
    if (!availableCounts.includes(count) && availableCounts.length > 0) {
        // auto-select max available if chosen count isn't available
    }

    const getStatColor = (val: number, good: number, elite: number) => {
        if (val >= elite) return 'text-emerald-500 font-bold';
        if (val >= good) return 'text-emerald-500/80';
        return 'text-slate-300';
    };

    const getPlusMinusColor = (val: number) => {
        if (val > 0) return 'text-emerald-500';
        if (val < 0) return 'text-red-400';
        return 'text-slate-500';
    };

    // Summary averages over selected games
    const avg = (field: keyof GameLog) => {
        const total = logs.reduce((s, g) => s + (Number(g[field]) || 0), 0);
        return (total / logs.length).toFixed(1);
    };

    return (
        <div className="space-y-4">
            {/* Header row */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-indigo-400" />
                    Game Log
                    <span className="text-xs text-slate-500 font-mono normal-case ml-1">
                        {source === 'espn_player_game_logs' ? '· ESPN' : ''}
                    </span>
                </h3>

                {/* Count selector */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 font-mono">LAST</span>
                    <div className="relative">
                        <select
                            value={count}
                            onChange={e => setCount(Number(e.target.value) as GameCount)}
                            className="appearance-none bg-slate-800 border border-slate-700 rounded-lg pl-3 pr-8 py-1.5 text-sm text-white font-mono cursor-pointer focus:outline-none focus:border-indigo-500 transition-colors"
                        >
                            {[5, 10, 20].map(n => (
                                <option key={n} value={n} disabled={n > allLogs.length}>
                                    {n} {n > allLogs.length ? `(${allLogs.length} avail.)` : 'GAMES'}
                                </option>
                            ))}
                        </select>
                        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
                    </div>
                </div>
            </div>

            {/* Averages bar */}
            <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                {[
                    { label: 'PPG', val: avg('PTS'), color: 'text-amber-400' },
                    { label: 'RPG', val: avg('REB'), color: 'text-blue-500' },
                    { label: 'APG', val: avg('AST'), color: 'text-purple-400' },
                    { label: 'STL', val: avg('STL'), color: 'text-emerald-500' },
                    { label: 'BLK', val: avg('BLK'), color: 'text-cyan-400' },
                    { label: 'TOV', val: avg('TOV'), color: 'text-red-400' },
                    { label: 'FG%', val: `${(Number(avg('FG_PCT')) * 100).toFixed(1)}%`, color: 'text-slate-200' },
                ].map(s => (
                    <div key={s.label} className="bg-slate-800/60 rounded-lg p-2.5 text-center border border-slate-700/40">
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{s.label}</div>
                        <div className={`text-base font-bold font-mono ${s.color}`}>{s.val}</div>
                    </div>
                ))}
            </div>

            {/* Table — scrollable on mobile */}
            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl overflow-hidden shadow-2xl">
                <div className="overflow-x-auto -webkit-overflow-scrolling-touch">
                    <table className="w-full text-sm text-left whitespace-nowrap min-w-[600px]">
                        <thead className="text-xs uppercase bg-slate-800/80 text-slate-400 border-b border-slate-700/50">
                            <tr>
                                <th className="px-3 py-2.5 font-semibold tracking-wider sticky left-0 z-20 bg-slate-800/95 backdrop-blur-sm min-w-[130px]">
                                    Date / Matchup
                                </th>
                                <th className="px-3 py-2.5 text-center">MIN</th>
                                <th className="px-3 py-2.5 text-center">PTS</th>
                                <th className="px-3 py-2.5 text-center">REB</th>
                                <th className="px-3 py-2.5 text-center">AST</th>
                                <th className="px-3 py-2.5 text-center">STL/BLK</th>
                                <th className="px-3 py-2.5 text-center">TOV</th>
                                <th className="px-3 py-2.5 text-center">FG%</th>
                                <th className="px-3 py-2.5 text-center">3P%</th>
                                <th className="px-3 py-2.5 text-center">+/-</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-mono">
                            {logs.map((log, i) => (
                                <tr
                                    key={log.GAME_ID || i}
                                    className="bg-slate-900/40 hover:bg-slate-800/40 transition-colors group"
                                >
                                    {/* Date + Matchup (sticky) */}
                                    <td className="px-3 py-2.5 sticky left-0 z-10 bg-slate-900/90 group-hover:bg-slate-800/90 backdrop-blur-sm border-r border-slate-800/30 transition-colors">
                                        <div className="flex flex-col">
                                            <div className="flex items-center gap-1.5">
                                                {log.WL && (
                                                    <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${log.WL === 'W' ? 'bg-emerald-500/20 text-emerald-500' : 'bg-red-500/20 text-red-400'}`}>
                                                        {log.WL}
                                                    </span>
                                                )}
                                                <span className="text-slate-300 font-sans text-xs font-bold truncate max-w-[90px]">
                                                    {log.MATCHUP}
                                                </span>
                                            </div>
                                            <span className="text-xs text-slate-500 tracking-wide">
                                                {log.GAME_DATE
                                                    ? new Date(log.GAME_DATE).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                                                    : '—'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-3 py-2.5 text-center text-slate-400 text-xs">
                                        {Math.floor(log.MIN) || '—'}
                                    </td>
                                    <td className={`px-3 py-2.5 text-center font-bold ${getStatColor(log.PTS, 20, 30)}`}>
                                        {log.PTS}
                                    </td>
                                    <td className={`px-3 py-2.5 text-center ${getStatColor(log.REB, 8, 12)}`}>
                                        {log.REB}
                                    </td>
                                    <td className={`px-3 py-2.5 text-center ${getStatColor(log.AST, 6, 10)}`}>
                                        {log.AST}
                                    </td>
                                    <td className="px-3 py-2.5 text-center text-slate-400 text-xs">
                                        <span className={log.STL > 1 ? 'text-amber-400 font-bold' : ''}>{log.STL}</span>
                                        <span className="mx-0.5 opacity-40">/</span>
                                        <span className={log.BLK > 1 ? 'text-blue-500 font-bold' : ''}>{log.BLK}</span>
                                    </td>
                                    <td className={`px-3 py-2.5 text-center text-xs ${log.TOV >= 4 ? 'text-red-400' : 'text-slate-400'}`}>
                                        {log.TOV}
                                    </td>
                                    <td className="px-3 py-2.5 text-center text-xs">
                                        <span className={log.FG_PCT >= 0.5 ? 'text-emerald-500' : 'text-slate-400'}>
                                            {(log.FG_PCT * 100).toFixed(1)}%
                                        </span>
                                    </td>
                                    <td className="px-3 py-2.5 text-center text-xs">
                                        <span className={log.FG3_PCT >= 0.36 ? 'text-cyan-400' : 'text-slate-400'}>
                                            {(log.FG3_PCT * 100).toFixed(1)}%
                                        </span>
                                    </td>
                                    <td className={`px-3 py-2.5 text-center text-xs font-bold ${getPlusMinusColor(log.PLUS_MINUS)}`}>
                                        {log.PLUS_MINUS > 0 ? `+${log.PLUS_MINUS}` : log.PLUS_MINUS}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="text-xs text-slate-600 text-right font-mono">
                {allLogs.length} games available · showing last {logs.length}
            </div>
        </div>
    );
}

export const GameLogsViewer = ({ playerId }: { playerId: string }) => (
    <SectionErrorBoundary fallbackMessage="Live Telemetry Viewer offline">
        <GameLogsViewerContent playerId={playerId} />
    </SectionErrorBoundary>
);
