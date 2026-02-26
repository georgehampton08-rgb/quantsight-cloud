import React, { useEffect, useState, useCallback } from 'react';
import {
    Activity, ShieldCheck, AlertTriangle, RefreshCw, Cpu,
    CheckCircle2, Loader2, FileKey, X, Zap
} from 'lucide-react';

const BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app';

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
    ai_analysis?: any;
}

interface VanguardStats {
    active_incidents: number;
    resolved_incidents: number;
    health_score: number;
    vanguard_mode: string;
}

// ─── SVG Components ───────────────────────────────────────────────────────────
function DoughnutScore({ score = 0 }: { score: number }) {
    const strokeDasharray = 251.2; // roughly 2 * pi * 40
    const strokeDashoffset = strokeDasharray - (score / 100) * strokeDasharray;
    const color = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#f43f5e';

    return (
        <div className="relative w-48 h-48 flex items-center justify-center">
            <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" strokeWidth="8" />
                <circle
                    cx="50" cy="50" r="40" fill="none" stroke={color} strokeWidth="8"
                    strokeDasharray={strokeDasharray}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                    className="transition-all duration-1000 ease-out"
                />
            </svg>
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function VanguardControlRoom() {
    const [activeTab, setActiveTab] = useState<'HEALTH' | 'INCIDENTS' | 'ARCHIVES' | 'LEARNING'>('HEALTH');
    const [incidents, setIncidents] = useState<Incident[]>([]);
    const [stats, setStats] = useState<VanguardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [selected, setSelected] = useState<Set<string>>(new Set());

    const loadData = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        else setRefreshing(true);
        try {
            const [incRes, statsRes] = await Promise.all([
                fetch(`${BASE}/vanguard/admin/incidents?status=active&limit=100`),
                fetch(`${BASE}/vanguard/admin/stats`),
            ]);
            if (incRes.ok) {
                const data = await incRes.json();
                setIncidents(Array.isArray(data) ? data : data.incidents || []);
            }
            if (statsRes.ok) setStats(await statsRes.json());
        } catch { /* ignore */ }
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
        if (selected.size === incidents.length) {
            setSelected(new Set());
        } else {
            setSelected(new Set(incidents.map(i => i.fingerprint)));
        }
    };

    // Subsystem helper
    const subSystemCheck = (name: string, active: boolean, subtitle: string) => (
        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 flex justify-between items-start">
            <div>
                <h4 className="text-white font-bold text-sm tracking-widest">{name}</h4>
                <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
            </div>
            <div className={`w-5 h-5 rounded-full flex justify-center items-center border ${active ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-slate-600/50 text-slate-500 bg-slate-700/20'}`}>
                {active ? <CheckCircle2 className="w-3 h-3" /> : <X className="w-3 h-3" />}
            </div>
        </div>
    );

    return (
        <div className="p-8 h-full overflow-y-auto space-y-8 bg-slate-900 font-sans">

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        <Activity className="w-8 h-8 text-[#2ad8a0]" />
                        Vanguard Control Room
                    </h1>
                    <p className="text-sm text-slate-400 mt-1 pl-1">System Health & Incident Management • v3.1.2</p>
                </div>
                <button
                    onClick={() => loadData(true)}
                    disabled={refreshing}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-all text-sm font-semibold tracking-wide"
                >
                    <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Nav Tabs */}
            <div className="flex items-center gap-2">
                {(['HEALTH', 'INCIDENTS', 'ARCHIVES', 'LEARNING'] as const).map(tab => {
                    const isActive = activeTab === tab;
                    let activeStyles = "bg-slate-800 text-white border-slate-600 shadow-md";

                    if (isActive) {
                        if (tab === 'HEALTH') activeStyles = "bg-emerald-400/20 text-emerald-400 border-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.3)]";
                        if (tab === 'INCIDENTS') activeStyles = "bg-amber-400/20 text-amber-400 border-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.2)]";
                        if (tab === 'LEARNING') activeStyles = "bg-[#2ad8a0] text-slate-900 border-[#2ad8a0] font-bold shadow-[0_0_20px_rgba(42,216,160,0.5)]";
                        if (tab === 'ARCHIVES') activeStyles = "bg-blue-400/20 text-blue-400 border-blue-400 shadow-[0_0_15px_rgba(96,165,250,0.2)]";
                    } else {
                        activeStyles = "bg-slate-800/50 text-slate-400 border-slate-700 hover:bg-slate-800 hover:text-slate-300";
                    }

                    return (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-5 py-2.5 rounded-lg border text-xs tracking-widest font-bold transition-all flex items-center gap-2 ${activeStyles}`}
                        >
                            {tab === 'HEALTH' && <Activity className="w-3 h-3" />}
                            {tab === 'INCIDENTS' && <AlertTriangle className="w-3 h-3" />}
                            {tab === 'ARCHIVES' && <FileKey className="w-3 h-3" />}
                            {tab === 'LEARNING' && <Cpu className="w-3 h-3" />}

                            {tab === 'INCIDENTS' ? `INCIDENTS (${incidents.length})` : tab}
                        </button>
                    );
                })}
            </div>

            {/* TAB CONTENT: HEALTH */}
            {activeTab === 'HEALTH' && (
                <div className="space-y-6">
                    {/* Big Health Banner */}
                    <div className="bg-[#111827] border border-slate-700/50 rounded-2xl p-8 flex justify-between items-center shadow-lg">
                        <div className="space-y-2">
                            <h2 className="text-xl font-bold text-white mb-4">Overall System Health</h2>
                            <div className="text-7xl font-bold text-red-500 font-mono tracking-tighter">
                                {stats?.health_score?.toFixed(1) ?? 'N/A'}
                            </div>
                            <div className="pt-4 space-y-1">
                                <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Status:</span><span className={stats?.health_score && stats.health_score >= 80 ? "text-emerald-500" : "text-red-500"}>{stats?.health_score && stats.health_score >= 80 ? "OPERATIONAL" : "DEGRADED"}</span></p>
                                <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Mode:</span><span className="text-amber-500">{stats?.vanguard_mode?.replace('VanguardMode.', '') ?? 'SILENT_OBSERVER'}</span></p>
                                <p className="text-sm font-semibold"><span className="text-slate-500 mr-2">Role:</span><span className="text-blue-400">FOLLOWER</span></p>
                            </div>
                        </div>
                        <div className="mr-8">
                            <DoughnutScore score={stats?.health_score ?? 0} />
                        </div>
                    </div>

                    {/* Metric Row */}
                    <div className="grid grid-cols-4 gap-6">
                        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Active Incidents</div>
                            <div className="text-3xl font-bold text-amber-500">{stats?.active_incidents ?? '--'}</div>
                        </div>
                        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Resolved</div>
                            <div className="text-3xl font-bold text-emerald-500">{stats?.resolved_incidents ?? '--'}</div>
                        </div>
                        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Storage Used</div>
                            <div className="text-3xl font-bold text-blue-400">0.00 MB</div>
                        </div>
                        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Redis</div>
                            <div className="text-3xl font-bold font-mono text-red-500">X</div>
                        </div>
                    </div>

                    {/* Subsystems */}
                    <div className="pt-6">
                        <h3 className="text-lg font-bold text-white mb-4">Subsystems</h3>
                        <div className="grid grid-cols-3 gap-6">
                            {subSystemCheck("INQUISITOR", true, "Sample: 5%")}
                            {subSystemCheck("ARCHIVIST", true, "Retention: 7d")}
                            {subSystemCheck("PROFILER", true, "Model: gemini-2.0-flash")}
                            {subSystemCheck("SURGEON", false, "")}
                            {subSystemCheck("VACCINE", true, "")}
                        </div>
                    </div>
                </div>
            )}

            {/* TAB CONTENT: INCIDENTS */}
            {activeTab === 'INCIDENTS' && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between mb-6 pb-2 border-b border-slate-700/50">
                        <div className="flex items-center gap-4">
                            <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
                                <input
                                    type="checkbox"
                                    checked={selected.size === incidents.length && incidents.length > 0}
                                    onChange={selectAll}
                                    className="w-4 h-4 bg-slate-800 border-slate-600 rounded text-amber-500 focus:ring-amber-500/20"
                                />
                                Select All
                            </label>
                            <span className="text-sm text-slate-500">Sort by:</span>
                            <select className="bg-slate-800 border-slate-700 text-white text-sm rounded-lg px-3 py-1.5 focus:ring-0">
                                <option>Newest First</option>
                                <option>Oldest First</option>
                                <option>Highest Impact</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-4">
                            <button className="flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors font-bold text-sm shadow-[0_0_15px_rgba(147,51,234,0.3)]">
                                <Cpu className="w-4 h-4" /> Analyze All
                            </button>
                            <span className="text-sm text-slate-400">{incidents.length} active incidents</span>
                        </div>
                    </div>

                    {loading ? (
                        <div className="flex justify-center p-12 text-slate-500"><Loader2 className="animate-spin w-8 h-8" /></div>
                    ) : (
                        incidents.map(inc => (
                            <div key={inc.fingerprint} className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5 flex items-center gap-4 hover:border-slate-600 transition-colors">
                                <input
                                    type="checkbox"
                                    checked={selected.has(inc.fingerprint)}
                                    onChange={() => toggleSelect(inc.fingerprint)}
                                    className="w-4 h-4 bg-slate-900 border-slate-700 rounded text-amber-500"
                                />
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                                        <span className="text-white font-bold">{inc.error_type}</span>
                                        <span className="bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[10px] px-2 py-0.5 rounded font-black tracking-widest">{inc.severity.toUpperCase()}</span>
                                    </div>
                                    <div className="text-slate-400 font-mono text-sm ml-6">{inc.endpoint}</div>
                                    <div className="text-slate-500 text-xs ml-6 mt-2">
                                        Count: {inc.occurrence_count} | Last: {new Date(inc.last_seen).toLocaleString()}
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button className="px-4 py-2 rounded border border-purple-500/30 text-purple-400 hover:bg-purple-500/10 transition-colors text-xs font-bold tracking-wide flex items-center gap-2">
                                        <Cpu className="w-3 h-3" /> AI Analysis
                                    </button>
                                    <button className="px-4 py-2 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 transition-colors text-xs font-bold tracking-wide">
                                        Resolve
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}

            {/* TAB CONTENT: ARCHIVES */}
            {activeTab === 'ARCHIVES' && (
                <div className="flex flex-col items-center justify-center py-32 rounded-2xl bg-slate-800/30 border border-slate-700/50">
                    <FileKey className="w-16 h-16 text-slate-500 mb-6" />
                    <h2 className="text-white font-bold text-xl mb-2">Archive Management</h2>
                    <p className="text-slate-400">Weekly archives: 7 days retention</p>
                </div>
            )}

            {/* TAB CONTENT: LEARNING */}
            {activeTab === 'LEARNING' && (
                <div className="space-y-6">
                    <div className="grid grid-cols-4 gap-6">
                        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Total Resolutions</div>
                            <div className="text-3xl font-bold text-white">0</div>
                        </div>
                        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-emerald-500/70 uppercase tracking-wider mb-2">Verified</div>
                            <div className="text-3xl font-bold text-emerald-500">0</div>
                        </div>
                        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-amber-500/70 uppercase tracking-wider mb-2">Pending</div>
                            <div className="text-3xl font-bold text-amber-500">0</div>
                        </div>
                        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5">
                            <div className="text-xs text-blue-500/70 uppercase tracking-wider mb-2">Success Patterns</div>
                            <div className="text-3xl font-bold text-blue-400">0</div>
                        </div>
                    </div>

                    <div className="bg-slate-800/30 border border-slate-700/50 rounded-2xl p-6 min-h-[400px]">
                        <h3 className="text-white font-bold text-lg">Top Success Patterns</h3>
                        {/* Empty slate for now */}
                    </div>
                </div>
            )}

        </div>
    );
}
