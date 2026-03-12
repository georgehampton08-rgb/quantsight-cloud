import React from 'react'
import { Activity, ShieldCheck, Zap, BarChart3, LayoutDashboard, TrendingUp, AlertTriangle, Star, Stethoscope } from 'lucide-react'
import { ApiContract } from '../api/client'
import { BoxScoreViewer } from '../components/dashboard/BoxScoreViewer'
import { PlayByPlayFeed } from '../components/PlayByPlay/PlayByPlayFeed'
import { API_BASE } from '../config/apiConfig'

// Placeholder components - in a real app these would be their own widgets
const DataCard = ({ title, icon: Icon, children }: { title: string, icon: any, children: React.ReactNode }) => (
    <div className="glass-panel rounded-xl p-4 sm:p-6 flex flex-col gap-4 min-w-0 min-h-[280px] sm:min-h-[350px] lg:min-h-0 lg:h-full hover:border-financial-accent/30 transition-all duration-300 hover:shadow-lg hover:shadow-blue-900/20 group">
        <div className="flex items-center gap-2 text-slate-400 font-medium tracking-wider text-sm uppercase flex-shrink-0 group-hover:text-financial-accent transition-colors">
            <Icon className="w-4 h-4 text-financial-accent" />
            {title}
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-700 hover:scrollbar-thumb-slate-500 scrollbar-track-transparent">
            {children}
        </div>
    </div>
)

// ─── Today's Injuries Widget ──────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
    Out:          'bg-red-500/20 text-red-400 border-red-500/30',
    Questionable: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    Doubtful:     'bg-orange-500/20 text-orange-400 border-orange-500/30',
    'Day-To-Day': 'bg-yellow-500/15 text-yellow-400 border-yellow-500/25',
    Probable:     'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
};
const statusColor = (s: string) => STATUS_COLORS[s] ?? 'bg-slate-700/40 text-slate-400 border-slate-600/30';

