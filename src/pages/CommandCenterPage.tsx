import React from 'react'
import { Activity, ShieldCheck, Zap } from 'lucide-react'

// Placeholder components - in a real app these would be their own widgets
const DataCard = ({ title, icon: Icon, children }: { title: string, icon: any, children: React.ReactNode }) => (
    <div className="glass-panel rounded-xl p-6 flex flex-col gap-4 h-full hover:border-financial-accent/30 transition-all duration-300 hover:shadow-lg hover:shadow-blue-900/20 group">
        <div className="flex items-center gap-2 text-slate-400 font-medium tracking-wider text-sm uppercase flex-shrink-0 group-hover:text-financial-accent transition-colors">
            <Icon className="w-4 h-4 text-financial-accent" />
            {title}
        </div>
        <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {children}
        </div>
    </div>
)

const ScheduleWidget = () => {
    const [games, setGames] = React.useState<any[]>([]);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        const load = async () => {
            try {
                let data;
                const isDev = window.location.hostname === 'localhost' && window.location.port === '5173';

                if (!isDev && window.electronAPI?.getSchedule) {
                    console.log('[Schedule] Loading via Electron IPC');
                    data = await window.electronAPI.getSchedule();

                    // Fallback to HTTP if IPC returns nothing
                    if (!data || !data.games) {
                        console.warn('[Schedule] IPC returned no data, falling back to direct HTTP');
                        const res = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/schedule');
                        if (res.ok) {
                            data = await res.json();
                        }
                    }
                } else {
                    console.log('[Schedule] Loading via direct HTTP');
                    const res = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/schedule');
                    data = await res.json();
                }

                if (data && data.games) {
                    console.log(`[Schedule] Loaded ${data.games.length} games`);
                    setGames(data.games);
                } else {
                    console.warn('[Schedule] No games in response:', data);
                }
            } catch (e) {
                console.error('[Schedule] Failed to load:', e);
            }
            setLoading(false);
        };
        load();
    }, []);

    if (loading) return <div className="text-xs text-slate-500 animate-pulse">Scanning League Data...</div>;
    if (games.length === 0) return <div className="text-xs text-slate-500">No games scheduled.</div>;

    return (
        <div className="space-y-4">
            {games.map((game, idx) => {
                const isLive = game.status === 'LIVE';
                const isFinal = game.status === 'FINAL';
                const hasStarted = game.started || isLive || isFinal;
                const hasScores = hasStarted && (game.home_score > 0 || game.away_score > 0);

                return (
                    <div key={idx} className={`p-3 bg-slate-900/50 rounded border-l-2 ${isLive ? 'border-red-500' : game.volatility === 'High' ? 'border-green-500' : 'border-slate-700'}`}>
                        <div className="flex justify-between items-center mb-1">
                            {hasScores ? (
                                <span className="font-bold text-white">
                                    {game.away} <span className="text-financial-accent">{game.away_score}</span> @ {game.home} <span className="text-financial-accent">{game.home_score}</span>
                                </span>
                            ) : (
                                <span className="font-bold text-white">{game.away} @ {game.home}</span>
                            )}
                            <div className="flex items-center gap-2">
                                {/* Status indicator */}
                                {isLive && (
                                    <span className="text-xs text-red-400 animate-pulse flex items-center gap-1">
                                        <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
                                        {game.time}
                                    </span>
                                )}
                                {isFinal && (
                                    <span className="text-xs text-slate-400">{game.time}</span>
                                )}
                                {!isLive && !isFinal && (
                                    <span className={`text-xs ${hasStarted ? 'text-amber-400' : 'text-slate-400'}`}>
                                        {hasStarted && <span className="mr-1">▶</span>}
                                        {game.time}
                                    </span>
                                )}
                            </div>
                        </div>
                        {/* Additional game info */}
                        {isLive && (
                            <div className="text-xs text-red-400/80">Live Game • High Volatility</div>
                        )}
                        {hasStarted && !isLive && !isFinal && (
                            <div className="text-xs text-amber-400/80">Started • Check for updates</div>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

export default function CommandCenterPage() {
    return (
        <div className="p-8 h-full overflow-y-auto">
            <header className="mb-8 flex-shrink-0">
                <h1 className="text-3xl font-bold text-gray-100 flex items-center gap-3">
                    <Activity className="w-8 h-8 text-financial-accent" />
                    Command Center
                </h1>
                <p className="text-slate-400 mt-2">Operational Overview • {new Date().toLocaleDateString()}</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 auto-rows-fr animate-fade-in-up">
                {/* Pillar 1: Today's Matchups */}
                <DataCard title="Today's Matchups" icon={Zap}>
                    <ScheduleWidget />
                </DataCard>

                {/* Pillar 2: System Health Matrix */}
                <DataCard title="System Health Matrix" icon={ShieldCheck}>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-slate-900/50 p-3 rounded text-center">
                            <div className="text-xs text-slate-500 uppercase mb-1">API Latency</div>
                            <div className="text-xl font-mono text-green-400">42ms</div>
                        </div>
                        <div className="bg-slate-900/50 p-3 rounded text-center">
                            <div className="text-xs text-slate-500 uppercase mb-1">Model Drift</div>
                            <div className="text-xl font-mono text-blue-400">0.03%</div>
                        </div>
                        <div className="col-span-2 bg-slate-900/50 p-3 rounded text-center border border-green-500/20">
                            <div className="text-xs text-green-500 uppercase font-bold">All Systems Operational</div>
                        </div>
                    </div>
                </DataCard>

                {/* Pillar 3: Quick Insights */}
                <DataCard title="Quick Insights" icon={Activity}>
                    <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                        <div className="text-center space-y-2">
                            <Activity className="w-8 h-8 mx-auto opacity-30" />
                            <div>AI-Generated Insights</div>
                            <div className="text-xs opacity-50">Coming Soon</div>
                        </div>
                    </div>
                </DataCard>
            </div>
        </div>
    )
}
