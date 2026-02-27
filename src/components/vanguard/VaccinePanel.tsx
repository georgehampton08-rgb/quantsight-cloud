import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
    Activity, ShieldCheck, XCircle, FileCode, CheckCircle2,
    Zap, Terminal, ChevronDown, AlertTriangle, Cpu, Bug,
    RefreshCw, RotateCcw, Clock, FolderOpen, Code2, ChevronRight
} from 'lucide-react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

// ── Types ─────────────────────────────────────────────────────────────────────

interface VaccineDefinition {
    id: string;
    name: string;
    description: string;
    status: 'ACTIVE' | 'DRAFT' | 'ERROR';
    deployment_date: string;
    target_pattern: string;
    hit_count: number;
}

type LogLevel = 'scan' | 'incident' | 'analysis' | 'patch' | 'skip' | 'chaos' | 'error' | 'done' | 'info' | 'warn';

interface LogEntry {
    id: string;
    level: LogLevel;
    ts: string;
    msg: string;
    detail?: string;
    fingerprint?: string;
    file?: string;
    confidence?: number;
}

interface RunSummary {
    run_id?: string;
    incidents_scanned: number;
    analyzed: number;
    patched: number;
    skipped: number;
    errors: number;
    chaos_fired: number;
    duration_ms: number;
}

interface RunHistoryEntry {
    run_id: string;
    triggered_at: string;
    completed_at: string;
    duration_ms: number;
    summary: {
        incidents_scanned: number;
        analyzed: number;
        patched: number;
        skipped: number;
        errors: number;
        chaos_fired: number;
    };
    size_bytes: number;
    patch_count: number;
}

interface RunDetail {
    run_id: string;
    schema_version?: string;
    triggered_by?: {
        ip?: string;
        forwarded_for?: string;
        user_agent?: string;
        referer?: string;
        host?: string;
        origin?: string;
        method?: string;
        url?: string;
        timestamp_utc?: string;
        server_hostname?: string;
        server_env?: string;
        accept_language?: string;
    };
    triggered_at: string;
    completed_at: string;
    duration_ms: number;
    summary: RunHistoryEntry['summary'];
    incidents?: Array<{
        index: number;
        fingerprint: string;
        title: string;
        error_type: string;
        error_message: string;
        endpoint: string;
        occurrence_count: number;
        severity: string;
        action_taken: string;
        ai_confidence: number;
        ai_root_cause: string;
        patch_file: string | null;
        skip_reason: string | null;
        processed_at: string;
    }>;
    log: Array<{ level: string; msg: string; ts: string; detail?: string; fingerprint?: string; file?: string; confidence?: number }>;
    patches: Array<{
        fingerprint: string;
        title: string;
        file_path: string;
        line_start: number;
        line_end: number;
        explanation: string | string[];
        confidence: number;
        generated_at: string;
        original_code_full: string;
        fixed_code_full: string;
    }>;
    environment?: {
        service?: string;
        revision?: string;
        region?: string;
        project?: string;
        python_ver?: string;
    };
}


// ── Helpers ───────────────────────────────────────────────────────────────────

const FALLBACK_API = 'https://quantsight-cloud-458498663186.us-central1.run.app';

function levelMeta(level: string) {
    switch (level) {
        case 'scan': return { color: 'text-cyan-400', prefix: '[ SCAN ]', bg: 'bg-cyan-400/10' };
        case 'incident': return { color: 'text-blue-300', prefix: '[ INC  ]', bg: 'bg-blue-400/10' };
        case 'analysis': return { color: 'text-purple-400', prefix: '[ AI   ]', bg: 'bg-purple-400/10' };
        case 'patch': return { color: 'text-emerald-400', prefix: '[ FIX  ]', bg: 'bg-emerald-500/10' };
        case 'skip': return { color: 'text-amber-400', prefix: '[ SKIP ]', bg: 'bg-amber-400/10' };
        case 'chaos': return { color: 'text-violet-400', prefix: '[CHAOS ]', bg: 'bg-violet-500/10' };
        case 'error': return { color: 'text-red-400', prefix: '[ ERR  ]', bg: 'bg-red-500/10' };
        case 'done': return { color: 'text-emerald-300', prefix: '[ DONE ]', bg: 'bg-emerald-400/10' };
        case 'warn': return { color: 'text-yellow-400', prefix: '[ WARN ]', bg: 'bg-yellow-400/10' };
        default: return { color: 'text-slate-400', prefix: '[ INFO ]', bg: '' };
    }
}

