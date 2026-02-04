import { RefreshCw } from 'lucide-react';

interface DataProvenanceBadgeProps {
    status: 'fresh' | 'stale' | 'live';
    lastUpdated: string; // ISO date string
    source: 'cached' | 'live';
    onRefresh?: () => void;
    isRefreshing?: boolean;
}

export default function DataProvenanceBadge({
    status,
    lastUpdated,
    source,
    onRefresh,
    isRefreshing = false
}: DataProvenanceBadgeProps) {
    const statusConfig = {
        fresh: { color: 'bg-emerald-500', label: 'Fresh' },
        stale: { color: 'bg-orange-500', label: 'Stale' },
        live: { color: 'bg-blue-500', label: 'Just Updated' }
    };

    const config = statusConfig[status];
    const formattedDate = new Date(lastUpdated).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });

    return (
        <div className="flex items-center justify-between px-4 py-3 bg-slate-900/60 border-t border-slate-700/50 rounded-b-xl backdrop-blur-sm">
            <div className="flex items-center gap-3">
                {/* Status Dot */}
                <div className={`w-2 h-2 rounded-full ${config.color} animate-pulse`}></div>

                {/* Timestamp */}
                <span className="text-xs text-slate-400">
                    Stats current as of: <span className="text-slate-300 font-medium">{formattedDate}</span>
                </span>

                {/* Source Badge */}
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold tracking-wider ${source === 'live'
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                    : 'bg-slate-700/50 text-slate-400 border border-slate-600/30'
                    }`}>
                    {source === 'live' ? 'LIVE' : 'CACHED'}
                </span>
            </div>

            {/* Refresh Button */}
            {onRefresh && (
                <button
                    onClick={onRefresh}
                    disabled={isRefreshing}
                    className="p-1.5 rounded-full hover:bg-slate-800/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Force refresh data"
                >
                    <RefreshCw
                        size={14}
                        className={`text-slate-400 hover:text-financial-accent transition-colors ${isRefreshing ? 'animate-spin' : ''
                            }`}
                    />
                </button>
            )}
        </div>
    );
}
