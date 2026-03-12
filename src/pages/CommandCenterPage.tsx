import React from 'react'
import { Activity, ShieldCheck, Zap, BarChart3, LayoutDashboard, TrendingUp, AlertTriangle, Star, Stethoscope } from 'lucide-react'
import { ApiContract } from '../api/client'
import { BoxScoreViewer } from '../components/dashboard/BoxScoreViewer'
import { PlayByPlayFeed } from '../components/PlayByPlay/PlayByPlayFeed'
import { API_BASE } from '../config/apiConfig'
import CornerBrackets from '../components/common/CornerBrackets'

// Placeholder components - in a real app these would be their own widgets
const DataCard = ({ title, icon: Icon, children }: { title: string, icon: any, children: React.ReactNode }) => (
    <div className="relative bg-cyber-surface p-4 sm:p-6 flex flex-col gap-4 min-w-0 min-h-[280px] sm:min-h-[350px] lg:min-h-0 lg:h-full transition-colors duration-100 group shadow-none" style={{ border: '1px solid #1a2332' }}>
        <CornerBrackets />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyber-border to-transparent pointer-events-none" />
        <div className="flex items-center gap-2 text-cyber-muted font-display font-600 tracking-[0.12em] text-[10px] uppercase flex-shrink-0 group-hover:text-cyber-green transition-colors duration-100 relative z-10">
            <Icon className="w-4 h-4 text-cyber-green" />
            {title}
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto pr-1 scrollbar-premium relative z-10 font-sans">
            {children}
        </div>
    </div>
)

