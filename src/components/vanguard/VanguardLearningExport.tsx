import React, { useEffect, useState, useCallback } from 'react';
import { Loader2, Download, ShieldCheck, Database, Calendar } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

interface ExportLog {
    timestamp: string;
    file_name: string;
    size_mb: number;
    record_count: number;
}

export function VanguardLearningExportContent() {
    const [loading, setLoading] = useState(false);
    const [logs, setLogs] = useState<ExportLog[]>([]);
    const [statusText, setStatusText] = useState<string | null>(null);

    const loadHistory = useCallback(async () => {
        try {
            const res = await ApiContract.execute<{ exports: ExportLog[] }>(null, {
                path: 'vanguard/admin/learning/export-history'
            });
            setLogs(res.data?.exports || []);
        } catch (e) {
            console.error("Failed to load export history", e);
        }
    }, []);

    useEffect(() => {
        loadHistory();
    }, [loadHistory]);

    const handleExport = async () => {
        if (!confirm("Initiate Vanguard Learning Database Export?")) return;

        setLoading(true);
        setStatusText("Compiling RAG training dataset...");

        try {
            // Initiate the export on the backend
            const res = await ApiContract.execute<{ download_url?: string, training_data?: any, stats: any }>(null, {
                path: 'vanguard/admin/learning/export',
                options: { method: 'POST' }
            });

            setStatusText("Export complete. Generating download link...");

            // If the backend returned a URL (e.g., GCS signed URL), trigger the download
            if (res.data?.download_url) {
                const a = document.createElement('a');
                a.href = res.data.download_url;
                a.download = `vanguard_learning_export_${Date.now()}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            } else if (res.data?.training_data) {
                // Fallback: programmatic blob download from raw JSON response
                const blob = new Blob([JSON.stringify(res.data.training_data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `vanguard_learning_export_${Date.now()}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }

            // Refresh history after
            await loadHistory();

        } catch (e: any) {
            alert(`Export failed: ${e.message}`);
        } finally {
            setLoading(false);
            setStatusText(null);
        }
    };

    return (
        <div className="space-y-6">
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-6 relative overflow-hidden">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 relative z-10">
                    <div>
                        <h3 className="text-white font-bold text-lg flex items-center gap-2">
                            <Database className="w-5 h-5 text-cyan-400" />
                            Knowledge Base Export
                        </h3>
                        <p className="text-slate-400 text-sm mt-1 max-w-lg">
                            Export accumulated Vanguard resolutions for offline ML training.
                            Generates JSONL format optimized for Gemini few-shot priming.
                        </p>
                    </div>

                    <button
                        onClick={handleExport}
                        disabled={loading}
                        className="px-6 py-3 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-xl font-bold transition-colors flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(6,182,212,0.3)] whitespace-nowrap"
                    >
                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Download className="w-5 h-5" />}
                        Generate Training Set
                    </button>
                </div>

                {statusText && (
                    <div className="mt-4 text-cyan-400 text-sm font-mono animate-pulse w-full text-center sm:text-right bg-slate-900/50 py-2 rounded">
                        {statusText}
                    </div>
                )}
            </div>

            <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden relative">
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest px-6 py-4 border-b border-slate-700/50 bg-slate-900/50">
                    Recent Exports
                </h4>

                {logs.length === 0 ? (
                    <div className="p-8 text-center text-slate-500">
                        <Calendar className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p className="text-sm">No recent training exports found.</p>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-700/30">
                        {logs.map((log, i) => (
                            <div key={i} className="px-6 py-4 flex flex-col sm:flex-row justify-between sm:items-center gap-2 hover:bg-slate-800/30 transition-colors">
                                <div>
                                    <div className="font-mono text-cyan-300 text-sm">{log.file_name}</div>
                                    <div className="text-xs text-slate-500 mt-1">{new Date(log.timestamp).toLocaleString()}</div>
                                </div>
                                <div className="flex items-center gap-4 text-sm mt-2 sm:mt-0">
                                    <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-bold">
                                        {log.record_count} Records
                                    </span>
                                    <span className="text-slate-400 font-mono">
                                        {log.size_mb.toFixed(2)} MB
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

export const VanguardLearningExport = () => (
    <SectionErrorBoundary fallbackMessage="Learning Export UI offline">
        <VanguardLearningExportContent />
    </SectionErrorBoundary>
);
