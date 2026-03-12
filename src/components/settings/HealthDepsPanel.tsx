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
        <div className="flex items-center justify-between py-2 border-b border-pro-border/50 last:border-0 text-sm">
            <span className="text-pro-text font-mono text-xs uppercase tracking-wide truncate pr-4">{name}</span>
            <span className={`flex-shrink-0 px-2 py-0.5 rounded-xl text-xs font-mono font-bold uppercase tracking-wide ${isHealthy ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/30' : 'bg-red-500/10 text-red-500 border border-red-500/30'}`}>
                {displayStatus}
            </span>
        </div>
    );
};

const BooleanStatusRow = ({ name, ok }: { name: string, ok: boolean }) => (
    <div className="flex items-center justify-between py-2 border-b border-pro-border/50 last:border-0 text-sm">
        <span className="text-pro-text font-mono text-xs uppercase tracking-wide">{name}</span>
        {ok ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
        ) : (
            <XCircle className="w-4 h-4 text-red-500" />
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
            <div className="p-6 rounded-xl border border-pro-border bg-white/[0.02] animate-pulse text-center space-y-3 relative shadow-sm">
                
                <Activity className="w-6 h-6 text-pro-muted mx-auto animate-spin relative z-10" />
                <div className="text-pro-muted font-mono text-xs uppercase tracking-wide relative z-10">Scanning System Dependencies...</div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="p-6 rounded-xl border border-red-500/30 bg-red-500/10 relative shadow-sm">
                
                <div className="text-red-500 font-medium font-bold uppercase tracking-wide mb-2 relative z-10">Dependency Audit Failed</div>
                <div className="text-xs font-mono text-pro-muted mb-4 uppercase tracking-wide relative z-10">{error}</div>
                <button onClick={loadData} className="px-4 py-2 bg-red-500/10 border border-red-500 hover:bg-red-500/20 rounded-xl text-xs font-mono font-bold text-red-500 uppercase tracking-wide transition-colors relative z-10">
                    Retry Scan
                </button>
            </div>
        );
    }

    return (
        <section className="p-6 rounded-xl border border-pro-border bg-pro-surface relative shadow-sm" >
            
            <div className="flex items-center justify-between mb-5 relative z-10">
                <h3 className="text-xs tracking-wide text-emerald-500 font-medium font-bold uppercase flex items-center gap-2">
                    <Server className="w-4 h-4 text-emerald-500" />
                    System Dependencies
                </h3>
                <button onClick={loadData} className="text-xs font-mono text-pro-muted uppercase tracking-wide hover:text-pro-text transition-colors">
                    Refresh
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative z-10">
                {/* Core Infrastructure */}
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-4 relative shadow-sm">
                    <h4 className="text-xs text-pro-muted font-medium font-semibold uppercase tracking-wide mb-3 flex items-center gap-2 border-b border-pro-border/50 pb-2">
                        <Database className="w-3.5 h-3.5 text-pro-muted" />
                        Infrastructure
                    </h4>
                    <div className="space-y-1">
                        <BooleanStatusRow name="OpenTelemetry" ok={!!data.otel_ok} />
                        <BooleanStatusRow name="BigTable" ok={!!data.bigtable_ok} />
                        <BooleanStatusRow name="ML Classifier" ok={!!data.ml_classifier_ok} />
                    </div>
                </div>

                {/* Microservices */}
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-4 relative shadow-sm">
                    <h4 className="text-xs text-pro-muted font-medium font-semibold uppercase tracking-wide mb-3 flex items-center gap-2 border-b border-pro-border/50 pb-2">
                        <ActivityIcon className="w-3.5 h-3.5 text-pro-muted" />
                        Microservices
                    </h4>
                    <div className="space-y-1">
                        {Object.entries(data.services || {}).map(([name, status]) => (
                            <ServiceStatusRow key={name} name={name} status={status as string} />
                        ))}
                    </div>
                </div>

                {/* Scale Monitors */}
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-4 md:col-span-2 relative shadow-sm">
                    <h4 className="text-xs text-pro-muted font-medium font-semibold uppercase tracking-wide mb-3 flex items-center gap-2 border-b border-pro-border/50 pb-2">
                        <HardDrive className="w-3.5 h-3.5 text-pro-muted" />
                        Scale Monitors & Routing
                    </h4>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
                        <div className="space-y-1 pr-4 border-r border-pro-border/30">
                            <div className="text-xs font-mono text-pro-muted mb-2 uppercase tracking-wide">Monitors</div>
                            {Object.entries(data.scale_monitors || {}).map(([name, status]) => (
                                <ServiceStatusRow key={name} name={name} status={status as string} />
                            ))}
                        </div>

                        <div className="space-y-1 pl-2">
                            <div className="text-xs font-mono text-pro-muted mb-2 uppercase tracking-wide">Routing Strategy</div>
                            <div className="bg-[#0b1120] p-4 rounded-xl border border-pro-border/30 text-emerald-500 font-mono text-xs overflow-x-auto">
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
