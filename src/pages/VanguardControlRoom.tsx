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

// ─── AI Analysis Panel ────────────────────────────────────────────────────────
function AnalysisPanel({ fingerprint, onClose }: { fingerprint: string; onClose: () => void }) {
    const [data, setData] = useState<AnalysisResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function fetchAnalysis() {
            try {
                // First try to get cached analysis
                const res = await ApiContract.execute<AnalysisResult>(null, {
                    path: `vanguard/admin/incidents/${fingerprint}/analysis`
                });
                if (!cancelled && res.data) setData(res.data);
            } catch {
                // If no cached analysis, trigger one and wait
                try {
                    await ApiContract.execute(null, {
                        path: `vanguard/admin/incidents/${fingerprint}/analyze`,
                        options: { method: 'POST' }
                    });
                    // Small wait then re-fetch
                    await new Promise(r => setTimeout(r, 2000));
                    const res2 = await ApiContract.execute<AnalysisResult>(null, {
                        path: `vanguard/admin/incidents/${fingerprint}/analysis`
                    });
                    if (!cancelled && res2.data) setData(res2.data);
                    else if (!cancelled) setError('Analysis queued. Check back in a few seconds.');
                } catch (e2: any) {
                    if (!cancelled) setError(e2.message || 'Analysis failed');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        fetchAnalysis();
        return () => { cancelled = true; };
    }, [fingerprint]);

    return (
        <div className="mt-3 rounded-xl border border-purple-500/30 bg-purple-950/20 p-4 sm:p-5 relative">
            <button onClick={onClose} className="absolute top-3 right-3 text-slate-500 hover:text-white transition-colors">
                <X className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 mb-3">
                <Brain className="w-4 h-4 text-purple-400" />
                <span className="text-purple-400 text-xs font-bold tracking-widest uppercase">AI Analysis</span>
                <span className="text-[10px] text-slate-500 font-mono ml-auto pr-6">{fingerprint.slice(0, 12)}…</span>
            </div>

            {loading ? (
                <div className="flex items-center gap-3 text-slate-400 text-sm py-3">
                    <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                    Fetching AI analysis…
                </div>
            ) : error ? (
                <p className="text-amber-400 text-sm">{error}</p>
            ) : data ? (
                <div className="space-y-3 text-sm">
                    {(data.summary || data.analysis) && (
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Summary</p>
                            <p className="text-slate-200 leading-relaxed">{data.summary || data.analysis}</p>
                        </div>
                    )}
                    {data.root_cause && (
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Root Cause</p>
                            <p className="text-slate-300">{data.root_cause}</p>
                        </div>
                    )}
                    {data.recommendation && (
                        <div>
                            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Recommendation</p>
                            <p className="text-emerald-300">{data.recommendation}</p>
                        </div>
                    )}
                    {data.confidence !== undefined && (
                        <div className="flex items-center gap-3 pt-1">
                            <p className="text-[10px] uppercase tracking-wider text-slate-500">Confidence</p>
                            <div className="flex-1 bg-slate-800 rounded-full h-1.5">
                                <div
                                    className="h-1.5 rounded-full bg-purple-500 transition-all duration-700"
                                    style={{ width: `${Math.min(100, (data.confidence ?? 0) * 100)}%` }}
                                />
                            </div>
                            <span className="text-xs text-slate-400">{((data.confidence ?? 0) * 100).toFixed(0)}%</span>
                        </div>
                    )}
                    {data.status && (
                        <p className="text-[10px] text-slate-600 mt-2">Status: {data.status}</p>
                    )}
                    {!data.summary && !data.analysis && !data.root_cause && (
                        <p className="text-slate-500 italic text-sm">Analysis is pending — Gemini AI is processing. Refresh in ~30s.</p>
                    )}
                </div>
            ) : (
                <p className="text-slate-500 text-sm italic">No analysis data available.</p>
            )}
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
    const [showAnalysis, setShowAnalysis] = useState(false);

    const severityStyle = inc.severity === 'RED'
        ? 'bg-red-500/10 border-red-500/30 text-red-400'
        : 'bg-amber-500/10 border-amber-500/30 text-amber-400';

    return (
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
                        onClick={() => setShowAnalysis(v => !v)}
                        className="px-3 sm:px-4 py-2 rounded border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors text-xs font-bold tracking-wide flex items-center gap-1.5"
                    >
                        <Brain className="w-3 h-3" />
                        <span className="hidden sm:inline">AI Analysis</span>
                        <span className="sm:hidden">AI</span>
                        {showAnalysis ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
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

            {/* Expandable AI Analysis Panel */}
            {showAnalysis && (
                <div className="px-4 sm:px-5 pb-4 sm:pb-5">
                    <AnalysisPanel fingerprint={inc.fingerprint} onClose={() => setShowAnalysis(false)} />
                </div>
            )}
        </div>
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
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-white flex items-center gap-3">
                        <Activity className="w-7 h-7 sm:w-8 sm:h-8 text-[#2ad8a0]" />
                        Vanguard Control Room
                    </h1>
                    <p className="text-sm text-slate-400 mt-1 pl-1">System Health & Incident Management • v3.1.2</p>
                </div>
                <button
                    onClick={() => loadData(true)}
                    disabled={refreshing}
                    className="self-start sm:self-auto flex items-center gap-2 px-4 sm:px-5 py-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-all text-sm font-semibold tracking-wide"
                >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Tabs — scrollable on mobile */}
            <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-4 px-4 sm:mx-0 sm:px-0 no-scrollbar">
                {(['HEALTH', 'INCIDENTS', 'ARCHIVES', 'LEARNING'] as const).map(tab => {
                    const isActive = activeTab === tab;
                    let cls = "bg-slate-800/50 text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300";
                    if (isActive) {
                        if (tab === 'HEALTH') cls = "bg-emerald-400/20 text-emerald-400 border-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.3)]";
                        else if (tab === 'INCIDENTS') cls = "bg-amber-400/20 text-amber-400 border-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.2)]";
                        else if (tab === 'LEARNING') cls = "bg-[#2ad8a0] text-slate-900 border-[#2ad8a0] font-bold shadow-[0_0_20px_rgba(42,216,160,0.5)]";
                        else if (tab === 'ARCHIVES') cls = "bg-blue-400/20 text-blue-400 border-blue-400 shadow-[0_0_15px_rgba(96,165,250,0.2)]";
                    }
                    return (
                        <button key={tab} onClick={() => setActiveTab(tab)}
                            className={`flex-shrink-0 px-4 sm:px-5 py-2 sm:py-2.5 rounded-lg border text-xs tracking-widest font-bold transition-all flex items-center gap-2 ${cls}`}>
                            {tab === 'HEALTH' && <Activity className="w-3 h-3" />}
                            {tab === 'INCIDENTS' && <AlertTriangle className="w-3 h-3" />}
                            {tab === 'ARCHIVES' && <FileKey className="w-3 h-3" />}
                            {tab === 'LEARNING' && <Cpu className="w-3 h-3" />}
                            {tab === 'INCIDENTS' ? `INCIDENTS (${activeIncidents.length})` : tab}
                        </button>
                    );
                })}
            </div>

            {/* ── HEALTH TAB ───────────────────────────────────────────────── */}
            {activeTab === 'HEALTH' && (
                <div className="space-y-5 sm:space-y-6">
                    {/* Main card */}
                    <div className="bg-[#111827] border border-slate-700/50 rounded-2xl p-5 sm:p-8 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-6 shadow-lg">
                        <div className="space-y-2">
                            <h2 className="text-lg sm:text-xl font-bold text-white mb-3 sm:mb-4">Overall System Health</h2>
                            {loading ? <Loader2 className="w-10 h-10 animate-spin text-slate-500" /> : (
                                <>
                                    <div className={`text-6xl sm:text-7xl font-bold font-mono tracking-tighter ${scoreColor}`}>
                                        {stats?.health_score?.toFixed(1) ?? '—'}
                                    </div>
                                    <div className="pt-3 sm:pt-4 space-y-1">
                                        <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Status:</span>
                                            <span className={stats && stats.health_score >= 80 ? "text-emerald-500" : "text-red-500"}>
                                                {stats ? (stats.health_score >= 80 ? "OPERATIONAL" : "DEGRADED") : "—"}
                                            </span>
                                        </p>
                                        <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Mode:</span>
                                            <span className="text-amber-500">{stats?.vanguard_mode?.replace('VanguardMode.', '') ?? '—'}</span>
                                        </p>
                                        <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Role:</span>
                                            <span className="text-blue-400">FOLLOWER</span>
                                        </p>
                                    </div>
                                </>
                            )}
                        </div>
                        <div className="self-center sm:mr-8">
                            <DoughnutScore score={stats?.health_score ?? 0} />
                        </div>
                    </div>

                    {/* 2-col mobile / 4-col desktop metric strip */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-6">
                        {[
                            { label: 'Active Incidents', value: loading ? '—' : String(stats?.active_incidents ?? '—'), color: 'text-amber-500' },
                            { label: 'Resolved', value: loading ? '—' : String(stats?.resolved_incidents ?? '—'), color: 'text-emerald-500' },
                            { label: 'Storage Used', value: '0.00 MB', color: 'text-blue-400' },
                            { label: 'Redis', value: '✗', color: 'text-red-500' },
                        ].map(m => (
                            <div key={m.label} className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 sm:p-5">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{m.label}</div>
                                <div className={`text-2xl sm:text-3xl font-bold font-mono ${m.color}`}>{m.value}</div>
                            </div>
                        ))}
                    </div>

                    {/* Subsystems — 2-col mobile / 3-col desktop */}
                    <div className="pt-2 sm:pt-4">
                        <h3 className="text-lg font-bold text-white mb-4">Subsystems</h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-6">
                            <SubSystemCard name="INQUISITOR" active={true} subtitle="Sample: 5%" />
                            <SubSystemCard name="ARCHIVIST" active={true} subtitle="Retention: 7d" />
                            <SubSystemCard name="PROFILER" active={true} subtitle="Model: gemini-2.0-flash" />
                            <SubSystemCard name="SURGEON" active={false} subtitle="Disabled" />
                            <SubSystemCard name="VACCINE" active={true} subtitle="" />
                        </div>
                    </div>
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
