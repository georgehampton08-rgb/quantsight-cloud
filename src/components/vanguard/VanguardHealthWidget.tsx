import React, { useEffect, useState, useCallback } from 'react';
import { Shield, AlertTriangle, Loader2 } from 'lucide-react';
import { ApiContract } from '../../api/client';

interface VanguardStats {
    active_incidents: number;
    resolved_incidents: number;
    health_score: number;
    vanguard_mode: string;
}

export function VanguardHealthWidget() {
    const [stats, setStats] = useState<VanguardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    const loadData = useCallback(async () => {
        setError(false);
        try {
            const res = await ApiContract.execute<VanguardStats>(null, {
                path: 'vanguard/admin/stats'
            });
            if (res.data) {
                setStats(res.data);
            } else {
                setError(true);
            }
        } catch {
            setError(true);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
        const interval = setInterval(loadData, 30000);
        return () => clearInterval(interval);
    }, [loadData]);

    const healthColor = (score: number | undefined) => {
        if (score === undefined) return 'text-slate-500';
        if (score >= 80) return 'text-emerald-500';
        if (score >= 50) return 'text-amber-400';
        return 'text-red-400';
    };

    const statusText = (score: number | undefined) => {
        if (score === undefined) return '—';
        if (score >= 80) return 'OPERATIONAL';
        if (score >= 50) return 'DEGRADED';
        return 'CRITICAL';
    };

    const modeDisplay = (mode: string | undefined) => {
        if (!mode) return '—';
        return mode.replace('VanguardMode.', '').toUpperCase();
    };

    if (loading) {
        return (
            <div className="p-5 sm:p-6 rounded-xl border border-emerald-500/30 bg-pro-surface animate-pulse relative shadow-sm" >
                
                <div className="flex items-center gap-3 relative z-10">
                    <Shield className="w-5 h-5 text-emerald-500" />
                    <span className="text-sm font-medium font-semibold tracking-wide text-emerald-500 uppercase">Vanguard Sovereign Health</span>
                </div>
                <div className="mt-4 flex items-center justify-center py-4 relative z-10">
                    <Loader2 className="w-6 h-6 animate-spin text-pro-muted" />
                </div>
            </div>
        );
    }

    return (
        <div className="p-5 sm:p-6 rounded-xl border border-emerald-500/30 bg-pro-bg relative font-sans shadow-sm" >
            
            <div className="flex flex-col gap-1 mb-5 sm:mb-6 relative z-10">
                <div className="flex items-center gap-2">
                    <Shield className="w-5 h-5 text-emerald-500" />
                    <span className="text-sm font-medium font-semibold tracking-wide text-emerald-500 uppercase">Vanguard Sovereign Health</span>
                    {stats && stats.health_score < 80 && <AlertTriangle className="w-4 h-4 text-amber-500 ml-1" />}
                </div>
                <p className="text-xs font-mono text-pro-muted mt-1 uppercase tracking-wide">
                    {error ? 'Could not reach backend — check deployment.' : 'Monitoring active endpoints. Cloud persistence via Firestore.'}
                </p>
            </div>

            {/* Top 4 tiles — 2-col on mobile, 4-col on desktop */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 relative z-10">
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-3">
                    <div className="text-xs font-mono text-pro-muted uppercase tracking-wide mb-1">Health Score</div>
                    <div className={`text-xl font-mono ${healthColor(stats?.health_score)?.replace('emerald', 'qs-green').replace('amber', 'qs-gold') || 'text-emerald-500'}`}>
                        {stats?.health_score !== undefined ? `${stats.health_score.toFixed(0)}%` : '—'}
                    </div>
                </div>
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-3">
                    <div className="text-xs font-mono text-pro-muted uppercase tracking-wide mb-1">Status</div>
                    <div className={`text-xs font-mono mt-1.5 uppercase tracking-wide ${healthColor(stats?.health_score)?.replace('emerald', 'qs-green').replace('amber', 'qs-gold') || 'text-emerald-500'}`}>
                        {statusText(stats?.health_score)}
                    </div>
                </div>
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-3">
                    <div className="text-xs font-mono text-pro-muted uppercase tracking-wide mb-1">Active</div>
                    <div className="text-xl font-mono text-amber-500">
                        {stats?.active_incidents ?? '—'}
                    </div>
                </div>
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-3">
                    <div className="text-xs font-mono text-pro-muted uppercase tracking-wide mb-1">Resolved</div>
                    <div className="text-xl font-mono text-emerald-500">
                        {stats?.resolved_incidents ?? '—'}
                    </div>
                </div>
            </div>

            {/* Bottom row */}
            <div className="mt-3 sm:mt-4 relative z-10">
                <div className="bg-white/[0.02] border border-pro-border/50 rounded-xl p-3">
                    <div className="text-xs font-mono text-pro-muted uppercase tracking-wide mb-1">Operating Mode</div>
                    <div className="text-xs font-mono text-amber-500 uppercase tracking-wide mt-1">
                        {modeDisplay(stats?.vanguard_mode)}
                    </div>
                </div>
            </div>
        </div>
    );
}