const TodayInjuriesWidget = () => {
    const [injuries, setInjuries] = React.useState<Record<string, any[]>>({});
    const [loading, setLoading]   = React.useState(true);
    const [count, setCount]       = React.useState(0);

    React.useEffect(() => {
        fetch(`${API_BASE}/v1/games/injuries/today`)
            .then(r => r.ok ? r.json() : Promise.reject())
            .then(d => {
                // Group by team tricode
                const byTeam: Record<string, any[]> = {};
                (d.injuries ?? []).forEach((inj: any) => {
                    const t = inj.teamTricode ?? inj.team ?? 'UNK';
                    if (!byTeam[t]) byTeam[t] = [];
                    byTeam[t].push(inj);
                });
                setInjuries(byTeam);
                setCount(d.injuries?.length ?? 0);
            })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="text-xs text-slate-500 animate-pulse">Fetching injury reports...</div>;

    if (count === 0) return (
        <div className="flex flex-col items-center justify-center h-full gap-2 text-slate-600">
            <Stethoscope className="w-7 h-7 opacity-30" />
            <div className="text-xs">No injury reports for today</div>
        </div>
    );

    return (
        <div className="flex flex-col gap-4">
            {Object.entries(injuries).map(([team, players]) => (
                <div key={team}>
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">
                        {team}
                    </div>
                    <div className="flex flex-col gap-1">
                        {players.map((inj: any) => (
                            <div key={inj.playerId ?? inj.playerName}
                                className="flex items-center gap-2 px-2 py-1.5 bg-slate-900/50 rounded-lg border border-slate-800/60">
                                <span className={`flex-shrink-0 text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wide ${statusColor(inj.status)}`}>
                                    {inj.status === 'Day-To-Day' ? 'DTD' : (inj.status ?? '?').charAt(0)}
                                </span>
                                <div className="flex flex-col min-w-0">
                                    <span className="text-[11px] font-semibold text-slate-200 truncate leading-tight">{inj.playerName}</span>
                                    {inj.injuryType && <span className="text-[10px] text-slate-500 truncate leading-tight">{inj.injuryType}</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
            <div className="text-[9px] text-slate-700 text-right">via ESPN • updates hourly</div>
        </div>
    );
};

// ─── AI Insights Widget ───────────────────────────────────────────────────────

interface DailyInsight {
    headline: string;
    bullets: string[];
    top_watch: { player: string; team: string; stat: string; reason: string } | null;
    risk_flag: { player: string; reason: string; severity: string } | null;
    ai_powered: boolean;
    generated_at?: string;
    games_tonight?: number;
    cached?: boolean;
}

const InsightsWidget = () => {
    const [insight, setInsight] = React.useState<DailyInsight | null>(null);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
        fetch(`${API_BASE}/api/insights/daily`)
            .then(r => r.ok ? r.json() : Promise.reject(`Server error ${r.status}`))
            .then(d => { setInsight(d); setLoading(false); })
            .catch(err => { setError(String(err)); setLoading(false); });
    }, []);

    if (loading) return (
        <div className="space-y-3 animate-pulse">
            <div className="h-4 bg-slate-700/60 rounded-full w-3/4" />
            <div className="h-3 bg-slate-700/60 rounded-full w-full" />
            <div className="h-3 bg-slate-700/60 rounded-full w-5/6" />
            <div className="h-3 bg-slate-700/60 rounded-full w-4/6" />
        </div>
    );

    if (error || !insight) return (
        <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2 text-center">
            <AlertTriangle className="w-8 h-8 opacity-40 text-amber-500" />
            <div className="text-xs">Insights offline — refreshes in 30 min</div>
        </div>
    );

    const severityColor = insight.risk_flag?.severity === 'HIGH' ? 'text-red-400 bg-red-500/10 border-red-500/20'
        : insight.risk_flag?.severity === 'MEDIUM' ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
            : 'text-slate-400 bg-slate-700/30 border-slate-600/20';

    return (
        <div className="flex flex-col gap-3 h-full text-sm">
            {/* Headline */}
            <div className="text-indigo-300 font-semibold leading-snug drop-shadow-[0_0_8px_rgba(165,180,252,0.3)]">
                {insight.headline}
            </div>

            {/* Bullets */}
            <div className="space-y-1.5 flex-1">
                {(insight.bullets || []).map((b, i) => (
                    <div key={i} className="flex gap-2 items-start">
                        <span className="text-[10px] font-black font-mono text-emerald-500 mt-0.5 flex-shrink-0">
                            {String(i + 1).padStart(2, '0')}
                        </span>
                        <span className="text-slate-300 text-xs leading-relaxed">{b}</span>
                    </div>
                ))}
            </div>

            {/* Top Watch */}
            {insight.top_watch && (
                <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                    <Star className="w-3 h-3 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                        <div className="flex flex-wrap items-baseline gap-x-1">
                            <span className="text-emerald-400 text-xs font-bold">{insight.top_watch.player}</span>
                            <span className="text-slate-400 text-xs">({insight.top_watch.team}) — {insight.top_watch.stat}</span>
                        </div>
                        <div className="text-slate-400 text-[11px] leading-relaxed mt-0.5">{insight.top_watch.reason}</div>
                    </div>
                </div>
            )}

            {/* Risk Flag */}
            {insight.risk_flag && (
                <div className={`flex items-start gap-2 px-3 py-2.5 rounded-lg border ${severityColor}`}>
                    <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                        <span className="text-xs font-bold">{insight.risk_flag.player}</span>
                        <div className="text-[11px] leading-relaxed mt-0.5 opacity-90">{insight.risk_flag.reason}</div>
                    </div>
                </div>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between text-[10px] text-slate-600 border-t border-slate-800 pt-2 flex-shrink-0">
                <span>{insight.ai_powered ? '⚡ Powered by Gemini 2.0' : '📊 Rule-based analysis'}</span>
                {insight.generated_at && (
                    <span>{new Date(insight.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                )}
            </div>
        </div>
    );
};


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
    const [activeTab, setActiveTab] = React.useState<'OVERVIEW' | 'BOXSCORE' | 'PLAY_BY_PLAY'>('OVERVIEW');

    return (
        <div className="p-4 sm:p-8 h-full overflow-y-auto overflow-x-hidden w-full flex flex-col font-sans">
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
                    <button
                        onClick={() => setActiveTab('PLAY_BY_PLAY')}
                        className={`px-4 sm:px-6 py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-bold tracking-wider transition-all flex items-center gap-2 ${activeTab === 'PLAY_BY_PLAY' ? 'bg-red-500/20 text-red-400 shadow-sm border border-red-500/30' : 'text-slate-500 hover:text-slate-300'}`}
                    >
                        <Zap className="w-4 h-4" />
                        <span className="hidden sm:inline">PLAY-BY-PLAY</span>
                    </button>
                </div>
            </header>

            <div className="flex-1 min-h-0 flex flex-col min-w-0 w-full">
                {activeTab === 'OVERVIEW' ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 lg:auto-rows-fr animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
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
                            <InsightsWidget />
                        </DataCard>

                        {/* Pillar 4: Injury Report */}
                        <DataCard title="Injury Report — Today" icon={Stethoscope}>
                            <TodayInjuriesWidget />
                        </DataCard>
                    </div>
                ) : activeTab === 'BOXSCORE' ? (
                    <div className="animate-in fade-in flex-1 min-h-0">
                        <BoxScoreViewer />
                    </div>
                ) : (
                    <div className="animate-in fade-in w-full pb-8">
                        <PlayByPlayFeed />
                    </div>
                )}
            </div>
        </div>
    )
}
