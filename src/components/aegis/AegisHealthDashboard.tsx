import React from 'react';
import { Cpu, Database, Zap, Shield, TrendingUp, AlertTriangle } from 'lucide-react';
import { AegisApi, AegisHealthStatus } from '../../services/aegisApi';
import { NexusHealthPanel } from '../nexus/NexusHealthPanel';

interface StatusBadgeProps {
    status: string;
    size?: 'sm' | 'md' | 'lg';
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'sm' }) => {
    const colors: Record<string, string> = {
        healthy: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        degraded: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        critical: 'bg-red-500/20 text-red-400 border-red-500/30',
        down: 'bg-red-600/20 text-red-500 border-red-600/30',
        error: 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    };

    const sizeClasses = {
        sm: 'text-xs px-2 py-0.5',
        md: 'text-sm px-3 py-1',
        lg: 'text-base px-4 py-2'
    };

    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium uppercase tracking-wider ${colors[status] || colors.error} ${sizeClasses[size]}`}>
            <span className={`w-2 h-2 rounded-full ${status === 'healthy' ? 'bg-emerald-400 animate-pulse' : status === 'degraded' ? 'bg-yellow-400' : 'bg-red-400'}`} />
            {status}
        </span>
    );
};

interface MetricCardProps {
    icon: React.ReactNode;
    label: string;
    value: string | number;
    subValue?: string;
    color?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ icon, label, value, subValue, color = 'text-financial-accent' }) => (
    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50 hover:border-slate-600/50 transition-colors">
        <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg bg-slate-900/50 ${color}`}>
                {icon}
            </div>
            <div>
                <div className="text-xs text-slate-500 uppercase tracking-wider">{label}</div>
                <div className={`text-lg font-bold ${color}`}>{value}</div>
                {subValue && <div className="text-xs text-slate-500">{subValue}</div>}
            </div>
        </div>
    </div>
);

