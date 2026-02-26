import React, { useEffect, useState, useCallback } from 'react';
import { History, Swords, Info, Activity, ShieldAlert } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

interface H2HRecord {
    MATCHUP: string;
    GAME_DATE: string;
    PTS: number;
    REB: number;
    AST: number;
    WL: string;
    PLUS_MINUS: number;
}

interface H2HData {
    records: H2HRecord[];
    summary: {
        total_games: number;
        wins: number;
        losses: number;
        avg_pts: number;
        avg_reb: number;
        avg_ast: number;
    };
}

export function H2HHistoryPanelContent({ playerId, opponentId }: { playerId: string, opponentId: string }) {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<H2HData | null>(null);
    const [error, setError] = useState<string | null>(null);

    const loadH2H = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await ApiContract.execute<H2HData>(null, {
                path: `player-data/h2h/${playerId}?opponent_id=${opponentId}`
            });
            setData(res.data);
        } catch (e: any) {
            setError(e.message || 'Failed to fetch H2H history.');
        } finally {
            setLoading(false);
        }
    }, [playerId, opponentId]);

    useEffect(() => {
        if (playerId && opponentId && playerId !== '0') {
            loadH2H();
        }
    }, [loadH2H, playerId, opponentId]);

    if (!playerId || playerId === '0' || !opponentId) {
        return null;
    }

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-12 space-y-4 border border-slate-800 rounded-xl bg-slate-900/30">
                <Activity className="w-8 h-8 text-slate-500 animate-spin" />
                <div className="text-sm text-slate-400 font-mono tracking-widest">LOADING HISTORICAL VECTORS...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-6 rounded-xl border border-red-900/30 bg-red-900/10 flex items-start gap-4">
                <ShieldAlert className="w-6 h-6 text-red-500 flex-shrink-0 mt-1" />
                <div>
                    <h3 className="text-red-400 font-bold mb-1">H2H Retrieval Failed</h3>
                    <p className="text-slate-400 text-sm">{error}</p>
                    <button onClick={loadH2H} className="mt-3 px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded transition-colors">
                        RETRY
                    </button>
                </div>
            </div>
        );
    }

    if (!data || data.records.length === 0) {
        return (
            <div className="p-8 text-center border border-slate-700/50 rounded-xl bg-slate-800/20 text-slate-400">
                <Info className="w-8 h-8 mx-auto mb-3 opacity-50" />
                <p>No historical matchups found against this opponent.</p>
            </div>
        );
    }

    const { summary, records } = data;
    const winRate = summary.total_games > 0 ? (summary.wins / summary.total_games) * 100 : 0;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <Swords className="w-5 h-5 text-amber-500" />
                    Head-to-Head History
                </h3>
            </div>

            {/* Averages summary strip */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">Win Rate</div>
                    <div className={`text-2xl font-black ${winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {winRate.toFixed(0)}%
                    </div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{summary.wins}W - {summary.losses}L</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">AVG PTS</div>
                    <div className="text-2xl font-black text-white">{summary.avg_pts.toFixed(1)}</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">AVG REB</div>
                    <div className="text-2xl font-black text-white">{summary.avg_reb.toFixed(1)}</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">AVG AST</div>
                    <div className="text-2xl font-black text-white">{summary.avg_ast.toFixed(1)}</div>
                </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl overflow-hidden shadow-xl">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="text-xs uppercase bg-slate-800/80 text-slate-400 border-b border-slate-700/50">
                            <tr>
                                <th className="px-4 py-3 font-semibold tracking-wider">Date</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">Result</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">PTS</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">REB</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">AST</th>
                                <th className="px-4 py-3 font-semibold tracking-wider text-center">+/-</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-mono">
                            {records.map((rec, i) => (
                                <tr key={i} className="bg-slate-900/40 hover:bg-slate-800/40 transition-colors">
                                    <td className="px-4 py-3">
                                        <div className="text-slate-300">
                                            {new Date(rec.GAME_DATE).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                                        </div>
                                        <div className="text-[10px] text-slate-500">{rec.MATCHUP}</div>
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${rec.WL === 'W' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                                            {rec.WL}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-center text-white font-bold">{rec.PTS}</td>
                                    <td className="px-4 py-3 text-center text-slate-300">{rec.REB}</td>
                                    <td className="px-4 py-3 text-center text-slate-300">{rec.AST}</td>
                                    <td className={`px-4 py-3 text-center font-bold ${rec.PLUS_MINUS > 0 ? 'text-emerald-400' : rec.PLUS_MINUS < 0 ? 'text-red-400' : 'text-slate-500'}`}>
                                        {rec.PLUS_MINUS > 0 ? `+${rec.PLUS_MINUS}` : rec.PLUS_MINUS}
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

export const H2HHistoryPanel = ({ playerId, opponentId }: { playerId: string, opponentId: string }) => (
    <SectionErrorBoundary fallbackMessage="H2H History Viewer offline">
        <H2HHistoryPanelContent playerId={playerId} opponentId={opponentId} />
    </SectionErrorBoundary>
);
