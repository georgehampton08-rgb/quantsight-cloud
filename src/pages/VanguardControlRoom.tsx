/**
 * Vanguard Control Room
 * =====================
 * Admin hub for the QuantSight Digital Immune System.
 * Incidents · AI Analysis (with Regenerate) · Resolve · Health
 */
import React, { useEffect, useState, useCallback } from 'react'
import {
    ShieldCheck, AlertTriangle, XCircle, RefreshCw, Cpu,
    ChevronDown, ChevronUp, CheckCircle2, Loader2, Zap, RotateCcw
} from 'lucide-react'

const BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app'

// ─── Types ────────────────────────────────────────────────────────────────────
interface Incident {
    fingerprint: string
    error_type: string
    endpoint: string
    severity: string
    occurrence_count: number
    first_seen: string
    last_seen: string
    status: string
    ai_analysis?: AnalysisResult
}

interface AnalysisResult {
    root_cause: string
    impact: string
    recommended_fix: string[]
    ready_to_resolve: boolean
    ready_reasoning: string
    confidence: number
    generated_at: string
    cached: boolean
    model_id?: string
}

interface VanguardStats {
    active_incidents: number
    resolved_incidents: number
    health_score: number
    vanguard_mode: string
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function severityColor(s: string) {
    switch (s?.toUpperCase()) {
        case 'RED': return 'text-red-400 border-red-500/40 bg-red-500/10'
        case 'ORANGE': return 'text-orange-400 border-orange-500/40 bg-orange-500/10'
        case 'YELLOW': return 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10'
        default: return 'text-slate-400 border-slate-600/40 bg-slate-700/20'
    }
}

function SeverityBadge({ s }: { s: string }) {
    return (
        <span className={`inline-block text-xs font-bold px-2 py-0.5 rounded border ${severityColor(s)}`}>
            {s?.toUpperCase() || 'UNKNOWN'}
        </span>
    )
}

function ConfidenceDial({ pct }: { pct: number }) {
    const color = pct >= 75 ? '#22d3ee' : pct >= 50 ? '#f59e0b' : '#f87171'
    return (
        <div className="flex items-center gap-2">
            <div className="relative w-10 h-10">
                <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                    <circle cx="18" cy="18" r="15" fill="none" stroke="#334155" strokeWidth="4" />
                    <circle
                        cx="18" cy="18" r="15" fill="none" stroke={color} strokeWidth="4"
                        strokeDasharray={`${(pct / 100) * 94.2} 94.2`}
                        strokeLinecap="round"
                    />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-xs font-bold" style={{ color }}>
                    {pct}
                </span>
            </div>
            <span className="text-xs text-slate-400">confidence</span>
        </div>
    )
}

// ─── AI Analysis Modal ────────────────────────────────────────────────────────
function AnalysisModal({
    incident,
    onClose,
}: {
    incident: Incident
    onClose: () => void
}) {
    const [analysis, setAnalysis] = useState<AnalysisResult | null>(
        incident.ai_analysis || null
    )
    const [loading, setLoading] = useState(!incident.ai_analysis)
    const [error, setError] = useState<string | null>(null)
    const [resolving, setResolving] = useState(false)
    const [resolved, setResolved] = useState(false)

    const fetchAnalysis = useCallback(async (forceRegenerate = false) => {
        setLoading(true)
        setError(null)
        try {
            let res: Response
            if (forceRegenerate) {
                // POST endpoint forces fresh generation — no cache hit
                res = await fetch(
                    `${BASE}/vanguard/admin/incidents/${incident.fingerprint}/analyze`,
                    { method: 'POST' }
                )
            } else {
                res = await fetch(
                    `${BASE}/vanguard/admin/incidents/${incident.fingerprint}/analysis`
                )
            }
            if (!res.ok) {
                const body = await res.json().catch(() => ({}))
                throw new Error(body?.detail || `HTTP ${res.status}`)
            }
            const data = await res.json()
            setAnalysis(data)
        } catch (e: any) {
            setError(e?.message || 'Analysis failed')
        } finally {
            setLoading(false)
        }
    }, [incident.fingerprint])

    useEffect(() => {
        if (!analysis) fetchAnalysis(false)
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    const handleResolve = async () => {
        setResolving(true)
        try {
            const res = await fetch(
                `${BASE}/vanguard/admin/incidents/${incident.fingerprint}/resolve`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ approved: true, resolution_notes: 'Resolved via Control Room' }),
                }
            )
            if (res.ok) setResolved(true)
        } catch { /* ignore */ }
        setResolving(false)
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl">
                {/* Header */}
                <div className="sticky top-0 z-10 flex items-center justify-between p-5 border-b border-slate-700 bg-slate-900/95 backdrop-blur">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <Cpu className="w-4 h-4 text-cyan-400" />
                            <span className="text-xs text-cyan-400 font-mono">VANGUARD SOVEREIGN — AI ANALYSIS</span>
                        </div>
                        <h2 className="text-white font-semibold text-sm font-mono truncate max-w-md">
                            {incident.error_type} · <span className="text-slate-400">{incident.endpoint}</span>
                        </h2>
                    </div>
                    <div className="flex items-center gap-2">
                        {/* Regenerate button */}
                        <button
                            id={`regenerate-${incident.fingerprint}`}
                            onClick={() => fetchAnalysis(true)}
                            disabled={loading}
                            title="Force-regenerate AI analysis (bypasses 24h cache)"
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/10 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
                        >
                            {loading
                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                : <RotateCcw className="w-3.5 h-3.5" />
                            }
                            {loading ? 'Analyzing…' : 'Regenerate'}
                        </button>
                        <button
                            onClick={onClose}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                        >
                            <XCircle className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div className="p-5 space-y-5">
                    {/* Incident meta */}
                    <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="bg-slate-800/60 rounded-lg p-3">
                            <div className="text-slate-500 mb-1">Severity</div>
                            <SeverityBadge s={incident.severity} />
                        </div>
                        <div className="bg-slate-800/60 rounded-lg p-3">
                            <div className="text-slate-500 mb-1">Occurrences</div>
                            <div className="text-white font-mono font-bold">{incident.occurrence_count}</div>
                        </div>
                        <div className="bg-slate-800/60 rounded-lg p-3">
                            <div className="text-slate-500 mb-1">First Seen</div>
                            <div className="text-slate-300 font-mono">{new Date(incident.first_seen).toLocaleString()}</div>
                        </div>
                        <div className="bg-slate-800/60 rounded-lg p-3">
                            <div className="text-slate-500 mb-1">Last Seen</div>
                            <div className="text-slate-300 font-mono">{new Date(incident.last_seen).toLocaleString()}</div>
                        </div>
                    </div>

                    {/* Analysis content */}
                    {loading && (
                        <div className="flex flex-col items-center justify-center gap-3 py-10 text-slate-400">
                            <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
                            <span className="text-sm">Vanguard Sovereign is analyzing…</span>
                        </div>
                    )}

                    {error && (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-sm text-red-400">
                            <strong>Analysis failed:</strong> {error}
                        </div>
                    )}

                    {analysis && !loading && (
                        <>
                            {/* Cache/model badge */}
                            <div className="flex items-center justify-between">
                                <ConfidenceDial pct={analysis.confidence} />
                                <div className="flex items-center gap-2 text-xs text-slate-500">
                                    {analysis.cached && (
                                        <span className="px-2 py-0.5 bg-slate-700 rounded text-slate-400">CACHED</span>
                                    )}
                                    {analysis.model_id && (
                                        <span className="px-2 py-0.5 bg-cyan-900/30 rounded text-cyan-600 font-mono">
                                            {analysis.model_id}
                                        </span>
                                    )}
                                    <span>{new Date(analysis.generated_at).toLocaleString()}</span>
                                </div>
                            </div>

                            {/* Root cause */}
                            <div className="bg-slate-800/60 rounded-lg p-4">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Root Cause</div>
                                <p className="text-slate-200 text-sm leading-relaxed">{analysis.root_cause}</p>
                            </div>

                            {/* Impact */}
                            <div className="bg-slate-800/60 rounded-lg p-4">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Impact</div>
                                <p className="text-slate-200 text-sm leading-relaxed">{analysis.impact}</p>
                            </div>

                            {/* Recommended fixes */}
                            <div className="bg-slate-800/60 rounded-lg p-4">
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Recommended Actions</div>
                                <ul className="space-y-2">
                                    {analysis.recommended_fix.map((fix, i) => (
                                        <li key={i} className="flex gap-2 text-sm text-slate-200">
                                            <span className="text-cyan-400 mt-0.5 shrink-0">→</span>
                                            <span>{fix}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            {/* Resolution readiness */}
                            <div className={`rounded-lg p-4 border ${analysis.ready_to_resolve
                                    ? 'bg-green-500/10 border-green-500/30'
                                    : 'bg-amber-500/10 border-amber-500/30'
                                }`}>
                                <div className="flex items-center gap-2 mb-2">
                                    {analysis.ready_to_resolve
                                        ? <CheckCircle2 className="w-4 h-4 text-green-400" />
                                        : <AlertTriangle className="w-4 h-4 text-amber-400" />
                                    }
                                    <span className={`text-sm font-medium ${analysis.ready_to_resolve ? 'text-green-400' : 'text-amber-400'}`}>
                                        {analysis.ready_to_resolve ? 'Ready to Resolve' : 'Not Ready Yet'}
                                    </span>
                                </div>
                                <p className="text-slate-300 text-xs leading-relaxed">{analysis.ready_reasoning}</p>
                            </div>
                        </>
                    )}

                    {/* Resolve button */}
                    {!resolved ? (
                        <button
                            id={`resolve-${incident.fingerprint}`}
                            onClick={handleResolve}
                            disabled={resolving}
                            className="w-full py-2.5 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2"
                        >
                            {resolving
                                ? <><Loader2 className="w-4 h-4 animate-spin" /> Resolving…</>
                                : <><CheckCircle2 className="w-4 h-4" /> Mark Resolved</>
                            }
                        </button>
                    ) : (
                        <div className="w-full py-2.5 rounded-xl bg-green-500/20 border border-green-500/40 text-green-400 text-sm font-semibold text-center">
                            ✓ Incident Resolved
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

// ─── Incident Row ─────────────────────────────────────────────────────────────
function IncidentRow({
    incident,
    selected,
    onSelect,
    onOpenAnalysis,
}: {
    incident: Incident
    selected: boolean
    onSelect: (fp: string) => void
    onOpenAnalysis: (inc: Incident) => void
}) {
    return (
        <div className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${selected ? 'bg-cyan-500/10 border-cyan-500/30' : 'bg-slate-800/40 border-slate-700/40 hover:border-slate-600'
            }`}>
            <input
                type="checkbox"
                checked={selected}
                onChange={() => onSelect(incident.fingerprint)}
                className="accent-cyan-500 w-4 h-4 shrink-0"
            />
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                    <SeverityBadge s={incident.severity} />
                    <span className="text-xs text-slate-400 font-mono truncate">{incident.endpoint}</span>
                </div>
                <div className="text-sm text-white truncate">{incident.error_type}</div>
                <div className="text-xs text-slate-500 mt-0.5">
                    {incident.occurrence_count}× · last {new Date(incident.last_seen).toLocaleTimeString()}
                </div>
            </div>
            <button
                id={`analyze-btn-${incident.fingerprint}`}
                onClick={() => onOpenAnalysis(incident)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/20 transition-colors shrink-0"
            >
                <Cpu className="w-3 h-3" />
                AI Analysis
            </button>
        </div>
    )
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function VanguardControlRoom() {
    const [incidents, setIncidents] = useState<Incident[]>([])
    const [stats, setStats] = useState<VanguardStats | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [selected, setSelected] = useState<Set<string>>(new Set())
    const [modalIncident, setModalIncident] = useState<Incident | null>(null)
    const [bulkResolving, setBulkResolving] = useState(false)
    const [statusFilter, setStatusFilter] = useState<'active' | 'all'>('active')
    const [showResolved, setShowResolved] = useState(false)

    const loadData = useCallback(async (silent = false) => {
        if (!silent) setLoading(true)
        else setRefreshing(true)
        try {
            const [incRes, statsRes] = await Promise.all([
                fetch(`${BASE}/vanguard/admin/incidents?status=${statusFilter}&limit=100`),
                fetch(`${BASE}/vanguard/admin/stats`),
            ])
            if (incRes.ok) {
                const data = await incRes.json()
                setIncidents(Array.isArray(data) ? data : data.incidents || [])
            }
            if (statsRes.ok) setStats(await statsRes.json())
        } catch { /* ignore */ }
        setLoading(false)
        setRefreshing(false)
    }, [statusFilter])

    useEffect(() => { loadData() }, [loadData])

    const toggleSelect = (fp: string) => {
        setSelected(prev => {
            const next = new Set(prev)
            next.has(fp) ? next.delete(fp) : next.add(fp)
            return next
        })
    }

    const selectAll = () => {
        setSelected(new Set(incidents.map(i => i.fingerprint)))
    }

    const bulkResolve = async () => {
        if (selected.size === 0) return
        setBulkResolving(true)
        try {
            await fetch(`${BASE}/vanguard/admin/incidents/bulk-resolve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    fingerprints: [...selected],
                    resolution_notes: 'Bulk resolved via Control Room',
                }),
            })
            setSelected(new Set())
            await loadData(true)
        } catch { /* ignore */ }
        setBulkResolving(false)
    }

    const healthColor = (score: number | undefined) => {
        if (!score) return 'text-slate-400'
        if (score >= 80) return 'text-green-400'
        if (score >= 50) return 'text-amber-400'
        return 'text-red-400'
    }

    const modeColor = (mode: string | undefined) => {
        if (!mode) return 'text-slate-400'
        if (mode.includes('OBSERVER')) return 'text-green-400'
        if (mode.includes('BREAKER')) return 'text-red-400'
        return 'text-amber-400'
    }

    return (
        <div className="p-6 h-full overflow-y-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <ShieldCheck className="w-6 h-6 text-cyan-400" />
                        Vanguard Control Room
                    </h1>
                    <p className="text-sm text-slate-400 mt-1">Digital Immune System · Live Incident Dashboard</p>
                </div>
                <button
                    id="vanguard-refresh-btn"
                    onClick={() => loadData(true)}
                    disabled={refreshing}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:border-cyan-500/40 hover:text-cyan-400 disabled:opacity-50 transition-all text-sm"
                >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Stats bar */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 text-center">
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Health Score</div>
                        <div className={`text-3xl font-bold font-mono ${healthColor(stats.health_score)}`}>
                            {stats.health_score?.toFixed(0) ?? 'N/A'}
                        </div>
                    </div>
                    <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 text-center">
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Active</div>
                        <div className="text-3xl font-bold font-mono text-red-400">{stats.active_incidents ?? 0}</div>
                    </div>
                    <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 text-center">
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Resolved</div>
                        <div className="text-3xl font-bold font-mono text-green-400">{stats.resolved_incidents ?? 0}</div>
                    </div>
                    <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4 text-center">
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Mode</div>
                        <div className={`text-sm font-bold font-mono ${modeColor(stats.vanguard_mode)}`}>
                            {stats.vanguard_mode?.replace('VanguardMode.', '') ?? 'UNKNOWN'}
                        </div>
                    </div>
                </div>
            )}

            {/* Toolbar */}
            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                    <button
                        onClick={selectAll}
                        className="text-xs px-3 py-1.5 rounded-lg border border-slate-600 text-slate-400 hover:text-white hover:border-slate-500 transition-colors"
                    >
                        Select All
                    </button>
                    {selected.size > 0 && (
                        <button
                            id="bulk-resolve-btn"
                            onClick={bulkResolve}
                            disabled={bulkResolving}
                            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 hover:bg-green-500/20 disabled:opacity-50 transition-colors"
                        >
                            {bulkResolving ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                            Resolve {selected.size} selected
                        </button>
                    )}
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                    <Zap className="w-3.5 h-3.5 text-cyan-400" />
                    {incidents.length} incident{incidents.length !== 1 ? 's' : ''}
                </div>
            </div>

            {/* Incident list */}
            {loading ? (
                <div className="flex items-center justify-center py-20 text-slate-400 gap-3">
                    <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
                    <span>Loading incidents…</span>
                </div>
            ) : incidents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
                    <ShieldCheck className="w-12 h-12 text-green-500/40" />
                    <span className="text-lg">All clear — no active incidents</span>
                </div>
            ) : (
                <div className="space-y-2">
                    {incidents.map(inc => (
                        <IncidentRow
                            key={inc.fingerprint}
                            incident={inc}
                            selected={selected.has(inc.fingerprint)}
                            onSelect={toggleSelect}
                            onOpenAnalysis={setModalIncident}
                        />
                    ))}
                </div>
            )}

            {/* Analysis Modal */}
            {modalIncident && (
                <AnalysisModal
                    incident={modalIncident}
                    onClose={() => setModalIncident(null)}
                />
            )}
        </div>
    )
}
