import React, { useEffect, useState, useCallback } from 'react';
import { Archive, FileKey, ShieldAlert, Cpu } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

interface ArchiveLog {
    id: string;
    timestamp: string;
    description: string;
    level: string;
    component: string;
    metadata: Record<string, any>;
}

export function VanguardArchivesViewerContent() {
    const [loading, setLoading] = useState(false);
    const [archives, setArchives] = useState<ArchiveLog[]>([]);
    const [filter, setFilter] = useState('ALL');

    const loadArchives = useCallback(async () => {
        setLoading(true);
        try {
            const res = await ApiContract.execute<{ logs: ArchiveLog[] }>(null, {
                path: `vanguard/admin/archives?filter=${filter}`
            });
            setArchives(res.data?.logs || []);
        } catch (e) {
            console.error("Failed to load Vanguard archives", e);
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => {
        loadArchives();
    }, [loadArchives]);

    const getLevelColor = (level: string) => {
        switch (level) {
            case 'CRITICAL': return 'bg-red-500/10 border-red-500/30 text-red-500';
            case 'WARNING': return 'bg-amber-500/10 border-amber-500/30 text-amber-500';
            case 'INFO': return 'bg-blue-500/10 border-blue-500/30 text-blue-500';
            default: return 'bg-slate-500/10 border-slate-500/30 text-slate-400';
        }
    };

    const getComponentIcon = (comp: string) => {
        if (comp.includes('INQUISITOR')) return <ShieldAlert className="w-4 h-4 text-emerald-400" />;
        if (comp.includes('SURGEON')) return <Cpu className="w-4 h-4 text-purple-400" />;
        return <FileKey className="w-4 h-4 text-blue-400" />;
    };

    return (
        <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden relative">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-6 py-5 border-b border-slate-700/50 bg-slate-900/50">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
                        <Archive className="w-4 h-4 text-blue-400" />
                    </div>
                    <div>
                        <h3 className="text-white font-bold text-base">Security & Audit Logs</h3>
                        <p className="text-slate-500 text-xs">Immutable Vanguard operation history</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <select
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-1.5 focus:ring-blue-500/50"
                    >
                        <option value="ALL">All Events</option>
                        <option value="CRITICAL">Critical Actions</option>
                        <option value="SYST_MIGRATE">Migrations</option>
                        <option value="AURA_REDEPLOY">Redeploys</option>
                    </select>
                    <button
                        onClick={loadArchives}
                        className="text-blue-400 hover:text-blue-300 text-xs font-bold px-3 py-1.5 transition-colors"
                    >
                        REFRESH
                    </button>
                </div>
            </div>

            <div className="divide-y divide-slate-700/30 max-h-[600px] overflow-y-auto">
                {loading ? (
                    <div className="p-12 text-center text-slate-500 animate-pulse">Scanning archives...</div>
                ) : archives.length === 0 ? (
                    <div className="p-12 text-center text-slate-500 flex flex-col items-center">
                        <Archive className="w-10 h-10 mb-3 opacity-30" />
                        <p>No audit logs matching this filter.</p>
                    </div>
                ) : (
                    archives.map((log) => (
                        <div key={log.id} className="p-4 sm:p-5 flex gap-4 hover:bg-slate-800/30 transition-colors">
                            <div className="flex-shrink-0 mt-1">
                                {getComponentIcon(log.component)}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="font-black text-sm text-slate-200 truncate">
                                        {log.description}
                                    </span>
                                    <span className={`text-[9px] px-2 py-0.5 rounded border uppercase font-bold tracking-widest flex-shrink-0 ${getLevelColor(log.level)}`}>
                                        {log.level}
                                    </span>
                                </div>
                                <div className="flex items-center gap-3 text-xs">
                                    <span className="text-slate-500 font-mono">
                                        {new Date(log.timestamp).toLocaleString()}
                                    </span>
                                    <span className="text-slate-600">•</span>
                                    <span className="text-slate-400 font-mono tracking-widest">{log.component}</span>
                                </div>

                                {log.metadata && Object.keys(log.metadata).length > 0 && (
                                    <div className="mt-3 bg-black/40 border border-slate-700/50 rounded p-3 text-xs font-mono text-slate-400 overflow-x-auto">
                                        {JSON.stringify(log.metadata, null, 2)}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

export const VanguardArchivesViewer = () => (
    <SectionErrorBoundary fallbackMessage="Audit Archives Viewer offline">
        <VanguardArchivesViewerContent />
    </SectionErrorBoundary>
);
