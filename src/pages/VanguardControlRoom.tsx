import React, { useEffect, useState, useCallback } from 'react';
import {
    Activity, ShieldCheck, AlertTriangle, RefreshCw, Cpu,
    CheckCircle2, Loader2, FileKey, X, Zap, Brain, ChevronDown,
    ChevronUp, Clock, Hash
} from 'lucide-react';
import { ApiContract } from '../api/client';
import { VanguardLearningExport } from '../components/vanguard/VanguardLearningExport';
import { VanguardArchivesViewer } from '../components/vanguard/VanguardArchivesViewer';
import { VaccinePanel } from '../components/vanguard/VaccinePanel';
import { normalizeVanguardIncidentList } from '../api/normalizers';
import { Modal } from '../components/common/Modal';

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
    labels?: Record<string, string | number | boolean>;
    ai_analysis?: Record<string, unknown>;
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

interface VaccineRecommendation {
    feasible: boolean;
    target_file?: string | null;
    target_function?: string;
    target_line_hint?: number;
    change_description?: string;
    patch_risk?: 'low' | 'medium' | 'high';
    skip_reason?: string;
}

interface AnalysisResult {
    fingerprint: string;
    analysis?: string;
    summary?: string;
    root_cause?: string;
    recommendation?: string;
    recommended_fix?: string | string[];
    impact?: string;
    confidence?: number;
    status?: string;
    timeline_analysis?: string;
    ready_reasoning?: string;
    ready_to_resolve?: boolean;
    cached?: boolean;
    generated_at?: string;
    code_references?: string[];
    // New enriched fields from Prompt v2.0
    error_message_decoded?: string;
    middleware_insight?: string;
    vaccine_recommendation?: VaccineRecommendation;
}

