import React, { useEffect, useState, useCallback } from 'react';
import { Activity, Clock, Crosshair, BarChart2, ShieldAlert } from 'lucide-react';
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
    FG_PCT: number;
    FG3_PCT: number;
    FT_PCT: number;
    PLUS_MINUS: number;
}

export function GameLogsViewerContent({ playerId }: { playerId: string }) {
    const [loading, setLoading] = useState(true);
    const [logs, setLogs] = useState<GameLog[]>([]);
    const [error, setError] = useState<string | null>(null);

    const loadLogs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await ApiContract.execute<{ logs: GameLog[] }>(null, {
                path: `player-data/logs/${playerId}`
            });
            if (res.data?.logs) {
                setLogs(res.data.logs);
            } else {
                setError('No recent game logs found.');
            }
        } catch (e: any) {
            setError(e.message || 'Failed to fetch game logs.');
        } finally {
            setLoading(false);
        }
    }, [playerId]);

    useEffect(() => {
        if (playerId && playerId !== '0') {
            loadLogs();
        }
    }, [loadLogs, playerId]);

    if (!playerId || playerId === '0') {
        return null;
    }

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-12 space-y-4 border border-slate-800 rounded-xl bg-slate-900/30">
                <Activity className="w-8 h-8 text-slate-500 animate-spin" />
                <div className="text-sm text-slate-400 font-mono tracking-widest">PULLING GAME LOGS...</div>
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

    if (logs.length === 0) {
        return (
            <div className="p-12 text-center text-slate-500 border border-slate-800 rounded-xl bg-slate-900/30">
                Data pipeline active. Waiting for player activity to populate.
            </div>
        );
    }

    // Helper functions for coloring stats
    const getStatColor = (val: number, good: number, elite: number) => {
        if (val >= elite) return 'text-emerald-400 font-bold';
        if (val >= good) return 'text-emerald-500/80';
        return 'text-slate-300';
    };

    const getPlusMinusColor = (val: number) => {
        if (val > 0) return 'text-emerald-400';
        if (val < 0) return 'text-red-400';
        return 'text-slate-500';
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-indigo-400" />
                    Recent Live Telemetry
                </h3>
                <span className="text-xs text-slate-500 font-mono">Last {logs.length} Games</span>
            </div>

            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl overflow-hidden shadow-2xl">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left whitespace-nowrap">
                        <thead className="text-xs uppercase bg-slate-800/80 text-slate-400 border-b border-slate-700/50">
                            <tr>
                                <th className="px-4 py-3 font-semibold tracking-wider sticky left-0 z-20 bg-slate-800/95 backdrop-blur-sm shadow-[4px_0_8px_rgba(0,0,0,0.1)]">Date/Matchup</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">MIN</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">PTS</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">REB</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">AST</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">STL/BLK</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">FG%</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">+/-</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-mono">
                            {logs.map((log) => (
                                <tr key={log.GAME_ID} className="bg-slate-900/40 hover:bg-slate-800/40 transition-colors group">
                                    <td className="px-4 py-3 sticky left-0 z-10 bg-slate-900/90 group-hover:bg-slate-800/90 backdrop-blur-sm shadow-[4px_0_8px_rgba(0,0,0,0.1)] transition-colors border-r border-slate-800/30">
                                        <div className="flex flex-col">
                                            <span className="text-slate-300 font-sans font-bold text-xs">{log.MATCHUP}</span>
                                            <span className="text-[10px] text-slate-500 tracking-widest">{new Date(log.GAME_DATE).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3 text-center text-slate-400">
                                        {Math.floor(log.MIN)}
                                    </td>
                                    <td className={`px-4 py-3 text-center text-base ${getStatColor(log.PTS, 20, 30)}`}>
                                        {log.PTS}
                                    </td>
                                    <td className={`px-4 py-3 text-center ${getStatColor(log.REB, 8, 12)}`}>
                                        {log.REB}
                                    </td>
                                    <td className={`px-4 py-3 text-center ${getStatColor(log.AST, 6, 10)}`}>
                                        {log.AST}
                                    </td>
                                    <td className="px-4 py-3 text-center text-slate-400">
                                        <span className={log.STL > 1 ? 'text-amber-400 font-bold' : ''}>{log.STL}</span>
                                        <span className="mx-1 opacity-50">/</span>
                                        <span className={log.BLK > 1 ? 'text-blue-400 font-bold' : ''}>{log.BLK}</span>
                                    </td>
                                    <td className="px-4 py-3 text-center text-slate-400">
                                        <div className="flex items-center justify-center gap-1">
                                            <Crosshair className="w-3 h-3 opacity-50" />
                                            <span className={log.FG_PCT >= 0.5 ? 'text-emerald-400' : ''}>
                                                {(log.FG_PCT * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    </td>
                                    <td className={`px-4 py-3 text-center font-bold ${getPlusMinusColor(log.PLUS_MINUS)}`}>
                                        {log.PLUS_MINUS > 0 ? `+${log.PLUS_MINUS}` : log.PLUS_MINUS}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

export const GameLogsViewer = ({ playerId }: { playerId: string }) => (
    <SectionErrorBoundary fallbackMessage="Live Telemetry Viewer offline">
        <GameLogsViewerContent playerId={playerId} />
    </SectionErrorBoundary>
);
