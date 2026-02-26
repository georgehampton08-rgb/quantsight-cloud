import React from 'react'
import { Activity, ShieldCheck, Zap, BarChart3, LayoutDashboard } from 'lucide-react'
import { ApiContract } from '../api/client'
import { BoxScoreViewer } from '../components/dashboard/BoxScoreViewer'

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
                const res = await ApiContract.execute<any>('getSchedule', { path: 'schedule' });
                const data = res.data;

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
    const [activeTab, setActiveTab] = React.useState<'OVERVIEW' | 'BOXSCORE'>('OVERVIEW');

    return (
        <div className="p-4 sm:p-8 h-full overflow-y-auto w-full flex flex-col font-sans">
            <header className="mb-6 flex-shrink-0 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/30 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center backdrop-blur-sm shadow-inner">
                            <Activity className="w-6 h-6 text-indigo-400" />
                        </div>
                        Command Center
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-400 mt-2 font-medium tracking-wide">Operational Overview • {new Date().toLocaleDateString()}</p>
                </div>

                <div className="flex bg-slate-800/50 p-1.5 rounded-xl border border-slate-700/50 self-start sm:self-auto shadow-inner">
                    <button
                        onClick={() => setActiveTab('OVERVIEW')}
                        className={`px-4 sm:px-6 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-bold tracking-wider transition-all flex items-center gap-2 ${activeTab === 'OVERVIEW' ? 'bg-indigo-500/20 text-indigo-400 shadow-sm border border-indigo-500/30' : 'text-slate-500 hover:text-slate-300'}`}
                    >
                        <LayoutDashboard className="w-4 h-4" />
                        <span className="hidden sm:inline">OVERVIEW</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('BOXSCORE')}
                        className={`px-4 sm:px-6 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-bold tracking-wider transition-all flex items-center gap-2 ${activeTab === 'BOXSCORE' ? 'bg-emerald-500/20 text-emerald-400 shadow-sm border border-emerald-500/30' : 'text-slate-500 hover:text-slate-300'}`}
                    >
                        <BarChart3 className="w-4 h-4" />
                        <span className="hidden sm:inline">BOX SCORES</span>
                    </button>
                </div>
            </header>

            <div className="flex-1 min-h-0 flex flex-col">
                {activeTab === 'OVERVIEW' ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 auto-rows-fr animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
                        {/* Dramatic glow hidden behind the card */}
                        <div className="absolute top-1/2 left-1/4 w-96 h-96 bg-indigo-500/5 blur-[120px] rounded-full pointer-events-none" />

                        {/* Pillar 1: Today's Matchups */}
                        <DataCard title="Today's Matchups" icon={Zap}>
                            <ScheduleWidget />
                        </DataCard>

                        {/* Pillar 2: System Health Matrix */}
                        <DataCard title="System Health Matrix" icon={ShieldCheck}>
                            <div className="grid grid-cols-2 gap-4 h-full content-start">
                                <div className="bg-slate-900/40 p-4 rounded-xl text-center border border-slate-700/30 shadow-inner">
                                    <div className="text-[10px] text-slate-500 uppercase font-black tracking-widest mb-1.5 shadow-sm">API Latency</div>
                                    <div className="text-2xl font-black font-mono text-emerald-400 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]">42ms</div>
                                </div>
                                <div className="bg-slate-900/40 p-4 rounded-xl text-center border border-slate-700/30 shadow-inner">
                                    <div className="text-[10px] text-slate-500 uppercase font-black tracking-widest mb-1.5 shadow-sm">Model Drift</div>
                                    <div className="text-2xl font-black font-mono text-blue-400 drop-shadow-[0_0_8px_rgba(96,165,250,0.5)]">0.03%</div>
                                </div>
                                <div className="col-span-2 bg-emerald-950/20 p-4 rounded-xl text-center border border-emerald-500/30 relative overflow-hidden group">
                                    <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                                    <div className="text-sm text-emerald-400 uppercase font-black tracking-widest relative z-10">All Systems Operational</div>
                                </div>
                            </div>
                        </DataCard>

                        {/* Pillar 3: Quick Insights */}
                        <DataCard title="Quick Insights" icon={Activity}>
                            <div className="flex flex-col items-center justify-center p-12 h-full text-slate-500 bg-slate-900/30 rounded-xl border border-dashed border-slate-700/50">
                                <Activity className="w-12 h-12 mb-4 opacity-30 text-indigo-400" />
                                <div className="font-bold text-slate-400">AI-Generated Insights</div>
                                <div className="text-xs mt-1 font-mono uppercase tracking-widest">Coming Soon</div>
                            </div>
                        </DataCard>
                    </div>
                ) : (
                    <div className="animate-in fade-in flex-1 min-h-0">
                        <BoxScoreViewer />
                    </div>
                )}
            </div>
        </div>
    )
}