export default function AegisHealthDashboard() {
    const [health, setHealth] = React.useState<AegisHealthStatus | null>(null);
    const [loading, setLoading] = React.useState(true);
    const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null);

    const fetchHealth = React.useCallback(async () => {
        try {
            const data = await AegisApi.getHealth();
            setHealth(data);
            setLastUpdate(new Date());
        } catch (error) {
            console.error('Failed to fetch Aegis health:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    React.useEffect(() => {
        // Initial fetch
        fetchHealth();

        // Poll every 60 seconds (1 minute)
        const interval = setInterval(() => {
            // Only fetch if page is visible to avoid unnecessary API calls
            if (!document.hidden) {
                fetchHealth();
            }
        }, 60000);

        // Also fetch when page becomes visible again
        const handleVisibilityChange = () => {
            if (!document.hidden) {
                fetchHealth();
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            clearInterval(interval);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [fetchHealth]);

    if (loading) {
        return (
            <div className="p-6 rounded-xl border border-emerald-700/30 bg-emerald-900/10 animate-pulse">
                <div className="flex items-center gap-3 mb-4">
                    <Shield className="w-5 h-5 text-emerald-400" />
                    <span className="text-xs uppercase tracking-wider text-emerald-400 font-bold">Aegis System Status</span>
                </div>
                <div className="h-32 flex items-center justify-center text-slate-500">
                    Loading Aegis diagnostics...
                </div>
            </div>
        );
    }

    if (!health) {
        return (
            <div className="p-6 rounded-xl border border-red-700/30 bg-red-900/10">
                <div className="flex items-center gap-3 mb-4">
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                    <span className="text-xs uppercase tracking-wider text-red-400 font-bold">Aegis Offline</span>
                </div>
                <p className="text-sm text-slate-400">Unable to connect to Aegis router. Backend may not be running.</p>
            </div>
        );
    }

    return (
        <>
            <section className="p-6 rounded-xl border border-emerald-700/30 bg-emerald-900/10 space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Shield className="w-5 h-5 text-emerald-400" />
                        <span className="text-xs uppercase tracking-wider text-emerald-400 font-bold">Aegis System Status</span>
                    </div>
                    <div className="flex items-center gap-4">
                        <StatusBadge status={health.status} size="md" />
                        <button
                            onClick={fetchHealth}
                            className="text-xs text-slate-400 hover:text-emerald-400 transition-colors"
                        >
                            Refresh
                        </button>
                    </div>
                </div>

                {/* Uptime & Mode */}
                <div className="flex items-center gap-6 text-sm">
                    <div>
                        <span className="text-slate-500">Uptime:</span>
                        <span className="ml-2 text-white font-mono">{health.uptime}</span>
                    </div>
                    <div>
                        <span className="text-slate-500">Analysis Mode:</span>
                        <span className={`ml-2 font-mono ${health.analysis_mode === 'ml' ? 'text-purple-400' : health.analysis_mode === 'hybrid' ? 'text-blue-400' : 'text-emerald-400'}`}>
                            {health.analysis_mode?.toUpperCase() || 'UNKNOWN'}
                        </span>
                    </div>
                    <div>
                        <span className="text-slate-500">Vertex Engine:</span>
                        <span className={`ml-2 ${health.vertex_engine ? 'text-emerald-400' : 'text-red-400'}`}>
                            {health.vertex_engine ? 'ACTIVE' : 'OFFLINE'}
                        </span>
                    </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard
                        icon={<Database className="w-4 h-4" />}
                        label="Cache Hit Rate"
                        value={health.router?.cache_hit_rate || '0%'}
                        subValue={`${health.router?.cache_hits || 0} hits / ${health.router?.cache_misses || 0} misses`}
                        color="text-emerald-400"
                    />
                    <MetricCard
                        icon={<Zap className="w-4 h-4" />}
                        label="Rate Tokens"
                        value={`${health.rate_limiting?.tokens_available || 0}/${health.rate_limiting?.max_tokens || 0}`}
                        subValue={health.rate_limiting?.emergency_mode ? '⚠️ Emergency Mode' : 'Normal'}
                        color={health.rate_limiting?.emergency_mode ? 'text-red-400' : 'text-blue-400'}
                    />
                    <MetricCard
                        icon={<Cpu className="w-4 h-4" />}
                        label="System Load"
                        value={`${(health.system?.cpu_percent || 0).toFixed(1)}%`}
                        subValue={`${(health.system?.memory_percent || 0).toFixed(1)}% memory`}
                        color={(health.system?.cpu_percent || 0) > 80 ? 'text-red-400' : 'text-cyan-400'}
                    />
                    <MetricCard
                        icon={<TrendingUp className="w-4 h-4" />}
                        label="Storage"
                        value={health.storage?.success_rate || '0%'}
                        subValue={`${health.storage?.writes_succeeded || 0} writes`}
                        color="text-orange-400"
                    />
                </div>

                {/* Detailed Stats Row */}
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-700/50">
                    <div className="text-center">
                        <div className="text-2xl font-bold text-white">{health.router?.api_calls || 0}</div>
                        <div className="text-xs text-slate-500 uppercase">API Calls</div>
                    </div>
                    <div className="text-center">
                        <div className="text-2xl font-bold text-white">{health.router?.integrity_failures || 0}</div>
                        <div className="text-xs text-slate-500 uppercase">Integrity Failures</div>
                    </div>
                    <div className="text-center">
                        <div className="text-2xl font-bold text-white">{health.rate_limiting?.requests_last_minute || 0}</div>
                        <div className="text-xs text-slate-500 uppercase">Req/Min</div>
                    </div>
                </div>

                {/* Footer */}
                {lastUpdate && (
                    <div className="text-xs text-slate-600 text-right">
                        Last updated: {lastUpdate.toLocaleTimeString()}
                    </div>
                )}
            </section>

            {/* Nexus Hub Health Panel */}
            <div className="mt-6">
                <NexusHealthPanel />
            </div>
        </>
    );
}
