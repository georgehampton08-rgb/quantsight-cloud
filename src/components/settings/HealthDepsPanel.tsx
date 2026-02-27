import React, { useEffect, useState, useCallback } from 'react';
import { Activity, Server, Database, Activity as ActivityIcon, HardDrive, CheckCircle2, XCircle } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

interface HealthDepsData {
    routing_table: string | Record<string, unknown>;
    scale_monitors: Record<string, string | object>;
    services: Record<string, string | object>;
    otel_ok: boolean;
    bigtable_ok: boolean;
    ml_classifier_ok: boolean;
}

const ServiceStatusRow = ({ name, status }: { name: string, status: string | object }) => {
    // If status is an object (e.g. from circuit breakers or fallbacks), extract a meaningful string or stringify it
    let displayStatus = 'UNKNOWN';
    if (typeof status === 'string') {
        displayStatus = status;
    } else if (status && typeof status === 'object') {
        if ('status' in status) {
            displayStatus = (status as any).status;
        } else {
            displayStatus = 'ACTIVE'; // Fallback for things like {active_fallbacks: ...}
        }
    }

    const isHealthy = displayStatus === 'HEALTHY' || displayStatus === 'OK' || displayStatus === 'ACTIVE';
    return (
        <div className="flex items-center justify-between py-2 border-b border-slate-700/30 last:border-0 text-sm">
            <span className="text-slate-300 font-medium truncate pr-4">{name}</span>
            <span className={`flex-shrink-0 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${isHealthy ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                {displayStatus}
            </span>
        </div>
    );
};

const BooleanStatusRow = ({ name, ok }: { name: string, ok: boolean }) => (
    <div className="flex items-center justify-between py-2 border-b border-slate-700/30 last:border-0 text-sm">
        <span className="text-slate-300 font-medium">{name}</span>
        {ok ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        ) : (
            <XCircle className="w-4 h-4 text-red-400" />
        )}
    </div>
);

function HealthDepsPanelContent() {
    const [data, setData] = useState<HealthDepsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await ApiContract.execute<HealthDepsData>(null, {
                path: 'health/deps'
            });
            setData(res.data);
        } catch (e: any) {
            setError(e.message || "Failed to load health dependencies");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    if (loading) {
        return (
            <div className="p-6 rounded-xl border border-slate-700/50 bg-slate-800/20 animate-pulse text-center space-y-3">
                <Activity className="w-6 h-6 text-slate-500 mx-auto animate-spin" />
                <div className="text-slate-400 text-sm">Scanning System Dependencies...</div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="p-6 rounded-xl border border-red-900/30 bg-red-900/10">
                <div className="text-red-400 font-bold mb-2">Dependency Audit Failed</div>
                <div className="text-sm text-slate-400 mb-4">{error}</div>
                <button onClick={loadData} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded text-sm text-slate-300 transition-colors">
                    Retry Scan
                </button>
            </div>
        );
    }

    return (
        <section className="p-6 rounded-xl border border-slate-700/50 bg-[#121b2d]">
            <div className="flex items-center justify-between mb-5">
                <h3 className="text-xs tracking-widest text-[#2ad8a0] font-bold uppercase flex items-center gap-2">
                    <Server className="w-4 h-4" />
                    System Dependencies
                </h3>
                <button onClick={loadData} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
                    Refresh
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Core Infrastructure */}
                <div className="bg-[#1a253a] border border-slate-700/30 rounded-lg p-4">
                    <h4 className="text-xs text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                        <Database className="w-3.5 h-3.5" />
                        Infrastructure
                    </h4>
                    <div className="space-y-1">
                        <BooleanStatusRow name="OpenTelemetry" ok={!!data.otel_ok} />
                        <BooleanStatusRow name="BigTable" ok={!!data.bigtable_ok} />
                        <BooleanStatusRow name="ML Classifier" ok={!!data.ml_classifier_ok} />
                    </div>
                </div>

                {/* Microservices */}
                <div className="bg-[#1a253a] border border-slate-700/30 rounded-lg p-4">
                    <h4 className="text-xs text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                        <ActivityIcon className="w-3.5 h-3.5" />
                        Microservices
                    </h4>
                    <div className="space-y-1">
                        {Object.entries(data.services || {}).map(([name, status]) => (
                            <ServiceStatusRow key={name} name={name} status={status as string} />
                        ))}
                    </div>
                </div>

                {/* Scale Monitors */}
                <div className="bg-[#1a253a] border border-slate-700/30 rounded-lg p-4 md:col-span-2">
                    <h4 className="text-xs text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                        <HardDrive className="w-3.5 h-3.5" />
                        Scale Monitors & Routing
                    </h4>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <div className="text-[10px] text-slate-500 mb-1 uppercase tracking-wider">Monitors</div>
                            {Object.entries(data.scale_monitors || {}).map(([name, status]) => (
                                <ServiceStatusRow key={name} name={name} status={status as string} />
                            ))}
                        </div>

                        <div className="space-y-1">
                            <div className="text-[10px] text-slate-500 mb-1 uppercase tracking-wider">Routing Strategy</div>
                            <div className="bg-slate-900/50 p-3 rounded border border-slate-700/30 text-emerald-400 font-mono text-sm">
                                {typeof data.routing_table === 'string'
                                    ? (data.routing_table || 'LOCAL_EXECUTION')
                                    : typeof data.routing_table === 'object' && data.routing_table !== null
                                        ? JSON.stringify(data.routing_table, null, 2)
                                        : 'LOCAL_EXECUTION'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}

export const HealthDepsPanel = () => (
    <SectionErrorBoundary fallbackMessage="Health Dependencies Panel offline">
        <HealthDepsPanelContent />
    </SectionErrorBoundary>
);
