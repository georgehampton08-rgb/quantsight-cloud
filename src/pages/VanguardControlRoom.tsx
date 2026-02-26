import React, { useEffect, useState, useCallback } from 'react';
import {
    Activity, ShieldCheck, AlertTriangle, RefreshCw, Cpu,
    CheckCircle2, Loader2, FileKey, X, Zap, Brain, ChevronDown,
    ChevronUp, Clock, Hash
} from 'lucide-react';
import { ApiContract } from '../api/client';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Incident {
    fingerprint: string;
    error_type: string;
    endpoint: string;
    severity: string;
    occurrence_count: number;
    first_seen: string;
    last_seen: string;
    status: string;
    ai_analysis?: string;
}

interface VanguardStats {
    active_incidents: number;
    resolved_incidents: number;
    health_score: number;
    health_breakdown?: {
        incident_score: number;
        subsystem_score: number;
        endpoint_score: number;
    };
    subsystem_health?: Record<string, boolean>;
    hot_endpoints?: { endpoint: string; active_count: number }[];
    storage_mb?: number;
    storage_cap_mb?: number;
    vanguard_mode: string;
}

interface LearningStatus {
    total_resolutions: number;
    verified_resolutions: number;
    pending_verification: number;
    successful_patterns: number;
    patterns: any[];
}

interface AnalysisResult {
    fingerprint: string;
    analysis?: string;
    summary?: string;
    root_cause?: string;
    recommendation?: string;
    confidence?: number;
    status?: string;
}

// ─── Doughnut ─────────────────────────────────────────────────────────────────
function DoughnutScore({ score = 0 }: { score: number }) {
    const C = 251.2;
    const offset = C - (score / 100) * C;
    const color = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#f43f5e';
    return (
        <div className="relative w-36 h-36 sm:w-48 sm:h-48 flex items-center justify-center">
            <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" strokeWidth="8" />
                <circle cx="50" cy="50" r="40" fill="none" stroke={color} strokeWidth="8"
                    strokeDasharray={C} strokeDashoffset={offset}
                    strokeLinecap="round" className="transition-all duration-1000 ease-out" />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center rotate-0">
                <span className={`text-2xl sm:text-3xl font-black font-mono`} style={{ color }}>
                    {score.toFixed(0)}
                </span>
            </div>
        </div>
    );
}