// ─── Doughnut ─────────────────────────────────────────────────────────────────
function DoughnutScore({ score = 0 }: { score: number }) {
    const C = 251.2;
    const offset = C - (score / 100) * C;
    const color = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#f43f5e';
    return (
        <div className="relative w-28 h-28 sm:w-48 sm:h-48 flex items-center justify-center">
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
    incident,
    onClose,
    onResolve,
    resolving
}: {
    incident: Incident;
    onClose: () => void;
    onResolve: () => void;
    resolving: boolean;
}) {
    const fingerprint = incident.fingerprint;
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
    const summary = data?.summary || data?.impact || data?.analysis || '';
    const rootCause = data?.root_cause || '';
    const timelineAnalysis = data?.timeline_analysis || '';
    const readyReasoning = data?.ready_reasoning || '';
    const errorDecoded = data?.error_message_decoded || '';
    const middlewareInsight = data?.middleware_insight || '';
    const vaccineRec = data?.vaccine_recommendation || null;

    // Check for "recommended_fix" array, or fallback
    let recommendationList: string[] = [];
    if (Array.isArray(data?.recommended_fix)) {
        recommendationList = data.recommended_fix;
    } else if (typeof data?.recommended_fix === 'string') {
        recommendationList = (data.recommended_fix as string).split('\n');
    } else if (data?.recommendation) {
        recommendationList = data.recommendation.split('\n');
    }

    const confidence = data?.confidence;
    // Use typed code_references from the response model directly
    const codeRefs: string[] = data?.code_references || [];

    return (
        <Modal
            isOpen={true}
            onClose={onClose}
            title={
                <div className="flex-1 min-w-0">
                    <h2 className="text-white font-bold text-base">AI Analysis</h2>
                    <p className="text-slate-500 font-mono text-xs mt-0.5 truncate">{fingerprint.slice(0, 24)}...</p>
                </div>
            }
            icon={<Brain className="w-5 h-5 text-purple-400" />}
            maxWidth="4xl"
            bodyClassName="px-0 sm:px-0 py-0 flex flex-col h-full bg-slate-900"
        >
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
                        {/* Incident Meta/Context Metrics Strip */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 p-4 shadow-inner">
                            <div>
                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1 shadow-sm">Occurrences</div>
                                <div className="text-xl font-mono font-black text-amber-400 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">
                                    {incident.occurrence_count}
                                </div>
                            </div>
                            <div className="col-span-1 sm:col-span-2">
                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1 shadow-sm">Timeline</div>
                                <div className="text-xs font-mono font-bold text-slate-300"><span className="text-slate-500 uppercase tracking-widest text-[9px] mr-2">First</span> {incident.first_seen ? new Date(incident.first_seen).toLocaleString() : '—'}</div>
                                <div className="text-xs font-mono font-bold text-slate-300"><span className="text-slate-500 uppercase tracking-widest text-[9px] mr-2">Last</span> {incident.last_seen ? new Date(incident.last_seen).toLocaleString() : '—'}</div>
                            </div>
                            {/* Middleware tags — now fully typed via incident.labels */}
                            <div className="col-span-2 sm:col-span-1 border-t border-slate-700/50 sm:border-0 pt-2 sm:pt-0">
                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1.5 shadow-sm">Middleware Tags</div>
                                <div className="flex flex-wrap gap-1.5">
                                    {Object.entries(incident.labels || {}).slice(0, 3).map(([k, v]) => (
                                        <span key={k} className="text-[9px] px-2 py-0.5 rounded-full bg-slate-800 text-cyan-400 border border-cyan-500/30 whitespace-nowrap font-bold tracking-wider">
                                            {String(v)}
                                        </span>
                                    ))}
                                    {(!incident.labels || Object.keys(incident.labels).length === 0) && (
                                        <span className="text-xs text-slate-600 font-mono">None</span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Impact */}
                        {summary && (
                            <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 p-4">
                                <div className="flex items-center gap-2 mb-2.5">
                                    <AlertTriangle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                                    <span className="text-emerald-400 font-bold text-sm">Impact</span>
                                </div>
                                <p className="text-slate-300 text-sm leading-relaxed">{summary}</p>
                            </div>
                        )}

                        {/* Error Decoded */}
                        {errorDecoded && (
                            <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 p-4">
                                <div className="flex items-center gap-2 mb-2.5">
                                    <Cpu className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                                    <span className="text-cyan-400 font-bold text-sm">Error Decoded</span>
                                </div>
                                <p className="text-slate-300 text-sm leading-relaxed">{errorDecoded}</p>
                            </div>
                        )}

                        {/* Middleware Insight */}
                        {middlewareInsight && (
                            <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 p-4">
                                <div className="flex items-center gap-2 mb-2.5">
                                    <Activity className="w-4 h-4 text-violet-400 flex-shrink-0" />
                                    <span className="text-violet-400 font-bold text-sm">Middleware Insight</span>
                                </div>
                                <p className="text-slate-300 text-sm leading-relaxed">{middlewareInsight}</p>
                            </div>
                        )}

                        {/* Timeline Analysis from AI */}
                        {timelineAnalysis && (
                            <div className="rounded-xl bg-slate-800/40 border border-slate-700/40 p-4">
                                <div className="flex items-center gap-2 mb-2.5">
                                    <Clock className="w-4 h-4 text-blue-400 flex-shrink-0" />
                                    <span className="text-blue-400 font-bold text-sm">Timeline Analysis</span>
                                </div>
                                <p className="text-slate-300 text-sm leading-relaxed">{timelineAnalysis}</p>
                                {readyReasoning && (
                                    <div className="mt-2 pt-2 border-t border-slate-700/30">
                                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full mr-2 ${data?.ready_to_resolve ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                                            {data?.ready_to_resolve ? '✓ Ready to Resolve' : '⌛ Not Yet Ready'}
                                        </span>
                                        <span className="text-slate-500 text-xs">{readyReasoning}</span>
                                    </div>
                                )}
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
                        {recommendationList.length > 0 && (
                            <div className="rounded-2xl bg-white/5 backdrop-blur-md border border-emerald-500/20 p-5 shadow-lg relative overflow-hidden group">
                                <div className="absolute inset-0 bg-gradient-to-tr from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                                <div className="flex items-center gap-3 mb-3 relative z-10">
                                    <CheckCircle2 className="w-5 h-5 text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)] flex-shrink-0" />
                                    <span className="text-white font-black text-sm tracking-wide">Recommended Fixes</span>
                                </div>
                                <ul className="space-y-2 relative z-10">
                                    {recommendationList.map((rec, i) => (
                                        <li key={i} className="text-slate-300 text-sm leading-relaxed flex items-start gap-2">
                                            <span className="text-emerald-500/50 text-xs mt-0.5 font-mono select-none">›</span>
                                            <span className={rec.startsWith('IMMEDIATE:') ? 'text-amber-100 font-medium' : ''}>{rec}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* ── Vaccine Recommendation ── */}
                        {vaccineRec && (
                            <div className={`rounded-2xl border p-5 relative overflow-hidden ${vaccineRec.feasible
                                ? 'bg-emerald-950/30 border-emerald-500/30 shadow-[0_0_30px_rgba(16,185,129,0.1)]'
                                : 'bg-slate-800/40 border-slate-700/40'
                                }`}>
                                <div className="flex items-center gap-3 mb-4">
                                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${vaccineRec.feasible ? 'bg-emerald-500/20 border border-emerald-500/30' : 'bg-slate-700/50 border border-slate-600/30'
                                        }`}>
                                        <ShieldCheck className={`w-4 h-4 ${vaccineRec.feasible ? 'text-emerald-400' : 'text-slate-500'}`} />
                                    </div>
                                    <div className="flex-1">
                                        <span className={`font-black text-sm tracking-wide ${vaccineRec.feasible ? 'text-emerald-300' : 'text-slate-400'}`}>
                                            💉 Vaccine Recommendation
                                        </span>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${vaccineRec.feasible ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-700 text-slate-500'
                                                }`}>
                                                {vaccineRec.feasible ? '✓ FEASIBLE' : '✗ NOT FEASIBLE'}
                                            </span>
                                            {vaccineRec.patch_risk && vaccineRec.feasible && (
                                                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${vaccineRec.patch_risk === 'low' ? 'bg-emerald-500/10 text-emerald-500' :
                                                    vaccineRec.patch_risk === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                                                        'bg-red-500/20 text-red-400'
                                                    }`}>
                                                    {vaccineRec.patch_risk.toUpperCase()} RISK
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {vaccineRec.feasible ? (
                                    <div className="space-y-3">
                                        {vaccineRec.target_file && (
                                            <div>
                                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">Target File</div>
                                                <code className="text-xs text-emerald-300 bg-black/30 px-2 py-1 rounded font-mono block">
                                                    {vaccineRec.target_file}
                                                    {vaccineRec.target_function ? ` :: ${vaccineRec.target_function}` : ''}
                                                    {vaccineRec.target_line_hint ? ` (line ~${vaccineRec.target_line_hint})` : ''}
                                                </code>
                                            </div>
                                        )}
                                        {vaccineRec.change_description && (
                                            <div>
                                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">Proposed Change</div>
                                                <p className="text-slate-200 text-sm leading-relaxed bg-black/20 rounded-lg px-3 py-2">
                                                    {vaccineRec.change_description}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <p className="text-slate-500 text-sm italic">
                                        {vaccineRec.skip_reason || 'Automatic patching not possible for this incident type.'}
                                    </p>
                                )}
                            </div>
                        )}

                        {/* Confidence bar */}
                        {confidence !== undefined && (
                            <div className="flex items-center gap-3 px-1 mt-4">
                                <span className="text-xs font-bold text-slate-400 w-20 flex-shrink-0">Confidence</span>
                                <div className="flex-1 bg-slate-800/50 rounded-full h-2 overflow-hidden border border-slate-700/50">
                                    <div
                                        className="h-full rounded-full bg-gradient-to-r from-purple-600 to-purple-400 transition-all duration-700 shadow-[0_0_12px_rgba(168,85,247,0.6)]"
                                        style={{ width: `${Math.min(100, (confidence ?? 0) > 1 ? (confidence ?? 0) : ((confidence ?? 0) * 100))}%` }}
                                    />
                                </div>
                                <span className="text-xs font-black text-purple-300 w-10 text-right tracking-wider">
                                    {((confidence ?? 0) > 1 ? (confidence ?? 0) : ((confidence ?? 0) * 100)).toFixed(0)}%
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
                        {!summary && !rootCause && recommendationList.length === 0 && (
                            <div className="text-center py-10">
                                <Brain className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                                <p className="text-slate-500 text-sm italic">Analysis is pending — Gemini AI is processing. Click Regenerate to check.</p>
                            </div>
                        )}
                    </>
                ) : null}
            </div>

            {/* ── Footer ── */}
            <div className="flex items-center gap-3 px-6 py-4 border-t border-slate-700/50 flex-shrink-0 bg-slate-900/80">
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
        </Modal>
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
            <div
                onClick={onToggle}
                className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl shadow-xl transition-all hover:bg-white/10 group relative overflow-hidden cursor-pointer"
            >
                <div className="absolute inset-0 bg-gradient-to-r from-amber-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
                <div className="p-4 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6 relative z-10">
                    <div className="flex items-start sm:items-center gap-4 flex-1 min-w-0">
                        {/* Checkbox */}
                        <input
                            type="checkbox"
                            checked={selected}
                            onChange={(e) => { e.stopPropagation(); onToggle(); }}
                            className="w-5 h-5 bg-black/50 border-white/20 rounded text-amber-500 flex-shrink-0 cursor-pointer focus:ring-amber-500/50 mt-1 sm:mt-0"
                        />

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                            <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-1.5">
                                <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-amber-500 drop-shadow-[0_0_8px_rgba(245,158,11,0.6)] flex-shrink-0" />
                                <span className="text-white font-black text-sm sm:text-base tracking-wide drop-shadow-md break-all">{inc.error_type}</span>
                                <span className={`text-[10px] px-2 py-0.5 rounded font-black tracking-widest border shadow-sm ${severityStyle}`}>
                                    {inc.severity?.toUpperCase()}
                                </span>
                            </div>
                            <div className="text-slate-400 font-mono text-xs sm:text-sm ml-6 sm:ml-8 truncate">{inc.endpoint}</div>
                            <div className="text-slate-500 text-[10px] sm:text-xs ml-6 sm:ml-8 mt-2 flex flex-wrap gap-3 font-semibold">
                                <span className="flex items-center gap-1.5"><Hash className="w-3.5 h-3.5" /> {inc.occurrence_count} Occurrences</span>
                                <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> {new Date(inc.last_seen).toLocaleString()}</span>
                            </div>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 sm:gap-3 ml-9 sm:ml-0 flex-shrink-0 mt-1 sm:mt-0">
                        <button
                            onClick={(e) => { e.stopPropagation(); setShowAnalysisModal(true); }}
                            className="px-4 py-2.5 rounded-xl border border-purple-500/40 text-purple-400 shadow-[0_0_15px_rgba(168,85,247,0.15)] hover:bg-purple-500/20 hover:text-purple-300 hover:border-purple-500/60 transition-all text-xs font-black tracking-widest flex items-center gap-2 backdrop-blur-sm"
                        >
                            <Brain className="w-4 h-4" />
                            <span className="hidden sm:inline">AI Analysis</span>
                            <span className="sm:hidden">AI</span>
                        </button>
                        <button
                            onClick={(e) => { e.stopPropagation(); onResolve(); }}
                            disabled={resolving}
                            className="px-4 py-2.5 rounded-xl border border-emerald-500/40 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.15)] hover:bg-emerald-500/20 hover:text-emerald-300 hover:border-emerald-500/60 disabled:opacity-50 transition-all text-xs font-black tracking-widest flex items-center gap-2 backdrop-blur-sm"
                        >
                            {resolving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                            Resolve
                        </button>
                    </div>
                </div>
            </div>

            {/* AI Analysis Modal — Portal-like fixed overlay */}
            {showAnalysisModal && (
                <AnalysisModal
                    incident={inc}
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
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-4 sm:p-5 flex justify-between items-start shadow-xl relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <div>
                <h4 className="text-white font-black text-xs sm:text-sm tracking-widest uppercase">{name}</h4>
                {subtitle && <p className="text-xs text-slate-400 font-medium mt-1.5">{subtitle}</p>}
            </div>
            <div className={`w-6 h-6 rounded-full flex justify-center items-center border flex-shrink-0 relative z-10 ${active ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10 shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'border-slate-600/50 text-slate-500 bg-slate-700/20'}`}>
                {active ? <CheckCircle2 className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
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
    const [sortOrder, setSortOrder] = useState<'NEWEST' | 'OLDEST' | 'IMPACT'>('IMPACT');

    // Pagination state
    const [incidentsPage, setIncidentsPage] = useState(1);
    const incidentsPerPage = 40;

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
                const normalized = normalizeVanguardIncidentList(incRes.data);
                setIncidents(normalized);
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

    const activeIncidents = incidents.filter(i => i.status === 'active').sort((a, b) => {
        if (sortOrder === 'NEWEST') return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
        if (sortOrder === 'OLDEST') return new Date(a.last_seen).getTime() - new Date(b.last_seen).getTime();
        if (sortOrder === 'IMPACT') {
            const getSeverityScore = (s: string) => s === 'RED' ? 10000 : s === 'YELLOW' ? 100 : 0;
            const scoreA = getSeverityScore(a.severity) + a.occurrence_count;
            const scoreB = getSeverityScore(b.severity) + b.occurrence_count;
            if (scoreA !== scoreB) return scoreB - scoreA;
            // fallback to newest
            return new Date(b.last_seen).getTime() - new Date(a.last_seen).getTime();
        }
        return 0;
    });

    const scoreColor = stats
        ? stats.health_score >= 80 ? 'text-emerald-400' : stats.health_score >= 50 ? 'text-amber-400' : 'text-red-500'
        : 'text-slate-500';

    return (
        <div className="flex flex-col h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-[#060b13] to-black font-sans items-center">
            <div className="w-full max-w-7xl flex flex-col h-full min-h-0">
                <div className="flex-1 overflow-y-auto p-4 sm:p-8 space-y-5 sm:space-y-8 min-h-0 pb-12">
                    {/* Toast */}
                    {toast && (
                        <div className={`fixed top-4 right-4 z-50 px-4 sm:px-5 py-3 rounded-xl border text-sm font-semibold shadow-lg backdrop-blur-md transition-all max-w-[90vw] ${toast.ok ? 'bg-emerald-900/80 border-emerald-500/50 text-emerald-300' : 'bg-red-900/80 border-red-500/50 text-red-300'}`}>
                            {toast.msg}
                        </div>
                    )}

                    {/* Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4 flex-shrink-0">
                        <div>
                            <h1 className="text-xl sm:text-3xl font-extrabold text-white flex items-center gap-2 sm:gap-3">
                                <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-emerald-500/30 to-cyan-500/20 border border-emerald-500/30 flex items-center justify-center backdrop-blur-sm">
                                    <Activity className="w-5 h-5 sm:w-6 sm:h-6 text-emerald-400" />
                                </div>
                                Vanguard Control Room
                            </h1>
                            <p className="text-xs sm:text-sm text-slate-500 mt-1 pl-0.5">System Health & Incident Management • v3.2.0</p>
                        </div>
                        <button
                            onClick={() => loadData(true)}
                            disabled={refreshing}
                            className="self-start sm:self-auto flex items-center gap-2 px-4 py-2 sm:py-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-all text-xs sm:text-sm font-semibold tracking-wide backdrop-blur-sm"
                        >
                            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                            Refresh
                        </button>
                    </div>

                    {/* Tabs — full wording, glass style, web-first adaptive */}
                    <div className="flex gap-2.5 overflow-x-auto no-scrollbar pb-2 -mx-4 px-4 sm:mx-0 sm:px-0 flex-shrink-0">
                        {(['HEALTH', 'INCIDENTS', 'ARCHIVES', 'LEARNING'] as const).map(tab => {
                            const isActive = activeTab === tab;
                            const baseCls = "flex-shrink-0 sm:flex-1 px-4 sm:px-5 py-3 rounded-2xl text-xs sm:text-sm tracking-widest font-black transition-all duration-300 flex items-center justify-center gap-2.5 border backdrop-blur-xl group relative overflow-hidden";

                            let colorCls = "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10 hover:text-white shadow-lg";
                            if (isActive) {
                                if (tab === 'HEALTH') colorCls = "bg-emerald-500/15 text-emerald-400 border-emerald-500/50 shadow-[0_0_30px_rgba(16,185,129,0.25)]";
                                else if (tab === 'INCIDENTS') colorCls = "bg-amber-500/15 text-amber-400 border-amber-500/50 shadow-[0_0_25px_rgba(245,158,11,0.2)]";
                                else if (tab === 'ARCHIVES') colorCls = "bg-blue-500/15 text-blue-400 border-blue-500/50 shadow-[0_0_25px_rgba(59,130,246,0.2)]";
                                else if (tab === 'LEARNING') colorCls = "bg-cyan-500/15 text-cyan-400 border-cyan-500/50 shadow-[0_0_30px_rgba(6,182,212,0.25)]";
                            }
                            return (
                                <button key={tab} onClick={() => setActiveTab(tab)}
                                    className={`${baseCls} ${colorCls}`}>
                                    {/* Inner glow effect for active tab */}
                                    {isActive && <div className="absolute inset-0 bg-gradient-to-t from-white/5 to-transparent pointer-events-none" />}

                                    {tab === 'HEALTH' && <Activity className="w-4 h-4" />}
                                    {tab === 'INCIDENTS' && <AlertTriangle className="w-4 h-4" />}
                                    {tab === 'ARCHIVES' && <FileKey className="w-4 h-4" />}
                                    {tab === 'LEARNING' && <Cpu className="w-4 h-4" />}
                                    <span className="relative z-10 drop-shadow-md">{tab === 'INCIDENTS' ? `INCIDENTS (${activeIncidents.length})` : tab}</span>
                                </button>
                            );
                        })}
                    </div>

                    {/* ── HEALTH TAB ───────────────────────────────────────────────── */}
                    {activeTab === 'HEALTH' && (
                        <div className="space-y-5 sm:space-y-6">
                            {/* Main card */}
                            <div className="bg-[#0b1120]/60 backdrop-blur-xl border border-white/10 rounded-3xl p-6 sm:p-10 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-6 shadow-[0_15px_50px_rgba(0,0,0,0.5)] relative overflow-hidden">
                                {/* Dramatic glow hidden behind the card */}
                                <div className="absolute top-0 right-1/4 w-96 h-96 bg-emerald-500/10 blur-[100px] rounded-full pointer-events-none" />
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
                                <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
                                    <h3 className="text-sm font-black text-white mb-6 tracking-widest uppercase opacity-80">Score Breakdown</h3>
                                    <div className="space-y-5">
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
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
                                {[
                                    { label: 'Active Incidents', value: loading ? '—' : String(stats?.active_incidents ?? '—'), color: 'text-amber-400 drop-shadow-[0_0_10px_rgba(251,191,36,0.5)]' },
                                    { label: 'Resolved', value: loading ? '—' : String(stats?.resolved_incidents ?? '—'), color: 'text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]' },
                                    { label: 'Storage Used', value: loading ? '—' : `${stats?.storage_mb?.toFixed(2) ?? '0.00'} MB`, color: 'text-blue-400 drop-shadow-[0_0_10px_rgba(96,165,250,0.5)]' },
                                    { label: 'Redis', value: stats?.subsystem_health?.redis ? '✓' : '✗', color: stats?.subsystem_health?.redis ? 'text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]' : 'text-red-500 drop-shadow-[0_0_10px_rgba(239,68,68,0.5)]' },
                                ].map(m => (
                                    <div key={m.label} className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-5 sm:p-6 shadow-xl relative overflow-hidden group">
                                        <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                                        <div className="text-xs text-slate-400 font-bold uppercase tracking-widest mb-3">{m.label}</div>
                                        <div className={`text-3xl sm:text-4xl font-black font-mono ${m.color}`}>{m.value}</div>
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
                                <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
                                    <h3 className="text-sm font-black text-white mb-6 tracking-widest uppercase flex items-center gap-3 opacity-80">
                                        <AlertTriangle className="w-4 h-4 text-amber-500 drop-shadow-[0_0_8px_rgba(245,158,11,0.6)]" />
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
                                    <select
                                        className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-1.5 focus:ring-1 focus:ring-amber-500/50 focus:outline-none"
                                        value={sortOrder}
                                        onChange={(e) => {
                                            setSortOrder(e.target.value as any);
                                            setIncidentsPage(1); // Reset to page 1 on sort change
                                        }}
                                    >
                                        <option value="IMPACT">Highest Impact</option>
                                        <option value="NEWEST">Newest First</option>
                                        <option value="OLDEST">Oldest First</option>
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
                                <>
                                    {activeIncidents.slice((incidentsPage - 1) * incidentsPerPage, incidentsPage * incidentsPerPage).map(inc => (
                                        <IncidentCard
                                            key={inc.fingerprint}
                                            inc={inc}
                                            selected={selected.has(inc.fingerprint)}
                                            onToggle={() => toggleSelect(inc.fingerprint)}
                                            onResolve={() => resolveIncident(inc.fingerprint)}
                                            resolving={!!resolving[inc.fingerprint]}
                                        />
                                    ))}
                                    {activeIncidents.length > incidentsPerPage && (
                                        <div className="flex items-center justify-center gap-2 mt-6 pb-4">
                                            <button
                                                onClick={() => setIncidentsPage(p => Math.max(1, p - 1))}
                                                disabled={incidentsPage === 1}
                                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 transition-colors text-sm font-semibold"
                                            >
                                                Previous
                                            </button>
                                            <span className="text-slate-400 text-sm font-medium px-4">
                                                Page {incidentsPage} of {Math.ceil(activeIncidents.length / incidentsPerPage)}
                                            </span>
                                            <button
                                                onClick={() => setIncidentsPage(p => Math.min(Math.ceil(activeIncidents.length / incidentsPerPage), p + 1))}
                                                disabled={incidentsPage === Math.ceil(activeIncidents.length / incidentsPerPage)}
                                                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg disabled:opacity-50 transition-colors text-sm font-semibold"
                                            >
                                                Next
                                            </button>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}

                    {/* ── ARCHIVES TAB ──────────────────────────────────────────────── */}
                    {activeTab === 'ARCHIVES' && (
                        <div className="space-y-6">
                            <VanguardArchivesViewer />
                            <VaccinePanel />
                        </div>
                    )}

                    {/* ── LEARNING TAB ──────────────────────────────────────────────── */}
                    {activeTab === 'LEARNING' && (
                        <div className="space-y-5 sm:space-y-6">
                            {loading ? (
                                <div className="flex justify-center p-12"><Loader2 className="animate-spin w-8 h-8 text-slate-500" /></div>
                            ) : (
                                <>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6">
                                        {[
                                            { label: 'Total Resolutions', value: learning?.total_resolutions ?? '—', color: 'text-white' },
                                            { label: 'Verified', value: learning?.verified_resolutions ?? '—', color: 'text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]' },
                                            { label: 'Pending', value: learning?.pending_verification ?? '—', color: 'text-amber-400 drop-shadow-[0_0_10px_rgba(251,191,36,0.5)]' },
                                            { label: 'Success Patterns', value: learning?.successful_patterns ?? '—', color: 'text-blue-400 drop-shadow-[0_0_10px_rgba(96,165,250,0.5)]' },
                                        ].map(m => (
                                            <div key={m.label} className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-5 sm:p-6 shadow-xl text-center">
                                                <div className="text-xs text-slate-400 font-bold uppercase tracking-widest mb-3">{m.label}</div>
                                                <div className={`text-3xl sm:text-4xl font-black ${m.color}`}>{String(m.value)}</div>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-6 sm:p-8 min-h-[300px] shadow-2xl">
                                        <h3 className="text-white font-black text-lg mb-6 flex items-center gap-3 opacity-90">
                                            <Brain className="w-5 h-5 text-cyan-400 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]" />
                                            Top Success Patterns
                                        </h3>
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
                                    <VanguardLearningExport />
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