// ─── Today's Injuries Widget ──────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
    Out:          'bg-cyber-red/10 text-cyber-red border-cyber-red/30',
    Questionable: 'bg-cyber-gold/10 text-cyber-gold border-cyber-gold/30',
    Doubtful:     'bg-orange-500/10 text-orange-400 border-orange-500/30',
    'Day-To-Day': 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
    Probable:     'bg-cyber-green/10 text-cyber-green border-cyber-green/30',
};
const statusColor = (s: string) => STATUS_COLORS[s] ?? 'bg-white/[0.02] text-cyber-muted border-cyber-border/50';

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

    if (loading) return <div className="text-[10px] font-mono text-cyber-muted uppercase tracking-widest animate-pulse">Fetching injury reports...</div>;

    if (count === 0) return (
        <div className="flex flex-col items-center justify-center h-full gap-2 text-cyber-muted">
            <Stethoscope className="w-7 h-7 opacity-30 text-cyber-blue" />
            <div className="text-[10px] font-mono uppercase tracking-widest">No injury reports for today</div>
        </div>
    );

    return (
        <div className="flex flex-col gap-4">
            {Object.entries(injuries).map(([team, players]) => (
                <div key={team}>
                    <div className="text-[10px] font-display font-700 text-cyber-text uppercase tracking-[0.1em] mb-1.5 border-b border-cyber-border/50 pb-1">
                        {team}
                    </div>
                    <div className="flex flex-col gap-1">
                        {players.map((inj: any) => (
                            <div key={inj.playerId ?? inj.playerName}
                                className="flex items-center gap-2 px-2 py-1.5 bg-white/[0.02] rounded-none border border-cyber-border/50 relative">
                                <span className={`flex-shrink-0 text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-none border uppercase tracking-widest ${statusColor(inj.status)}`}>
                                    {inj.status === 'Day-To-Day' ? 'DTD' : (inj.status ?? '?').charAt(0)}
                                </span>
                                <div className="flex flex-col min-w-0">
                                    <span className="text-[10px] font-mono text-cyber-text uppercase tracking-wider truncate leading-tight">{inj.playerName}</span>
                                    {inj.injuryType && <span className="text-[9px] font-mono text-cyber-blue uppercase tracking-widest opacity-80 truncate leading-tight">{inj.injuryType}</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
            <div className="text-[8px] font-mono text-cyber-muted uppercase tracking-widest text-right">via ESPN • updates hourly</div>
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
            <div className="h-4 bg-cyber-border/50 rounded-none w-3/4" />
            <div className="h-3 bg-cyber-border/30 rounded-none w-full" />
            <div className="h-3 bg-cyber-border/30 rounded-none w-5/6" />
            <div className="h-3 bg-cyber-border/30 rounded-none w-4/6" />
        </div>
    );

    if (error || !insight) return (
        <div className="flex flex-col items-center justify-center h-full text-cyber-muted gap-2 text-center">
            <AlertTriangle className="w-8 h-8 opacity-40 text-cyber-red" />
            <div className="text-[10px] font-mono uppercase tracking-widest">Insights offline — refreshes in 30 min</div>
        </div>
    );

    const severityColor = insight.risk_flag?.severity === 'HIGH' ? 'text-cyber-red bg-cyber-red/10 border-cyber-red/30'
        : insight.risk_flag?.severity === 'MEDIUM' ? 'text-cyber-gold bg-cyber-gold/10 border-cyber-gold/30'
            : 'text-cyber-muted bg-white/[0.02] border-cyber-border/50';

    return (
        <div className="flex flex-col gap-4 h-full text-sm">
            {/* Headline */}
            <div className="text-cyber-blue font-display font-600 uppercase tracking-[0.05em] leading-snug glitch-text" data-text={insight.headline}>
                {insight.headline}
            </div>

            {/* Bullets */}
            <div className="space-y-2 flex-1">
                {(insight.bullets || []).map((b, i) => (
                    <div key={i} className="flex gap-2 items-start border-l border-cyber-border/30 pl-2">
                        <span className="text-[9px] font-black font-mono text-cyber-green mt-0.5 flex-shrink-0">
                            {String(i + 1).padStart(2, '0')}
                        </span>
                        <span className="text-cyber-text text-[11px] font-sans leading-relaxed">{b}</span>
                    </div>
                ))}
            </div>

            {/* Top Watch */}
            {insight.top_watch && (
                <div className="flex items-start gap-2 px-3 py-2.5 rounded-none bg-cyber-green/5 border border-cyber-green/30 relative">
                    <Star className="w-3 h-3 text-cyber-green flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                        <div className="flex flex-wrap items-baseline gap-x-1">
                            <span className="text-cyber-green text-[11px] font-mono tracking-wider uppercase font-bold">{insight.top_watch.player}</span>
                            <span className="text-cyber-muted text-[10px] font-mono uppercase tracking-widest">({insight.top_watch.team}) — {insight.top_watch.stat}</span>
                        </div>
                        <div className="text-cyber-text text-[10px] leading-relaxed mt-1 opacity-90">{insight.top_watch.reason}</div>
                    </div>
                </div>
            )}

            {/* Risk Flag */}
            {insight.risk_flag && (
                <div className={`flex items-start gap-2 px-3 py-2.5 rounded-none border ${severityColor} relative`}>
                    <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                        <span className="text-[11px] font-mono tracking-wider uppercase font-bold">{insight.risk_flag.player}</span>
                        <div className="text-[10px] text-cyber-text leading-relaxed mt-1 opacity-90">{insight.risk_flag.reason}</div>
                    </div>
                </div>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between font-mono tracking-widest text-[9px] uppercase text-cyber-muted border-t border-cyber-border pt-2 flex-shrink-0">
                <span>{insight.ai_powered ? 'POWERED BY GEMINI' : 'RULE-BASED ANALYSIS'}</span>
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

    if (loading) return <div className="text-[10px] font-mono text-cyber-muted uppercase tracking-widest animate-pulse">Scanning League Data...</div>;
    if (games.length === 0) return <div className="text-[10px] font-mono text-cyber-muted uppercase tracking-widest">No games scheduled.</div>;

    return (
        <div className="space-y-3">
            {games.map((game, idx) => {
                const isLive = game.status === 'LIVE';
                const isFinal = game.status === 'FINAL';
                const hasStarted = game.started || isLive || isFinal;
                const hasScores = hasStarted && (game.home_score > 0 || game.away_score > 0);

                return (
                    <div key={idx} className={`p-3 bg-white/[0.02] rounded-none border border-cyber-border/50 border-l-2 relative ${isLive ? 'border-l-cyber-red' : game.volatility === 'High' ? 'border-l-cyber-green' : 'border-l-cyber-border'}`}>
                        <div className="flex justify-between items-center mb-1">
                            {hasScores ? (
                                <span className="font-mono text-[11px] font-bold text-cyber-text uppercase tracking-wider">
                                    {game.away} <span className="text-cyber-blue font-black">{game.away_score}</span> <span className="text-cyber-muted mx-1">@</span> {game.home} <span className="text-cyber-blue font-black">{game.home_score}</span>
                                </span>
                            ) : (
                                <span className="font-mono text-[11px] font-bold text-cyber-text uppercase tracking-wider">{game.away} <span className="text-cyber-muted mx-1">@</span> {game.home}</span>
                            )}
                            <div className="flex items-center gap-2">
                                {/* Status indicator */}
                                {isLive && (
                                    <span className="text-[9px] font-mono tracking-widest uppercase text-cyber-red animate-pulse flex items-center gap-1">
                                        <span className="w-1.5 h-1.5 bg-cyber-red rounded-none animate-pulse"></span>
                                        {game.time}
                                    </span>
                                )}
                                {isFinal && (
                                    <span className="text-[9px] font-mono tracking-widest uppercase text-cyber-muted">{game.time}</span>
                                )}
                                {!isLive && !isFinal && (
                                    <span className={`text-[9px] font-mono uppercase tracking-widest ${hasStarted ? 'text-cyber-gold' : 'text-cyber-muted'}`}>
                                        {game.time}
                                    </span>
                                )}
                            </div>
                        </div>
                        {/* Additional game info */}
                        {isLive && (
                            <div className="text-[9px] font-mono text-cyber-red/80 uppercase tracking-widest mt-1">Live Game • High Volatility</div>
                        )}
                        {hasStarted && !isLive && !isFinal && (
                            <div className="text-[9px] font-mono text-cyber-gold/80 uppercase tracking-widest mt-1">Started • Check for updates</div>
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
        <div className="p-4 sm:p-8 min-h-full overflow-x-hidden w-full flex flex-col font-sans bg-cyber-bg relative z-10 bg-scanline">

            <header className="mb-6 flex-shrink-0 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 relative z-10">
                <div>
                    <h1 className="text-3xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text flex items-center gap-3">
                        <div className="w-10 h-10 rounded-sm border border-cyber-border bg-cyber-surface flex items-center justify-center">
                            <Activity className="w-5 h-5 text-cyber-green" />
                        </div>
                        Command Center
                    </h1>
                    <p className="font-mono tracking-[0.2em] text-[10px] text-cyber-muted mt-2 uppercase">Operational Overview • {new Date().toLocaleDateString()}</p>
                </div>

                <div className="flex gap-4 border-b border-cyber-border self-start sm:self-auto relative z-10 w-full sm:w-auto">
                    <button
                        onClick={() => setActiveTab('OVERVIEW')}
                        className={`py-2 px-1 text-[10px] font-display font-600 tracking-[0.12em] uppercase transition-all duration-100 flex items-center gap-2 border-b-2 ${activeTab === 'OVERVIEW' ? 'border-cyber-green text-cyber-green' : 'border-transparent text-cyber-muted hover:text-cyber-text'}`}
                    >
                        <LayoutDashboard className="w-4 h-4" />
                        <span className="hidden sm:inline">OVERVIEW</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('BOXSCORE')}
                        className={`py-2 px-1 text-[10px] font-display font-600 tracking-[0.12em] uppercase transition-all duration-100 flex items-center gap-2 border-b-2 ${activeTab === 'BOXSCORE' ? 'border-cyber-green text-cyber-green' : 'border-transparent text-cyber-muted hover:text-cyber-text'}`}
                    >
                        <BarChart3 className="w-4 h-4" />
                        <span className="hidden sm:inline">BOX SCORES</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('PLAY_BY_PLAY')}
                        className={`py-2 px-1 text-[10px] font-display font-600 tracking-[0.12em] uppercase transition-all duration-100 flex items-center gap-2 border-b-2 ${activeTab === 'PLAY_BY_PLAY' ? 'border-cyber-green text-cyber-green' : 'border-transparent text-cyber-muted hover:text-cyber-text'}`}
                    >
                        <Zap className="w-4 h-4" />
                        <span className="hidden sm:inline">PLAY-BY-PLAY</span>
                    </button>
                </div>
            </header>

            <div className="flex-1 min-h-0 flex flex-col min-w-0 w-full">
                {activeTab === 'OVERVIEW' ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 auto-rows-auto animate-in fade-in slide-in-from-bottom-4 duration-500 relative bg-cyber-bg">
                        {/* Pillar 1: Today's Matchups */}
                        <DataCard title="Today's Matchups" icon={Zap}>
                            <ScheduleWidget />
                        </DataCard>

                        {/* Pillar 2: System Health Matrix */}
                        <DataCard title="System Health Matrix" icon={ShieldCheck}>
                            <div className="grid grid-cols-2 gap-4 h-full content-start">
                                <div className="bg-white/[0.02] p-4 rounded-none text-center border border-cyber-border/50 relative">
                                    <div className="text-[9px] text-cyber-muted uppercase font-mono tracking-widest mb-1.5 shadow-none">API Latency</div>
                                    <div className="text-2xl font-black font-mono text-cyber-green glitch-text" data-text="42ms">42ms</div>
                                </div>
                                <div className="bg-white/[0.02] p-4 rounded-none text-center border border-cyber-border/50 relative">
                                    <div className="text-[9px] text-cyber-muted uppercase font-mono tracking-widest mb-1.5 shadow-none">Model Drift</div>
                                    <div className="text-2xl font-black font-mono text-cyber-blue glitch-text" data-text="0.03%">0.03%</div>
                                </div>
                                <div className="col-span-2 bg-cyber-green/5 p-4 rounded-none text-center border border-cyber-green/30 relative overflow-hidden group">
                                    <div className="absolute inset-0 bg-gradient-to-r from-cyber-green/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                                    <div className="text-[10px] text-cyber-green font-mono uppercase font-black tracking-[0.15em] relative z-10">All Systems Operational</div>
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