// ─── AI Analysis Modal ────────────────────────────────────────────────────────
function AnalysisModal({
    fingerprint,
    onClose,
    onResolve,
    resolving
}: {
    fingerprint: string;
    onClose: () => void;
    onResolve: () => void;
    resolving: boolean;
}) {
    const [data, setData] = useState<AnalysisResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [regenerating, setRegenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [codeRefOpen, setCodeRefOpen] = useState(false);

    const fetchAnalysis = async (force = false) => {
        setLoading(true);
        setError(null);
        try {
            if (force) {
                // Trigger fresh analysis
                await ApiContract.execute(null, {
                    path: `vanguard/admin/incidents/${fingerprint}/analyze`,
                    options: { method: 'POST' }
                });
                await new Promise(r => setTimeout(r, 2500));
            }
            const res = await ApiContract.execute<AnalysisResult>(null, {
                path: `vanguard/admin/incidents/${fingerprint}/analysis`
            });
            if (res.data) setData(res.data);
            else setError('No analysis returned yet.');
        } catch {
            // If GET analysis fails, auto-trigger analysis
            if (!force) {
                try {
                    await ApiContract.execute(null, {
                        path: `vanguard/admin/incidents/${fingerprint}/analyze`,
                        options: { method: 'POST' }
                    });
                    await new Promise(r => setTimeout(r, 2500));
                    const res2 = await ApiContract.execute<AnalysisResult>(null, {
                        path: `vanguard/admin/incidents/${fingerprint}/analysis`
                    });
                    if (res2.data) setData(res2.data);
                    else setError('Analysis queued. It may take ~30s — click Regenerate to check.');
                } catch (e2: any) {
                    setError(e2.message || 'Analysis failed — backend may be processing.');
                }
            } else {
                setError('Regeneration failed. Try again in a moment.');
            }
        } finally {
            setLoading(false);
            setRegenerating(false);
        }
    };

    useEffect(() => { fetchAnalysis(); }, [fingerprint]);

    const handleRegenerate = async () => {
        setRegenerating(true);
        await fetchAnalysis(true);
    };

    // Parse structured fields from analysis string if backend returns flat text
    const summary = data?.summary || data?.analysis || '';
    const rootCause = data?.root_cause || '';
    const recommendation = data?.recommendation || '';
    const confidence = data?.confidence;
    const codeRefs = (data as any)?.code_references || (data as any)?.references || [];

    // Close on backdrop click
    const handleBackdrop = (e: React.MouseEvent<HTMLDivElement>) => {
        if (e.target === e.currentTarget) onClose();
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
            onClick={handleBackdrop}
        >
            <div className="relative w-full max-w-2xl bg-[#0f172a] border border-slate-700/60 rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">

                {/* ── Header ── */}
                <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-700/50 flex-shrink-0">
                    <div className="w-9 h-9 rounded-xl bg-purple-500/20 border border-purple-500/30 flex items-center justify-center flex-shrink-0">
                        <Brain className="w-5 h-5 text-purple-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <h2 className="text-white font-bold text-base">AI Analysis</h2>
                        <p className="text-slate-500 font-mono text-xs mt-0.5 truncate">{fingerprint.slice(0, 24)}...</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-500 hover:text-white transition-colors p-1 rounded-lg hover:bg-slate-700/50"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* ── Scrollable Body ── */}
                <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-16 gap-4">
                            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
                            <p className="text-slate-400 text-sm">
                                {regenerating ? 'Regenerating analysis…' : 'Fetching AI analysis…'}
                            </p>
                        </div>
                    ) : error ? (
                        <div className="rounded-xl bg-amber-950/30 border border-amber-500/30 p-4">
                            <p className="text-amber-400 text-sm">{error}</p>
                        </div>
                    ) : data ? (
                        <>
                            {/* Summary / Impact */}
                            {summary && (
                                <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 p-4">
                                    <div className="flex items-center gap-2 mb-2.5">
                                        <AlertTriangle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                                        <span className="text-emerald-400 font-bold text-sm">Impact</span>
                                    </div>
                                    <p className="text-slate-300 text-sm leading-relaxed">{summary}</p>
                                </div>
                            )}

                            {/* Root Cause */}
                            {rootCause && (
                                <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 p-4">
                                    <div className="flex items-center gap-2 mb-2.5">
                                        <Activity className="w-4 h-4 text-amber-400 flex-shrink-0" />
                                        <span className="text-amber-400 font-bold text-sm">Root Cause</span>
                                    </div>
                                    <p className="text-slate-300 text-sm leading-relaxed">{rootCause}</p>
                                </div>
                            )}

                            {/* Recommended Fix */}
                            {recommendation && (
                                <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 p-4">
                                    <div className="flex items-center gap-2 mb-2.5">
                                        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                                        <span className="text-emerald-400 font-bold text-sm">Recommended Fix</span>
                                    </div>
                                    <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">{recommendation}</p>
                                </div>
                            )}

                            {/* Confidence bar */}
                            {confidence !== undefined && (
                                <div className="flex items-center gap-3 px-1">
                                    <span className="text-xs text-slate-500 w-20 flex-shrink-0">Confidence</span>
                                    <div className="flex-1 bg-slate-800 rounded-full h-1.5">
                                        <div
                                            className="h-1.5 rounded-full bg-purple-500 transition-all duration-700"
                                            style={{ width: `${Math.min(100, (confidence ?? 0) * 100)}%` }}
                                        />
                                    </div>
                                    <span className="text-xs text-slate-400 w-8 text-right">
                                        {((confidence ?? 0) * 100).toFixed(0)}%
                                    </span>
                                </div>
                            )}

                            {/* Code References — collapsible */}
                            <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 overflow-hidden">
                                <button
                                    onClick={() => setCodeRefOpen(v => !v)}
                                    className="w-full flex items-center gap-2 px-4 py-3 hover:bg-slate-700/30 transition-colors"
                                >
                                    <FileKey className="w-4 h-4 text-purple-400 flex-shrink-0" />
                                    <span className="text-purple-400 font-bold text-sm flex-1 text-left">Code References</span>
                                    {codeRefOpen ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                                </button>
                                {codeRefOpen && (
                                    <div className="px-4 pb-4 border-t border-slate-700/30">
                                        {codeRefs.length > 0 ? (
                                            codeRefs.map((ref: any, i: number) => (
                                                <div key={i} className="mt-3 font-mono text-xs text-slate-400 bg-slate-900/50 rounded-lg p-3">
                                                    {typeof ref === 'string' ? ref : JSON.stringify(ref, null, 2)}
                                                </div>
                                            ))
                                        ) : (
                                            <p className="text-slate-600 text-xs mt-3 italic">No code references attached to this incident.</p>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* No structured data fallback */}
                            {!summary && !rootCause && !recommendation && (
                                <div className="text-center py-10">
                                    <Brain className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                                    <p className="text-slate-500 text-sm italic">Analysis is pending — Gemini AI is processing. Click Regenerate to check.</p>
                                </div>
                            )}
                        </>
                    ) : null}
                </div>

                {/* ── Footer ── */}
                <div className="flex items-center gap-3 px-6 py-4 border-t border-slate-700/50 flex-shrink-0">
                    <button
                        onClick={handleRegenerate}
                        disabled={loading}
                        className="flex items-center gap-2 text-slate-400 hover:text-white text-sm font-semibold transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading && regenerating ? 'animate-spin' : ''}`} />
                        Regenerate
                    </button>
                    <div className="flex-1" />
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-semibold text-slate-300 hover:text-white bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors"
                    >
                        Close
                    </button>
                    <button
                        onClick={() => { onResolve(); onClose(); }}
                        disabled={resolving}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-bold bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 text-white rounded-lg transition-colors"
                    >
                        {resolving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                        Mark Resolved
                    </button>
                </div>
            </div>
        </div>
    );
}



// ─── Incident Card ────────────────────────────────────────────────────────────
function IncidentCard({
    inc,
    selected,
    onToggle,
    onResolve,
    resolving
}: {
    inc: Incident;
    selected: boolean;
    onToggle: () => void;
    onResolve: () => void;
    resolving: boolean;
}) {
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);

    const severityStyle = inc.severity === 'RED'
        ? 'bg-red-500/10 border-red-500/30 text-red-400'
        : 'bg-amber-500/10 border-amber-500/30 text-amber-400';

    return (
        <>
            <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl transition-colors hover:border-slate-600">
                <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
                    {/* Checkbox */}
                    <input
                        type="checkbox"
                        checked={selected}
                        onChange={onToggle}
                        className="w-4 h-4 bg-slate-900 border-slate-700 rounded text-amber-500 flex-shrink-0"
                    />

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                            <span className="text-white font-bold text-sm sm:text-base">{inc.error_type}</span>
                            <span className={`text-[10px] px-2 py-0.5 rounded font-black tracking-widest border ${severityStyle}`}>
                                {inc.severity?.toUpperCase()}
                            </span>
                        </div>
                        <div className="text-slate-400 font-mono text-xs sm:text-sm ml-6 truncate">{inc.endpoint}</div>
                        <div className="text-slate-500 text-xs ml-6 mt-1.5 flex flex-wrap gap-3">
                            <span className="flex items-center gap-1"><Hash className="w-3 h-3" /> {inc.occurrence_count}</span>
                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(inc.last_seen).toLocaleString()}</span>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 ml-6 sm:ml-0 flex-shrink-0">
                        <button
                            onClick={() => setShowAnalysisModal(true)}
                            className="px-3 sm:px-4 py-2 rounded border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors text-xs font-bold tracking-wide flex items-center gap-1.5"
                        >
                            <Brain className="w-3 h-3" />
                            <span className="hidden sm:inline">AI Analysis</span>
                            <span className="sm:hidden">AI</span>
                        </button>
                        <button
                            onClick={onResolve}
                            disabled={resolving}
                            className="px-3 sm:px-4 py-2 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-50 transition-colors text-xs font-bold tracking-wide flex items-center gap-1.5"
                        >
                            {resolving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                            Resolve
                        </button>
                    </div>
                </div>
            </div>

            {/* AI Analysis Modal — Portal-like fixed overlay */}
            {showAnalysisModal && (
                <AnalysisModal
                    fingerprint={inc.fingerprint}
                    onClose={() => setShowAnalysisModal(false)}
                    onResolve={onResolve}
                    resolving={resolving}
                />
            )}
        </>
    );
}

// ─── Subsystem Card ───────────────────────────────────────────────────────────
function SubSystemCard({ name, active, subtitle }: { name: string; active: boolean; subtitle: string }) {
    return (
        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-3 sm:p-4 flex justify-between items-start">
            <div>
                <h4 className="text-white font-bold text-xs sm:text-sm tracking-widest">{name}</h4>
                {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
            </div>
            <div className={`w-5 h-5 rounded-full flex justify-center items-center border flex-shrink-0 ${active ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-slate-600/50 text-slate-500 bg-slate-700/20'}`}>
                {active ? <CheckCircle2 className="w-3 h-3" /> : <X className="w-3 h-3" />}
            </div>
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function VanguardControlRoom() {
    const [activeTab, setActiveTab] = useState<'HEALTH' | 'INCIDENTS' | 'ARCHIVES' | 'LEARNING'>('HEALTH');
    const [incidents, setIncidents] = useState<Incident[]>([]);
    const [stats, setStats] = useState<VanguardStats | null>(null);
    const [learning, setLearning] = useState<LearningStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [resolving, setResolving] = useState<Record<string, boolean>>({});
    const [analyzingAll, setAnalyzingAll] = useState(false);
    const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

    const showToast = (msg: string, ok: boolean) => {
        setToast({ msg, ok });
        setTimeout(() => setToast(null), 3500);
    };

    const loadData = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        else setRefreshing(true);
        try {
            const [incRes, statsRes, learnRes] = await Promise.all([
                ApiContract.execute<{ incidents: Incident[] }>(null, {
                    path: 'vanguard/admin/incidents',
                    options: { method: 'GET' }
                }),
                ApiContract.execute<VanguardStats>(null, {
                    path: 'vanguard/admin/stats'
                }),
                ApiContract.execute<LearningStatus>(null, {
                    path: 'vanguard/admin/learning/status'
                }),
            ]);

            if (incRes.data) {
                const raw = incRes.data as any;
                setIncidents(Array.isArray(raw) ? raw : (raw.incidents || []));
            }
            if (statsRes.data) setStats(statsRes.data);
            if (learnRes.data) setLearning(learnRes.data);
        } catch (e: any) {
            console.error('[VanguardControlRoom] loadData failed:', e);
            showToast(`Data load failed: ${e.message}`, false);
        }
        setLoading(false);
        setRefreshing(false);
    }, []);

    useEffect(() => { loadData(); }, [loadData]);

    const toggleSelect = (fp: string) => {
        setSelected(prev => {
            const next = new Set(prev);
            next.has(fp) ? next.delete(fp) : next.add(fp);
            return next;
        });
    };

    const selectAll = () => {
        const active = incidents.filter(i => i.status === 'active');
        if (selected.size === active.length && active.length > 0) {
            setSelected(new Set());
        } else {
            setSelected(new Set(active.map(i => i.fingerprint)));
        }
    };

    const resolveIncident = async (fingerprint: string) => {
        setResolving(prev => ({ ...prev, [fingerprint]: true }));
        try {
            await ApiContract.execute(null, {
                path: `vanguard/admin/incidents/${fingerprint}/resolve`,
                options: {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ approved: true, resolution_notes: 'Resolved via Control Room' })
                }
            });
            showToast('Incident resolved', true);
            await loadData(true);
        } catch (e: any) {
            showToast(`Resolve failed: ${e.message}`, false);
        }
        setResolving(prev => ({ ...prev, [fingerprint]: false }));
    };

    const analyzeAll = async () => {
        setAnalyzingAll(true);
        try {
            await ApiContract.execute(null, {
                path: 'vanguard/admin/incidents/analyze-all',
                options: { method: 'POST' }
            });
            showToast('Bulk AI analysis queued for all active incidents', true);
        } catch (e: any) {
            showToast(`Analyze All failed: ${e.message}`, false);
        }
        setAnalyzingAll(false);
    };

    const activeIncidents = incidents.filter(i => i.status === 'active');
    const scoreColor = stats
        ? stats.health_score >= 80 ? 'text-emerald-400' : stats.health_score >= 50 ? 'text-amber-400' : 'text-red-500'
        : 'text-slate-500';

    return (
        <div className="p-4 sm:p-8 h-full overflow-y-auto space-y-6 sm:space-y-8 bg-slate-900 font-sans">

            {/* Toast */}
            {toast && (
                <div className={`fixed top-4 right-4 z-50 px-4 sm:px-5 py-3 rounded-xl border text-sm font-semibold shadow-lg transition-all max-w-[90vw] ${toast.ok ? 'bg-emerald-900/90 border-emerald-500/50 text-emerald-300' : 'bg-red-900/90 border-red-500/50 text-red-300'}`}>
                    {toast.msg}
                </div>
            )}

            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
                <div>
                    <h1 className="text-xl sm:text-3xl font-extrabold text-white flex items-center gap-2 sm:gap-3">
                        <Activity className="w-6 h-6 sm:w-8 sm:h-8 text-financial-accent" />
                        Vanguard Control Room
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 mt-0.5 sm:mt-1 pl-0.5">System Health & Incident Management • v3.2.0</p>
                </div>
                <button
                    onClick={() => loadData(true)}
                    disabled={refreshing}
                    className="self-start sm:self-auto flex items-center gap-2 px-4 py-2 sm:py-2.5 rounded-lg bg-financial-accent/10 border border-financial-accent/40 text-financial-accent hover:bg-financial-accent/20 disabled:opacity-50 transition-all text-xs sm:text-sm font-semibold tracking-wide"
                >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Tabs — adaptive: scrollable snap on mobile, equal-width on desktop */}
            <div className="relative">
                <div className="flex gap-1.5 sm:gap-2 overflow-x-auto snap-x snap-mandatory no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0 pb-1">
                    {(['HEALTH', 'INCIDENTS', 'ARCHIVES', 'LEARNING'] as const).map(tab => {
                        const isActive = activeTab === tab;
                        const baseClasses = "snap-start flex-shrink-0 sm:flex-1 px-3 sm:px-5 py-2.5 rounded-xl text-xs tracking-widest font-bold transition-all flex items-center justify-center gap-1.5 border";

                        let activeCls = "bg-slate-800/50 text-slate-500 border-slate-700/40 hover:bg-slate-800 hover:text-slate-300";
                        if (isActive) {
                            if (tab === 'HEALTH') activeCls = "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 shadow-[0_0_20px_rgba(0,229,160,0.15)]";
                            else if (tab === 'INCIDENTS') activeCls = "bg-amber-500/15 text-amber-400 border-amber-500/30 shadow-[0_0_15px_rgba(245,158,11,0.15)]";
                            else if (tab === 'ARCHIVES') activeCls = "bg-blue-500/15 text-blue-400 border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]";
                            else if (tab === 'LEARNING') activeCls = "bg-financial-accent/15 text-financial-accent border-financial-accent/30 shadow-[0_0_20px_rgba(0,229,160,0.2)]";
                        }
                        return (
                            <button key={tab} onClick={() => setActiveTab(tab)}
                                className={`${baseClasses} ${activeCls}`}>
                                {tab === 'HEALTH' && <Activity className="w-3.5 h-3.5" />}
                                {tab === 'INCIDENTS' && <AlertTriangle className="w-3.5 h-3.5" />}
                                {tab === 'ARCHIVES' && <FileKey className="w-3.5 h-3.5" />}
                                {tab === 'LEARNING' && <Cpu className="w-3.5 h-3.5" />}
                                <span className="hidden xs:inline">{tab === 'INCIDENTS' ? `INCIDENTS (${activeIncidents.length})` : tab}</span>
                                <span className="xs:hidden">{tab === 'INCIDENTS' ? `${activeIncidents.length}` : tab.slice(0, 4)}</span>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* ── HEALTH TAB ───────────────────────────────────────────────── */}
            {activeTab === 'HEALTH' && (
                <div className="space-y-5 sm:space-y-6">
                    {/* Main card */}
                    <div className="bg-[#111827] border border-slate-700/50 rounded-2xl p-5 sm:p-8 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-6 shadow-lg">
                        <div className="space-y-2 flex-1">
                            <h2 className="text-lg sm:text-xl font-bold text-white mb-3 sm:mb-4">Overall System Health</h2>
                            {loading ? <Loader2 className="w-10 h-10 animate-spin text-slate-500" /> : (
                                <>
                                    <div className={`text-6xl sm:text-7xl font-bold font-mono tracking-tighter ${scoreColor}`}>
                                        {stats?.health_score?.toFixed(1) ?? '—'}
                                    </div>
                                    <div className="pt-3 sm:pt-4 space-y-1">
                                        <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Status:</span>
                                            <span className={stats && stats.health_score >= 80 ? "text-emerald-500" : stats && stats.health_score >= 50 ? "text-amber-500" : "text-red-500"}>
                                                {stats ? (stats.health_score >= 80 ? "OPERATIONAL" : stats.health_score >= 50 ? "DEGRADED" : "CRITICAL") : "—"}
                                            </span>
                                        </p>
                                        <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Mode:</span>
                                            <span className="text-amber-500">{stats?.vanguard_mode?.replace('VanguardMode.', '') ?? '—'}</span>
                                        </p>
                                    </div>
                                </>
                            )}
                        </div>
                        <div className="self-center sm:mr-8">
                            <DoughnutScore score={stats?.health_score ?? 0} />
                        </div>
                    </div>

                    {/* Score Breakdown Bars */}
                    {stats?.health_breakdown && (
                        <div className="bg-slate-800/30 border border-slate-700/50 rounded-2xl p-5 sm:p-6">
                            <h3 className="text-sm font-bold text-white mb-4 tracking-wider uppercase">Score Breakdown</h3>
                            <div className="space-y-4">
                                {[
                                    { label: 'Incidents', score: stats.health_breakdown.incident_score, weight: '40%', color: 'bg-amber-500' },
                                    { label: 'Subsystems', score: stats.health_breakdown.subsystem_score, weight: '35%', color: 'bg-emerald-500' },
                                    { label: 'Endpoints', score: stats.health_breakdown.endpoint_score, weight: '25%', color: 'bg-blue-500' },
                                ].map(b => (
                                    <div key={b.label}>
                                        <div className="flex justify-between items-baseline mb-1.5">
                                            <span className="text-sm font-semibold text-slate-300">{b.label} <span className="text-slate-600 text-xs">({b.weight})</span></span>
                                            <span className={`text-sm font-bold font-mono ${b.score >= 80 ? 'text-emerald-400' : b.score >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
                                                {b.score.toFixed(1)}
                                            </span>
                                        </div>
                                        <div className="w-full bg-slate-700/40 rounded-full h-2">
                                            <div
                                                className={`h-2 rounded-full transition-all duration-700 ${b.color}`}
                                                style={{ width: `${Math.min(100, b.score)}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Metric Strip — real data */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-6">
                        {[
                            { label: 'Active Incidents', value: loading ? '—' : String(stats?.active_incidents ?? '—'), color: 'text-amber-500' },
                            { label: 'Resolved', value: loading ? '—' : String(stats?.resolved_incidents ?? '—'), color: 'text-emerald-500' },
                            { label: 'Storage Used', value: loading ? '—' : `${stats?.storage_mb?.toFixed(2) ?? '0.00'} MB`, color: 'text-blue-400' },
                            { label: 'Redis', value: stats?.subsystem_health?.redis ? '✓' : '✗', color: stats?.subsystem_health?.redis ? 'text-emerald-500' : 'text-red-500' },
                        ].map(m => (
                            <div key={m.label} className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 sm:p-5">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{m.label}</div>
                                <div className={`text-2xl sm:text-3xl font-bold font-mono ${m.color}`}>{m.value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Subsystems — driven by API */}
                    <div className="pt-2 sm:pt-4">
                        <h3 className="text-lg font-bold text-white mb-4">Subsystems</h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-6">
                            {stats?.subsystem_health ? (
                                Object.entries(stats.subsystem_health)
                                    .filter(([k]) => k !== 'redis')  // Redis shown in metric strip
                                    .map(([name, healthy]) => (
                                        <SubSystemCard
                                            key={name}
                                            name={name.toUpperCase()}
                                            active={healthy}
                                            subtitle={healthy ? 'Online' : 'Offline'}
                                        />
                                    ))
                            ) : (
                                <>
                                    <SubSystemCard name="INQUISITOR" active={true} subtitle="Sample: 5%" />
                                    <SubSystemCard name="ARCHIVIST" active={true} subtitle="Online" />
                                    <SubSystemCard name="PROFILER" active={true} subtitle="Online" />
                                    <SubSystemCard name="SURGEON" active={false} subtitle="Disabled" />
                                    <SubSystemCard name="VACCINE" active={true} subtitle="Online" />
                                </>
                            )}
                        </div>
                    </div>

                    {/* Hot Endpoints */}
                    {stats?.hot_endpoints && stats.hot_endpoints.length > 0 && (
                        <div className="bg-slate-800/30 border border-slate-700/50 rounded-2xl p-5 sm:p-6">
                            <h3 className="text-sm font-bold text-white mb-4 tracking-wider uppercase flex items-center gap-2">
                                <AlertTriangle className="w-4 h-4 text-amber-400" />
                                Hot Endpoints
                            </h3>
                            <div className="space-y-3">
                                {stats.hot_endpoints.map((ep, i) => {
                                    const maxCount = stats.hot_endpoints![0].active_count;
                                    const pct = maxCount > 0 ? (ep.active_count / maxCount) * 100 : 0;
                                    return (
                                        <div key={i}>
                                            <div className="flex justify-between items-baseline mb-1">
                                                <span className="text-sm font-mono text-slate-300 truncate mr-4">{ep.endpoint}</span>
                                                <span className="text-xs font-bold text-amber-400 flex-shrink-0">{ep.active_count} hits</span>
                                            </div>
                                            <div className="w-full bg-slate-700/30 rounded-full h-1.5">
                                                <div className="h-1.5 rounded-full bg-amber-500/70 transition-all duration-500" style={{ width: `${pct}%` }} />
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ── INCIDENTS TAB ─────────────────────────────────────────────── */}
            {activeTab === 'INCIDENTS' && (
                <div className="space-y-4">
                    {/* Toolbar */}
                    <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-700/50">
                        <div className="flex items-center gap-3 flex-wrap">
                            <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
                                <input
                                    type="checkbox"
                                    checked={selected.size === activeIncidents.length && activeIncidents.length > 0}
                                    onChange={selectAll}
                                    className="w-4 h-4 bg-slate-800 border-slate-600 rounded text-amber-500"
                                />
                                Select All
                            </label>
                            <select className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-1.5">
                                <option>Newest First</option>
                                <option>Oldest First</option>
                                <option>Highest Impact</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-3 flex-wrap">
                            <button
                                onClick={analyzeAll}
                                disabled={analyzingAll}
                                className="flex items-center gap-2 px-5 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg transition-colors font-bold text-sm shadow-[0_0_15px_rgba(147,51,234,0.3)]"
                            >
                                {analyzingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <Cpu className="w-4 h-4" />}
                                Analyze All
                            </button>
                            <span className="text-sm text-slate-400">{activeIncidents.length} active</span>
                        </div>
                    </div>

                    {loading ? (
                        <div className="flex justify-center p-12"><Loader2 className="animate-spin w-8 h-8 text-slate-500" /></div>
                    ) : activeIncidents.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                            <ShieldCheck className="w-12 h-12 mb-4 text-emerald-700" />
                            <p className="font-semibold">No active incidents</p>
                        </div>
                    ) : (
                        activeIncidents.map(inc => (
                            <IncidentCard
                                key={inc.fingerprint}
                                inc={inc}
                                selected={selected.has(inc.fingerprint)}
                                onToggle={() => toggleSelect(inc.fingerprint)}
                                onResolve={() => resolveIncident(inc.fingerprint)}
                                resolving={!!resolving[inc.fingerprint]}
                            />
                        ))
                    )}
                </div>
            )}

            {/* ── ARCHIVES TAB ──────────────────────────────────────────────── */}
            {activeTab === 'ARCHIVES' && (
                <div className="flex flex-col items-center justify-center py-20 sm:py-32 rounded-2xl bg-slate-800/30 border border-slate-700/50">
                    <FileKey className="w-14 h-14 sm:w-16 sm:h-16 text-slate-500 mb-6" />
                    <h2 className="text-white font-bold text-lg sm:text-xl mb-2">Archive Management</h2>
                    <p className="text-slate-400 text-sm">Weekly archives · 7 day retention</p>
                </div>
            )}

            {/* ── LEARNING TAB ──────────────────────────────────────────────── */}
            {activeTab === 'LEARNING' && (
                <div className="space-y-5 sm:space-y-6">
                    {loading ? (
                        <div className="flex justify-center p-12"><Loader2 className="animate-spin w-8 h-8 text-slate-500" /></div>
                    ) : (
                        <>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-6">
                                {[
                                    { label: 'Total Resolutions', value: learning?.total_resolutions ?? '—', color: 'text-white' },
                                    { label: 'Verified', value: learning?.verified_resolutions ?? '—', color: 'text-emerald-500' },
                                    { label: 'Pending', value: learning?.pending_verification ?? '—', color: 'text-amber-500' },
                                    { label: 'Success Patterns', value: learning?.successful_patterns ?? '—', color: 'text-blue-400' },
                                ].map(m => (
                                    <div key={m.label} className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-4 sm:p-5">
                                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{m.label}</div>
                                        <div className={`text-2xl sm:text-3xl font-bold ${m.color}`}>{String(m.value)}</div>
                                    </div>
                                ))}
                            </div>

                            <div className="bg-slate-800/30 border border-slate-700/50 rounded-2xl p-5 sm:p-6 min-h-[300px]">
                                <h3 className="text-white font-bold text-lg mb-4">Top Success Patterns</h3>
                                {learning?.patterns && learning.patterns.length > 0 ? (
                                    learning.patterns.map((p: any, i) => (
                                        <div key={i} className="border-b border-slate-700/40 py-3 text-sm text-slate-300">{JSON.stringify(p)}</div>
                                    ))
                                ) : (
                                    <div className="flex flex-col items-center justify-center py-12 text-slate-600">
                                        <Brain className="w-10 h-10 mb-3" />
                                        <p className="text-sm">No patterns yet — patterns emerge after resolutions are verified</p>
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