function fmtDate(iso: string) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function fmtSize(bytes: number) {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / 1048576).toFixed(2)}MB`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function LiveConsole({
    logs, running, progress, autoScroll, onScrollChange, logEndRef, consoleRef, onClear, onJumpBottom
}: {
    logs: LogEntry[];
    running: boolean;
    progress: number;
    autoScroll: boolean;
    onScrollChange: () => void;
    logEndRef: React.RefObject<HTMLDivElement>;
    consoleRef: React.RefObject<HTMLDivElement>;
    onClear: () => void;
    onJumpBottom: () => void;
}) {
    return (
        <div className="rounded-2xl border border-slate-700/60 overflow-hidden shadow-[0_0_30px_rgba(0,0,0,0.5)]">
            {/* Title bar */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-slate-950 border-b border-slate-800">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-500/70" />
                        <div className="w-3 h-3 rounded-full bg-amber-500/70" />
                        <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
                    </div>
                    <span className="text-slate-500 text-xs font-mono ml-2">vanguard_vaccine ~ live</span>
                    {running && (
                        <span className="ml-2 flex items-center gap-1.5 text-[10px] text-indigo-400 font-mono">
                            <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping" />
                            RUNNING
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-4">
                    {!autoScroll && (
                        <button onClick={onJumpBottom} className="text-[10px] text-amber-400 hover:text-white flex items-center gap-1 transition-colors">
                            <ChevronDown className="w-3 h-3" /> Jump to bottom
                        </button>
                    )}
                    <button onClick={onClear} className="text-[10px] text-slate-600 hover:text-slate-300 flex items-center gap-1 transition-colors">
                        <RotateCcw className="w-3 h-3" /> Clear
                    </button>
                </div>
            </div>

            {/* Progress bar */}
            {(running || progress > 0) && (
                <div className="h-0.5 bg-slate-800">
                    <div
                        className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500 transition-all duration-700"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            )}

            {/* Log output */}
            <div
                ref={consoleRef}
                onScroll={onScrollChange}
                className="h-80 overflow-y-auto bg-[#080810] font-mono text-xs p-3 space-y-0.5"
            >
                {logs.length === 0 ? (
                    <div className="text-slate-700 pt-3 pl-1 select-none">Awaiting vaccine cycle initiation...</div>
                ) : (
                    logs.map((entry) => {
                        const { color, prefix, bg } = levelMeta(entry.level);
                        return (
                            <div key={entry.id} className={`flex items-start gap-2 px-1 py-[2px] rounded transition-colors hover:${bg}`}>
                                <span className="text-slate-700 flex-shrink-0 select-none w-16 text-right">{entry.ts}</span>
                                <span className={`flex-shrink-0 font-bold ${color} select-none`}>{prefix}</span>
                                <span className="text-slate-300 leading-relaxed break-all">
                                    {entry.msg}
                                    {entry.fingerprint && (
                                        <span className={`ml-2 text-[10px] ${color} opacity-60`}>[{entry.fingerprint.slice(0, 14)}…]</span>
                                    )}
                                    {entry.file && (
                                        <span className="ml-2 text-slate-600 text-[10px]">→ {entry.file}</span>
                                    )}
                                    {entry.confidence !== undefined && (
                                        <span className="ml-2 text-emerald-400 font-bold">{entry.confidence.toFixed(0)}%</span>
                                    )}
                                    {entry.detail && (
                                        <span className="ml-2 text-slate-600 text-[10px] break-all" title={entry.detail}>
                                            {entry.detail.length > 100 ? entry.detail.slice(0, 100) + '…' : entry.detail}
                                        </span>
                                    )}
                                </span>
                            </div>
                        );
                    })
                )}
                <div ref={logEndRef} />
            </div>
        </div>
    );
}

function SummaryBar({ s, label }: { s: RunSummary | RunHistoryEntry['summary']; label?: string }) {
    const items = [
        { label: 'Scanned', val: (s as any).incidents_scanned ?? 0, color: 'text-slate-300' },
        { label: 'Analyzed', val: (s as any).analyzed ?? 0, color: 'text-cyan-400' },
        { label: 'Patched', val: (s as any).patched ?? 0, color: 'text-emerald-400' },
        { label: 'Skipped', val: (s as any).skipped ?? 0, color: 'text-amber-400' },
        { label: 'Errors', val: (s as any).errors ?? 0, color: 'text-red-400' },
        { label: 'Chaos', val: (s as any).chaos_fired ?? 0, color: 'text-violet-400' },
    ];
    return (
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-3 grid grid-cols-3 sm:grid-cols-6 gap-4">
            {items.map(item => (
                <div key={item.label} className="text-center">
                    <div className={`text-2xl font-black ${item.color}`}>{item.val}</div>
                    <div className="text-[9px] text-slate-600 uppercase tracking-widest mt-0.5">{item.label}</div>
                </div>
            ))}
        </div>
    );
}

function RunHistoryPanel() {
    const [history, setHistory] = useState<RunHistoryEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [selected, setSelected] = useState<RunDetail | null>(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [expandedPatch, setExpandedPatch] = useState<string | null>(null);

    const loadHistory = useCallback(async () => {
        setLoading(true);
        try {
            const res = await ApiContract.execute<{ runs: RunHistoryEntry[] }>(null, {
                path: 'vanguard/admin/vaccine/run-history'
            });
            setHistory(res.data?.runs || []);
        } catch { setHistory([]); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { loadHistory(); }, [loadHistory]);

    const openRun = async (run_id: string) => {
        setLoadingDetail(true);
        setSelected(null);
        try {
            const res = await ApiContract.execute<RunDetail>(null, {
                path: `vanguard/admin/vaccine/run-history/${run_id}`
            });
            setSelected(res.data);
        } catch { }
        finally { setLoadingDetail(false); }
    };

    // ── Detail view — full overlay modal (prevents cutoff in scroll containers) ──
    if (selected) {
        const tb = selected.triggered_by;
        const env = selected.environment;
        const renderExplanation = (ex: string | string[]) => {
            if (Array.isArray(ex)) return ex.map((line, i) => <div key={i} className="text-slate-300 text-xs leading-relaxed py-0.5">{line}</div>);
            return <p className="text-slate-300 text-sm">{String(ex)}</p>;
        };
        const actionColor = (a: string) => {
            if (a === 'patched') return 'text-emerald-400 bg-emerald-500/10';
            if (a === 'skipped') return 'text-amber-400 bg-amber-500/10';
            if (a === 'error') return 'text-red-400 bg-red-500/10';
            return 'text-slate-400 bg-slate-500/10';
        };

        return (
            <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex flex-col">
                {/* Sticky header */}
                <div className="flex-shrink-0 bg-[#0a0e1a] border-b border-slate-700/50 px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setSelected(null)}
                            className="text-slate-400 hover:text-white flex items-center gap-1.5 text-sm transition-colors border border-slate-700 rounded-lg px-3 py-1.5 hover:bg-slate-800"
                        >
                            ← Back
                        </button>
                        <div>
                            <span className="font-mono text-sm text-indigo-300 font-bold">{selected.run_id}</span>
                            <span className="text-slate-500 text-xs ml-3">{fmtDate(selected.triggered_at)}</span>
                            <span className="text-slate-600 text-xs ml-3">{(selected.duration_ms / 1000).toFixed(1)}s</span>
                            {selected.schema_version && <span className="text-slate-700 text-xs ml-3">schema v{selected.schema_version}</span>}
                        </div>
                    </div>
                    <button onClick={() => setSelected(null)} className="text-slate-500 hover:text-white p-1 rounded-lg transition-colors">
                        <XCircle className="w-5 h-5" />
                    </button>
                </div>

                {/* Scrollable body */}
                <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

                    <SummaryBar s={selected.summary} />

                    {/* ── Triggered By ───────────────────────────────────── */}
                    {tb && (
                        <div className="border border-slate-700/50 rounded-xl overflow-hidden">
                            <div className="bg-slate-900/50 px-4 py-2.5 border-b border-slate-700/30">
                                <h4 className="text-slate-300 font-bold text-sm flex items-center gap-2">
                                    <Activity className="w-4 h-4 text-cyan-400" /> Triggered By
                                </h4>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-3 p-4 text-xs">
                                {tb.ip && <div><span className="text-slate-600 block">IP Address</span><span className="text-slate-300 font-mono">{tb.ip}</span></div>}
                                {tb.user_agent && <div className="col-span-2"><span className="text-slate-600 block">User Agent</span><span className="text-slate-300 font-mono text-[10px] break-all">{tb.user_agent}</span></div>}
                                {tb.host && <div><span className="text-slate-600 block">Host</span><span className="text-slate-300 font-mono">{tb.host}</span></div>}
                                {tb.origin && <div><span className="text-slate-600 block">Origin</span><span className="text-slate-300 font-mono">{tb.origin}</span></div>}
                                {tb.referer && <div><span className="text-slate-600 block">Referer</span><span className="text-slate-300 font-mono">{tb.referer}</span></div>}
                                {tb.method && <div><span className="text-slate-600 block">Method</span><span className="text-slate-300 font-mono">{tb.method}</span></div>}
                                {tb.timestamp_utc && <div><span className="text-slate-600 block">Timestamp (UTC)</span><span className="text-slate-300 font-mono">{tb.timestamp_utc}</span></div>}
                                {tb.server_env && <div><span className="text-slate-600 block">Server Env</span><span className="text-slate-300 font-mono">{tb.server_env}</span></div>}
                            </div>
                        </div>
                    )}

                    {/* ── Incident Summary Table ────────────────────────── */}
                    {selected.incidents && selected.incidents.length > 0 && (
                        <div className="border border-slate-700/50 rounded-xl overflow-hidden">
                            <div className="bg-slate-900/50 px-4 py-2.5 border-b border-slate-700/30">
                                <h4 className="text-slate-300 font-bold text-sm flex items-center gap-2">
                                    <Bug className="w-4 h-4 text-amber-400" /> Incidents Processed ({selected.incidents.length})
                                </h4>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                    <thead>
                                        <tr className="text-slate-500 border-b border-slate-800">
                                            <th className="text-left px-4 py-2 font-medium">#</th>
                                            <th className="text-left px-4 py-2 font-medium">Endpoint</th>
                                            <th className="text-left px-4 py-2 font-medium">Type</th>
                                            <th className="text-center px-4 py-2 font-medium">Hits</th>
                                            <th className="text-left px-4 py-2 font-medium">Action</th>
                                            <th className="text-left px-4 py-2 font-medium">Reason / Patch</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {selected.incidents.map(inc => (
                                            <tr key={inc.fingerprint} className="border-b border-slate-800/50 hover:bg-white/[0.02]">
                                                <td className="px-4 py-2 text-slate-600">{inc.index}</td>
                                                <td className="px-4 py-2 font-mono text-slate-300 max-w-[200px] truncate" title={inc.endpoint}>{inc.endpoint}</td>
                                                <td className="px-4 py-2 text-slate-400">{inc.error_type}</td>
                                                <td className="px-4 py-2 text-center text-slate-400">{inc.occurrence_count}</td>
                                                <td className="px-4 py-2">
                                                    <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${actionColor(inc.action_taken)}`}>
                                                        {inc.action_taken.toUpperCase()}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-2 text-slate-500 max-w-[200px] truncate" title={inc.skip_reason || inc.patch_file || ''}>
                                                    {inc.skip_reason || inc.patch_file || '—'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* ── Patches ───────────────────────────────────────── */}
                    {selected.patches.length > 0 && (
                        <div className="space-y-3">
                            <h4 className="text-slate-300 font-bold text-sm flex items-center gap-2">
                                <Code2 className="w-4 h-4 text-emerald-400" /> Generated Patches ({selected.patches.length})
                            </h4>
                            {selected.patches.map((p, i) => (
                                <div key={i} className="border border-emerald-500/20 rounded-xl overflow-hidden">
                                    <button
                                        onClick={() => setExpandedPatch(expandedPatch === `${i}` ? null : `${i}`)}
                                        className="w-full flex items-center justify-between px-4 py-3 bg-emerald-900/10 hover:bg-emerald-900/20 transition-colors text-left"
                                    >
                                        <div className="flex items-center gap-3">
                                            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                                            <div>
                                                <div className="text-emerald-300 font-bold text-sm">{p.file_path}<span className="text-slate-500">:{p.line_start}-{p.line_end}</span></div>
                                                <div className="text-slate-500 text-xs mt-0.5">{p.title} • {p.confidence?.toFixed(0)}% confidence</div>
                                            </div>
                                        </div>
                                        {expandedPatch === `${i}` ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
                                    </button>
                                    {expandedPatch === `${i}` && (
                                        <div className="divide-y divide-slate-800">
                                            <div className="p-4 bg-slate-900/50">
                                                <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-2">Explanation</div>
                                                {renderExplanation(p.explanation)}
                                            </div>
                                            <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-slate-800">
                                                <div className="p-4">
                                                    <div className="text-[10px] text-red-400 uppercase tracking-widest mb-2 font-bold">BEFORE (original)</div>
                                                    <pre className="text-red-300/80 text-[11px] overflow-x-auto font-mono leading-relaxed bg-red-950/20 rounded p-3 max-h-64 overflow-y-auto whitespace-pre-wrap">
                                                        {p.original_code_full || '(no original code — new file or endpoint)'}
                                                    </pre>
                                                </div>
                                                <div className="p-4">
                                                    <div className="text-[10px] text-emerald-400 uppercase tracking-widest mb-2 font-bold">AFTER (patched)</div>
                                                    <pre className="text-emerald-300/80 text-[11px] overflow-x-auto font-mono leading-relaxed bg-emerald-950/20 rounded p-3 max-h-64 overflow-y-auto whitespace-pre-wrap">
                                                        {p.fixed_code_full || '(not captured)'}
                                                    </pre>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* ── Full log replay ───────────────────────────────── */}
                    <div>
                        <h4 className="text-slate-300 font-bold text-sm flex items-center gap-2 mb-2">
                            <Terminal className="w-4 h-4 text-slate-400" /> Full Run Log ({selected.log.length} entries)
                        </h4>
                        <div className="bg-[#080810] rounded-xl font-mono text-xs p-3 max-h-80 overflow-y-auto space-y-0.5 border border-slate-800">
                            {selected.log.map((e, i) => {
                                const { color, prefix } = levelMeta(e.level);
                                return (
                                    <div key={i} className="flex items-start gap-2 hover:bg-white/[0.02] px-1 py-[1px] rounded">
                                        <span className="text-slate-700 flex-shrink-0 w-16 text-right">{e.ts}</span>
                                        <span className={`flex-shrink-0 ${color} font-bold`}>{prefix}</span>
                                        <span className="text-slate-400 break-all">
                                            {e.msg}
                                            {e.fingerprint && <span className={`ml-2 text-[10px] ${color} opacity-50`}>[{e.fingerprint.slice(0, 14)}…]</span>}
                                            {e.file && <span className="ml-2 text-slate-600 text-[10px]">→ {e.file}</span>}
                                            {e.confidence != null && <span className="ml-2 text-emerald-400 font-bold">{e.confidence.toFixed(0)}%</span>}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* ── Environment ───────────────────────────────────── */}
                    {env && (
                        <div className="flex flex-wrap gap-x-6 gap-y-1 text-[10px] text-slate-600 border-t border-slate-800 pt-3">
                            {env.service && <span>Service: <span className="text-slate-400">{env.service}</span></span>}
                            {env.revision && <span>Revision: <span className="text-slate-400">{env.revision}</span></span>}
                            {env.region && <span>Region: <span className="text-slate-400">{env.region}</span></span>}
                            {env.python_ver && <span>Python: <span className="text-slate-400">{env.python_ver}</span></span>}
                        </div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-slate-300 font-bold flex items-center gap-2">
                    <Clock className="w-4 h-4 text-indigo-400" /> Run History
                </h3>
                <button onClick={loadHistory} disabled={loading} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors">
                    <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </button>
            </div>

            {loading ? (
                <div className="py-12 text-center text-slate-600 flex flex-col items-center">
                    <Activity className="w-6 h-6 animate-spin mb-2 text-indigo-400 opacity-40" />
                    Loading audit files...
                </div>
            ) : history.length === 0 ? (
                <div className="py-16 text-center text-slate-600 border border-dashed border-slate-800 rounded-xl flex flex-col items-center">
                    <FolderOpen className="w-8 h-8 mb-3 opacity-20" />
                    <div className="text-sm">No run history yet.</div>
                    <div className="text-xs mt-1 text-slate-700">Click "Run Vaccine Now" to generate the first audit file.</div>
                </div>
            ) : (
                <div className="space-y-2">
                    {history.map((run) => (
                        <button
                            key={run.run_id}
                            onClick={() => openRun(run.run_id)}
                            className="w-full flex items-center justify-between bg-slate-900/60 hover:bg-slate-800/60 border border-slate-700/50 hover:border-slate-600/60 rounded-xl px-5 py-3.5 transition-all text-left group"
                        >
                            <div className="flex items-center gap-4">
                                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${run.summary.errors > 0 ? 'bg-red-400' : run.summary.patched > 0 ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                                <div>
                                    <div className="font-mono text-sm text-slate-300 group-hover:text-white transition-colors">{run.run_id}</div>
                                    <div className="text-xs text-slate-500 mt-0.5">{fmtDate(run.triggered_at)}</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-5 text-right">
                                <div className="hidden sm:block">
                                    <div className="text-xs text-slate-500 mb-0.5">Patches</div>
                                    <div className={`text-sm font-black ${run.patch_count > 0 ? 'text-emerald-400' : 'text-slate-500'}`}>{run.patch_count}</div>
                                </div>
                                <div className="hidden sm:block">
                                    <div className="text-xs text-slate-500 mb-0.5">Duration</div>
                                    <div className="text-sm text-slate-400">{(run.duration_ms / 1000).toFixed(1)}s</div>
                                </div>
                                <div className="hidden md:block">
                                    <div className="text-xs text-slate-500 mb-0.5">Size</div>
                                    <div className="text-sm text-slate-400">{fmtSize(run.size_bytes)}</div>
                                </div>
                                <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-slate-300 transition-colors" />
                            </div>
                        </button>
                    ))}
                </div>
            )}
            {loadingDetail && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-indigo-500/30 rounded-xl p-8 flex flex-col items-center gap-3">
                        <Activity className="w-8 h-8 animate-spin text-indigo-400" />
                        <span className="text-slate-300 text-sm">Loading audit file...</span>
                    </div>
                </div>
            )}
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function VaccinePanelContent() {
    const [loading, setLoading] = useState(false);
    const [vaccines, setVaccines] = useState<VaccineDefinition[]>([]);
    const [running, setRunning] = useState(false);
    const [activeTab, setActiveTab] = useState<'definitions' | 'console' | 'history'>('definitions');
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [summary, setSummary] = useState<RunSummary | null>(null);
    const [progress, setProgress] = useState(0);
    const [autoScroll, setAutoScroll] = useState(true);
    const logEndRef = useRef<HTMLDivElement>(null);
    const consoleRef = useRef<HTMLDivElement>(null);
    const eventSourceRef = useRef<EventSource | null>(null);

    const appendLog = useCallback((entry: Omit<LogEntry, 'id' | 'ts'>) => {
        setLogs(prev => [...prev, {
            id: `${Date.now()}-${Math.random()}`,
            ts: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            ...entry
        }]);
    }, []);

    useEffect(() => {
        if (autoScroll && logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs, autoScroll]);

    const handleConsoleScroll = () => {
        if (!consoleRef.current) return;
        const { scrollTop, scrollHeight, clientHeight } = consoleRef.current;
        setAutoScroll(scrollHeight - scrollTop - clientHeight < 60);
    };

    const loadVaccines = useCallback(async () => {
        setLoading(true);
        try {
            const res = await ApiContract.execute<{ vaccines: VaccineDefinition[] }>(null, {
                path: 'vanguard/admin/vaccines'
            });
            setVaccines(res.data?.vaccines || []);
        } catch (e) {
            console.error('Failed to load vaccines', e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadVaccines(); }, [loadVaccines]);

    const triggerVaccineRun = useCallback(() => {
        setLogs([]);
        setSummary(null);
        setProgress(0);
        setAutoScroll(true);
        setActiveTab('console');
        setRunning(true);

        const base = (import.meta.env?.VITE_API_URL || FALLBACK_API).replace(/\/$/, '');
        const url = `${base}/vanguard/admin/vaccine/run-stream`;

        appendLog({ level: 'info', msg: `Connecting to Vanguard Vaccine Engine...`, detail: url });

        const es = new EventSource(url);
        eventSourceRef.current = es;

        es.onopen = () => {
            appendLog({ level: 'scan', msg: 'SSE stream connected — vaccine cycle initiating.' });
        };

        es.addEventListener('log', (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                if (data.progress !== undefined) setProgress(data.progress);
                appendLog({
                    level: data.level as LogLevel,
                    msg: data.msg,
                    detail: data.detail,
                    fingerprint: data.fingerprint,
                    file: data.file,
                    confidence: data.confidence,
                });
            } catch { }
        });

        es.addEventListener('summary', (e: MessageEvent) => {
            try {
                const s = JSON.parse(e.data) as RunSummary;
                setSummary(s);
                setProgress(100);
                appendLog({
                    level: 'done',
                    msg: `✅ Cycle complete — ${s.patched} patch(es) in ${(s.duration_ms / 1000).toFixed(1)}s — audit saved as ${s.run_id}.json`,
                });
            } catch { }
        });

        es.addEventListener('done', () => {
            setRunning(false);
            es.close();
            loadVaccines();
        });

        es.onerror = () => {
            appendLog({ level: 'error', msg: 'Stream ended or connection lost.' });
            setRunning(false);
            es.close();
        };
    }, [appendLog, loadVaccines]);

    useEffect(() => () => { eventSourceRef.current?.close(); }, []);

    const tabs: { id: typeof activeTab; label: string }[] = [
        { id: 'definitions', label: 'Definitions' },
        { id: 'console', label: running ? '⚡ Live Console' : 'Console' },
        { id: 'history', label: 'Run History' },
    ];

    return (
        <div className="space-y-5">

            {/* ── Header ─────────────────────────────────────────────────────── */}
            <div className="flex flex-col sm:flex-row justify-between sm:items-start gap-4 border-b border-slate-700/50 pb-5">
                <div>
                    <h2 className="text-white font-black text-xl flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                            <ShieldCheck className="w-5 h-5 text-indigo-400" />
                        </div>
                        Vaccine Subsystem
                    </h2>
                    <p className="text-sm text-slate-400 mt-1 max-w-2xl leading-relaxed">
                        AI-powered autonomous code remediation. Runs Gemini analysis on every active incident,
                        generates surgical code patches, fires chaos validation scenarios, and saves a full
                        audit trail you can review in{' '}
                        <button onClick={() => setActiveTab('history')} className="text-indigo-300 underline hover:text-white transition-colors">
                            Run History
                        </button>.
                    </p>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                    {activeTab === 'definitions' && (
                        <button
                            onClick={loadVaccines}
                            disabled={loading || running}
                            className="flex items-center gap-2 px-4 py-2 border border-slate-600 hover:bg-slate-800 disabled:opacity-50 text-slate-300 rounded-lg text-sm font-bold transition-colors"
                        >
                            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </button>
                    )}
                    <button
                        onClick={triggerVaccineRun}
                        disabled={running}
                        className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl text-sm font-bold transition-all shadow-[0_0_20px_rgba(99,102,241,0.35)]"
                    >
                        {running
                            ? <><Cpu className="w-4 h-4 animate-pulse" /> Running...</>
                            : <><Zap className="w-4 h-4" /> Run Vaccine Now</>
                        }
                    </button>
                </div>
            </div>

            {/* ── Tabs ───────────────────────────────────────────────────────── */}
            <div className="flex items-center gap-1 border-b border-slate-700/50">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-4 py-2 text-sm font-semibold rounded-t-lg transition-colors -mb-px border-b-2 ${activeTab === tab.id
                            ? 'text-indigo-300 border-indigo-500'
                            : 'text-slate-500 border-transparent hover:text-slate-300'
                            }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* ── Tab: Console ───────────────────────────────────────────────── */}
            {activeTab === 'console' && (
                <div className="space-y-4">
                    <LiveConsole
                        logs={logs}
                        running={running}
                        progress={progress}
                        autoScroll={autoScroll}
                        onScrollChange={handleConsoleScroll}
                        logEndRef={logEndRef}
                        consoleRef={consoleRef}
                        onClear={() => setLogs([])}
                        onJumpBottom={() => {
                            setAutoScroll(true);
                            logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                        }}
                    />
                    {summary && <SummaryBar s={summary} />}
                    {!running && logs.length === 0 && (
                        <div className="py-10 text-center text-slate-600 text-sm">
                            Click <span className="text-indigo-300 font-bold">Run Vaccine Now</span> to start and watch the live feed.
                        </div>
                    )}
                </div>
            )}

            {/* ── Tab: History ───────────────────────────────────────────────── */}
            {activeTab === 'history' && <RunHistoryPanel />}

            {/* ── Tab: Definitions ───────────────────────────────────────────── */}
            {activeTab === 'definitions' && (
                <div className="space-y-5">
                    <KnowledgeBaseStatus />
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">

                        {/* Core always-on vaccine */}
                        <div className="bg-indigo-950/20 border border-indigo-500/30 rounded-xl p-5 shadow-[0_0_20px_rgba(99,102,241,0.07)] relative overflow-hidden">
                            <div className="absolute top-0 right-0 w-28 h-28 bg-indigo-500/10 rounded-bl-full -mr-6 -mt-6 pointer-events-none" />
                            <div className="flex justify-between items-start mb-4">
                                <span className="text-indigo-400 font-mono text-xs bg-black/40 px-2.5 py-1 rounded">VACCINE-001 (CORE)</span>
                                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                            </div>
                            <h3 className="text-slate-200 font-bold mb-2">Shadow Service Protection</h3>
                            <p className="text-slate-400 text-sm leading-relaxed mb-4 min-h-[40px]">
                                Defensive wrapper for multi-container deployments where obsolete routes throw UnboundLocalError during initialization.
                            </p>
                            <div className="grid grid-cols-2 gap-3 border-t border-slate-700/50 pt-4">
                                <div>
                                    <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">Target</div>
                                    <div className="text-xs text-slate-300 font-mono flex items-center gap-1">
                                        <FileCode className="w-3 h-3 text-emerald-400" /> main.py
                                    </div>
                                </div>
                                <div>
                                    <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">Total Blocks</div>
                                    <div className="text-sm text-white font-black">24,401</div>
                                </div>
                            </div>
                        </div>

                        {/* Dynamic vaccines */}
                        {loading && vaccines.length === 0 ? (
                            <div className="col-span-full py-12 flex flex-col items-center justify-center border border-dashed border-slate-700/50 rounded-xl text-slate-500">
                                <Activity className="w-7 h-7 mb-3 animate-spin opacity-40 text-indigo-400" />
                                <span className="text-sm">Loading definitions from Surgeon...</span>
                            </div>
                        ) : vaccines.length === 0 && !loading ? (
                            <div className="col-span-full py-12 flex flex-col items-center justify-center border border-dashed border-slate-700/50 rounded-xl text-slate-500">
                                <Bug className="w-7 h-7 mb-3 opacity-30" />
                                <span className="text-sm">No dynamic vaccines generated yet.</span>
                                <span className="text-xs mt-1 text-slate-600">Run the vaccine cycle to generate new definitions.</span>
                            </div>
                        ) : (
                            vaccines.map((vac) => (
                                <div key={vac.id} className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 hover:border-slate-600/60 transition-colors flex flex-col relative overflow-hidden">
                                    <div className="absolute top-0 right-0 w-28 h-28 bg-slate-500/5 rounded-bl-full -mr-6 -mt-6 pointer-events-none" />
                                    <div className="flex justify-between items-start mb-4">
                                        <span className="text-slate-400 font-mono text-xs bg-black/40 px-2.5 py-1 rounded">{vac.id}</span>
                                        {vac.status === 'ACTIVE' ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                                            : vac.status === 'DRAFT' ? <ShieldCheck className="w-5 h-5 text-amber-400" />
                                                : <XCircle className="w-5 h-5 text-red-400" />}
                                    </div>
                                    <h3 className="text-slate-200 font-bold mb-2 break-words">{vac.name}</h3>
                                    <p className="text-slate-400 text-sm leading-relaxed mb-4 flex-1">{vac.description}</p>
                                    <div className="grid grid-cols-2 gap-3 border-t border-slate-700/50 pt-4">
                                        <div>
                                            <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">Target</div>
                                            <div className="text-xs text-slate-300 font-mono flex items-center gap-1 overflow-hidden" title={vac.target_pattern}>
                                                <FileCode className="w-3 h-3 flex-shrink-0 text-slate-400" />
                                                <span className="truncate">{vac.target_pattern.split('/').pop() || vac.target_pattern}</span>
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-1">Blocks</div>
                                            <div className="text-sm text-white font-black">{vac.hit_count.toLocaleString()}</div>
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// ── KB Status Widget ──────────────────────────────────────────────────────────

interface KBStatus {
    built?: string;
    age_seconds?: number;
    stale?: boolean;
    ttl_seconds?: number;
    module_count?: number;
    route_count?: number;
    collection_count?: number;
    dep_count?: number;
    root?: string;
    error?: string;
}

function KnowledgeBaseStatus() {
    const [kb, setKb] = useState<KBStatus | null>(null);
    const [rebuilding, setRebuilding] = useState(false);
    const [loading, setLoading] = useState(true);

    const fetchStatus = useCallback(async () => {
        setLoading(true);
        try {
            const res = await ApiContract.execute<KBStatus>(null, { path: 'vanguard/admin/vaccine/kb-status' });
            setKb(res.data);
        } catch { setKb(null); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchStatus(); }, [fetchStatus]);

    const rebuild = async () => {
        setRebuilding(true);
        try {
            await ApiContract.execute(null, { path: 'vanguard/admin/vaccine/kb-rebuild', method: 'POST' } as any);
            await fetchStatus();
        } catch { }
        finally { setRebuilding(false); }
    };

    const isStale = !kb || kb.stale !== false;
    const hasError = !!kb?.error;
    const statusColor = hasError ? 'text-red-400' : isStale ? 'text-amber-400' : 'text-emerald-400';
    const borderColor = hasError ? 'border-red-500/20' : isStale ? 'border-amber-500/20' : 'border-emerald-500/20';
    const bgColor = hasError ? 'bg-red-900/10' : isStale ? 'bg-amber-900/10' : 'bg-emerald-900/10';

    const ageFmt = (s?: number) => {
        if (s == null) return '—';
        if (s < 60) return `${s}s ago`;
        if (s < 3600) return `${Math.round(s / 60)}m ago`;
        return `${(s / 3600).toFixed(1)}h ago`;
    };

    return (
        <div className={`rounded-xl border ${borderColor} ${bgColor} px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4`}>
            <div className="flex items-start gap-3">
                <div className={`w-8 h-8 rounded-lg border ${borderColor} flex items-center justify-center flex-shrink-0 mt-0.5`}>
                    <Activity className={`w-4 h-4 ${loading || rebuilding ? 'animate-spin' : ''} ${statusColor}`} />
                </div>
                <div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-slate-200 font-bold text-sm">Codebase Knowledge Base</span>
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${hasError ? 'bg-red-500/20 text-red-300'
                            : isStale ? 'bg-amber-500/20 text-amber-300'
                                : 'bg-emerald-500/20 text-emerald-300'
                            }`}>
                            {hasError ? 'ERROR' : isStale ? 'STALE' : 'WARM'}
                        </span>
                    </div>
                    {kb && !hasError ? (
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5 mt-1">
                            <span className="text-slate-500 text-xs">
                                <span className="text-slate-300 font-bold">{kb.module_count ?? 0}</span> modules indexed
                            </span>
                            <span className="text-slate-500 text-xs">
                                <span className="text-slate-300 font-bold">{kb.route_count ?? 0}</span> routes mapped
                            </span>
                            <span className="text-slate-500 text-xs">
                                <span className="text-slate-300 font-bold">{kb.collection_count ?? 0}</span> collections
                            </span>
                            <span className="text-slate-500 text-xs">
                                <span className="text-slate-300 font-bold">{kb.dep_count ?? 0}</span> deps
                            </span>
                            <span className="text-slate-500 text-xs">Built {ageFmt(kb.age_seconds)}</span>
                        </div>
                    ) : (
                        <p className="text-slate-500 text-xs mt-1">
                            {loading ? 'Checking KB status...' : hasError ? kb?.error : 'KB not yet built — click Rebuild to index the codebase'}
                        </p>
                    )}
                    <p className="text-slate-600 text-[10px] mt-1 max-w-lg">
                        Injected into every Gemini patch prompt so the AI understands your architecture, routes, and dependencies. Rebuild after significant code changes.
                    </p>
                </div>
            </div>
            <button
                onClick={rebuild}
                disabled={rebuilding || loading}
                className="flex items-center gap-2 px-4 py-2 border border-slate-600 hover:bg-slate-800 disabled:opacity-50 text-slate-300 rounded-lg text-xs font-bold transition-colors flex-shrink-0"
            >
                <RefreshCw className={`w-3 h-3 ${rebuilding ? 'animate-spin' : ''}`} />
                {rebuilding ? 'Rebuilding...' : 'Rebuild KB'}
            </button>
        </div>
    );
}

export const VaccinePanel = () => (
    <SectionErrorBoundary fallbackMessage="Vaccine System Definitions offline">
        <VaccinePanelContent />
    </SectionErrorBoundary>
);

