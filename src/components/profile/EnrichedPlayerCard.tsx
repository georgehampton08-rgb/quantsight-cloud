import { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import { TrendingUp, Info, Activity, History, ChevronRight, Loader2 } from 'lucide-react';

interface HustleStats {
    contested_shots: number;
    deflections: number;
    charges_drawn: number;
    loose_balls_recovered: number;
    screen_assists: number;
}

interface LogicTrace {
    primary_factors: Array<{ factor: string; impact: string; is_positive: boolean }>;
    confidence_metrics: {
        model_agreement: number;
        historical_accuracy: number;
        data_freshness: string;
    };
}

interface TraceResponse {
    player_id: string;
    history: any[];
    logic_trace: LogicTrace;
}

interface EnrichedPlayerCardProps {
    playerId: string;
    playerName: string;
}

export default function EnrichedPlayerCard({ playerId, playerName }: EnrichedPlayerCardProps) {
    const [hustle, setHustle] = useState<HustleStats | null>(null);
    const [loadingHustle, setLoadingHustle] = useState(true);
    const [hustleError, setHustleError] = useState(false);

    const [showTrace, setShowTrace] = useState(false);
    const [trace, setTrace] = useState<TraceResponse | null>(null);
    const [loadingTrace, setLoadingTrace] = useState(false);

    useEffect(() => {
        fetchHustle();
    }, [playerId]);

    const fetchHustle = async () => {
        setLoadingHustle(true);
        setHustleError(false);
        try {
            const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/data/player-hustle/${playerId}`);
            if (res.status === 404) {
                setHustleError(true);
            } else if (res.ok) {
                setHustle(await res.json());
            }
        } catch (e) {
            setHustleError(true);
        } finally {
            setLoadingHustle(false);
        }
    };

    const fetchTrace = async () => {
        setLoadingTrace(true);
        setShowTrace(true);
        try {
            const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/aegis/ledger/trace/${playerId}`);
            if (res.ok) {
                setTrace(await res.json());
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoadingTrace(false);
        }
    };

    const StatBox = ({ label, value, loading, error }: { label: string, value: string | number, loading?: boolean, error?: boolean }) => (
        <div className="p-3 rounded-lg bg-slate-900/40 border border-slate-700/50">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">{label}</div>
            {loading ? (
                <div className="flex items-center gap-2 text-slate-600 animate-pulse">
                    <Loader2 size={12} className="animate-spin" />
                    <span className="text-xs">Syncing...</span>
                </div>
            ) : error ? (
                <div className="text-xs text-slate-600 italic">No Data</div>
            ) : (
                <div className="text-sm font-bold text-slate-200">{value}</div>
            )}
        </div>
    );

    return (
        <div className="bg-slate-800/40 backdrop-blur-md rounded-2xl border border-slate-700/50 p-6 shadow-xl relative overflow-hidden group">
            {/* Background Glow */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-financial-accent/5 rounded-full blur-3xl pointer-events-none" />

            <div className="flex justify-between items-start mb-6">
                <div>
                    <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                        <TrendingUp size={20} className="text-financial-accent" />
                        Enriched Analytics
                    </h3>
                    <p className="text-xs text-slate-500">Tracking-layer performance metrics</p>
                </div>

                <button
                    onClick={fetchTrace}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-700 border border-slate-700 hover:border-financial-accent text-xs font-bold text-slate-300 transition-all"
                >
                    Why? <Info size={14} />
                </button>
            </div>

            {/* Hustle Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <StatBox label="Contested Shots" value={hustle?.contested_shots ?? 0} loading={loadingHustle} error={hustleError} />
                <StatBox label="Deflections" value={hustle?.deflections ?? 0} loading={loadingHustle} error={hustleError} />
                <StatBox label="Loose Balls" value={hustle?.loose_balls_recovered ?? 0} loading={loadingHustle} error={hustleError} />
                <StatBox label="Screen Assists" value={hustle?.screen_assists ?? 0} loading={loadingHustle} error={hustleError} />
                <StatBox label="Charges Drawn" value={hustle?.charges_drawn ?? 0} loading={loadingHustle} error={hustleError} />

                {/* Dynamic Update Button for Freshness */}
                <button
                    onClick={fetchHustle}
                    className="flex flex-col items-center justify-center p-3 rounded-lg bg-emerald-500/5 hover:bg-emerald-500/10 border border-emerald-500/20 hover:border-emerald-500/40 transition-all group"
                >
                    <Activity size={16} className="text-emerald-500 mb-1 group-hover:scale-110 transition-transform" />
                    <span className="text-[10px] uppercase font-bold text-emerald-600">Update Tracking</span>
                </button>
            </div>

            {/* Logic Trace Modal Overlay */}
            {showTrace && (
                <div className="absolute inset-0 z-50 bg-slate-900/95 backdrop-blur-xl p-6 flex flex-col animate-in fade-in zoom-in-95 duration-200">
                    <div className="flex justify-between items-center mb-6">
                        <h4 className="font-bold text-slate-100 flex items-center gap-2 text-sm">
                            <History size={18} className="text-financial-accent" />
                            Aegis Logic Trace: {playerName}
                        </h4>
                        <button
                            onClick={() => setShowTrace(false)}
                            className="p-1 hover:bg-white/10 rounded-full transition-colors"
                        >
                            ✕
                        </button>
                    </div>

                    {loadingTrace ? (
                        <div className="flex-1 flex flex-col items-center justify-center gap-4">
                            <Loader2 size={32} className="text-financial-accent animate-spin" />
                            <span className="text-xs text-slate-500 uppercase tracking-widest">Querying Learning Ledger...</span>
                        </div>
                    ) : (
                        <div className="flex-1 space-y-6 overflow-y-auto pr-2 custom-scrollbar">
                            <div className="space-y-3">
                                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">Calculation Breakdown</div>
                                {trace?.logic_trace.primary_factors.map((f, i) => (
                                    <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/10">
                                        <div>
                                            <div className="text-xs font-bold text-slate-200">{f.factor}</div>
                                            <div className="text-[10px] text-slate-500">{f.impact}</div>
                                        </div>
                                        <div className={clsx("text-xs font-bold", f.is_positive ? "text-emerald-400" : "text-rose-400")}>
                                            {f.is_positive ? <ChevronRight size={14} /> : <div className="rotate-90"><ChevronRight size={14} /></div>}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="grid grid-cols-2 gap-3 pt-4 border-t border-white/10">
                                <div className="p-3 rounded-xl bg-slate-800/50">
                                    <div className="text-[10px] text-slate-500 mb-1">Model Agreement</div>
                                    <div className="text-lg font-bold text-financial-accent">{(trace?.logic_trace.confidence_metrics.model_agreement ?? 0 * 100).toFixed(0)}%</div>
                                </div>
                                <div className="p-3 rounded-xl bg-slate-800/50">
                                    <div className="text-[10px] text-slate-500 mb-1">Historical Hit Rate</div>
                                    <div className="text-lg font-bold text-emerald-400">{(trace?.logic_trace.confidence_metrics.historical_accuracy ?? 0 * 100).toFixed(0)}%</div>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="mt-4 pt-4 border-t border-white/5 text-[10px] text-slate-600 text-center italic">
                        Ledger ID: AX-90210 | Verified via Sovereign-Router
                    </div>
                </div>
            )}
        </div>
    );
}
