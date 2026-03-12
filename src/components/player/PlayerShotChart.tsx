import { useEffect, useState } from 'react';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';
import { Activity, Target } from 'lucide-react';
import CornerBrackets from '../common/CornerBrackets';

interface ShotAttempt {
    sequenceNumber?: number;
    gameId: string;
    gameDate: string;
    matchup: string;
    playerId: string | number;
    playerName?: string;
    teamTricode?: string;
    shotType?: string;
    distance: number | null;
    shotArea?: string | null;
    made: boolean;
    period?: number;
    clock?: string;
    x: number | null;
    y: number | null;
    pointsValue?: number;
}

interface ClusteredShot {
    cx: number;
    cy: number;
    made: number;
    missed: number;
    total: number;
    pct: number;
}

interface PlayerShotChartProps {
    playerId: string;
    playerName?: string;
}

// NBA court half-court dimensions
const COURT_W = 500;
const COURT_H = 470;
const CLUSTER_RADIUS = 12; // pixels — shots within this radius merge

function courtX(x: number): number {
    return ((x + 250) / 500) * COURT_W;
}
function courtY(y: number): number {
    return ((y + 50) / 470) * COURT_H;
}

/** Group shots that land within CLUSTER_RADIUS pixels of each other */
function clusterShots(shots: ShotAttempt[]): ClusteredShot[] {
    const clusters: ClusteredShot[] = [];

    for (const s of shots) {
        if (s.x === null || s.y === null) continue;
        const sx = courtX(s.x);
        const sy = courtY(s.y);

        // Find existing cluster within radius
        let merged = false;
        for (const c of clusters) {
            const dx = c.cx - sx;
            const dy = c.cy - sy;
            if (Math.sqrt(dx * dx + dy * dy) <= CLUSTER_RADIUS) {
                // Weighted average position
                const newTotal = c.total + 1;
                c.cx = (c.cx * c.total + sx) / newTotal;
                c.cy = (c.cy * c.total + sy) / newTotal;
                if (s.made) c.made++;
                else c.missed++;
                c.total = newTotal;
                c.pct = c.total > 0 ? (c.made / c.total) * 100 : 0;
                merged = true;
                break;
            }
        }

        if (!merged) {
            clusters.push({
                cx: sx,
                cy: sy,
                made: s.made ? 1 : 0,
                missed: s.made ? 0 : 1,
                total: 1,
                pct: s.made ? 100 : 0,
            });
        }
    }

    return clusters;
}

function getClusterColor(pct: number): string {
    if (pct >= 60) return '#22c55e';      // green — hot
    if (pct >= 45) return '#84cc16';      // lime
    if (pct >= 35) return '#eab308';      // yellow
    if (pct >= 20) return '#f97316';      // orange
    return '#ef4444';                      // red — cold
}

function PlayerShotChartContent({ playerId }: PlayerShotChartProps) {
    const [shots, setShots] = useState<ShotAttempt[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [source, setSource] = useState<string>('');
    const [selectedGame, setSelectedGame] = useState<string | null>(null);

    useEffect(() => {
        if (!playerId || playerId === '0') return;

        const fetchShots = async () => {
            setLoading(true);
            setError(null);
            try {
                const base = import.meta.env.VITE_API_URL || 'https://quantsight-cloud-458498663186.us-central1.run.app';
                // Use the new endpoint that tries Firestore first, then NBA API
                const res = await fetch(`${base}/player-shots/${playerId}`);
                if (!res.ok) throw new Error(`Shot data unavailable (${res.status})`);
                const data = await res.json();
                setShots(data.shots || []);
                setSource(data.source || '');
            } catch (e: any) {
                setError(e.message || 'Failed to load shot chart data');
            } finally {
                setLoading(false);
            }
        };
        fetchShots();
    }, [playerId]);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-16 space-y-4 border border-cyber-border rounded-none bg-cyber-surface relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                <CornerBrackets />
                <Activity className="w-8 h-8 text-cyber-blue animate-spin" />
                <div className="text-[10px] text-cyber-muted font-mono tracking-widest uppercase">LOADING SHOT VECTORS...</div>
            </div>
        );
    }

    if (error || shots.length === 0) {
        return (
            <div className="p-8 text-center border border-cyber-border rounded-none bg-cyber-surface text-cyber-muted relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                <CornerBrackets />
                <Target className="w-10 h-10 mx-auto mb-4 opacity-50 text-cyber-red" />
                <p className="text-sm font-display font-600 uppercase tracking-[0.08em] text-cyber-text mb-1">No Shot Chart Data Available</p>
                <p className="text-[10px] font-mono uppercase tracking-widest text-cyber-muted">
                    {error || 'Shot data will populate automatically as games are tracked. Data may also be available from historical NBA records.'}
                </p>
            </div>
        );
    }

    // Unique games for filter
    const games = Array.from(new Set(shots.map(s => s.gameId))).map(gid => {
        const shot = shots.find(s => s.gameId === gid);
        return { gameId: gid, gameDate: shot?.gameDate || '', matchup: shot?.matchup || gid };
    });
    games.sort((a, b) => (b.gameDate || '').localeCompare(a.gameDate || ''));

    const filteredShots = selectedGame ? shots.filter(s => s.gameId === selectedGame) : shots;
    const madeShots = filteredShots.filter(s => s.made);
    const missedShots = filteredShots.filter(s => !s.made);
    const fgPct = filteredShots.length > 0 ? ((madeShots.length / filteredShots.length) * 100).toFixed(1) : '0';

    // Cluster shots for visualization
    const clusters = clusterShots(filteredShots);

    // Zone breakdown
    const paintShots = filteredShots.filter(s => (s.distance || 0) < 8);
    const midShots = filteredShots.filter(s => (s.distance || 0) >= 8 && (s.distance || 0) < 23);
    const threeShots = filteredShots.filter(s => (s.distance || 0) >= 23);
    const paintPct = paintShots.length > 0 ? ((paintShots.filter(s => s.made).length / paintShots.length) * 100).toFixed(1) : '—';
    const midPct = midShots.length > 0 ? ((midShots.filter(s => s.made).length / midShots.length) * 100).toFixed(1) : '—';
    const threePct = threeShots.length > 0 ? ((threeShots.filter(s => s.made).length / threeShots.length) * 100).toFixed(1) : '—';

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <h3 className="text-lg font-display font-700 tracking-[0.08em] uppercase text-cyber-text flex items-center gap-2">
                    <Target className="w-5 h-5 text-cyber-blue" /> Shot Chart
                    <span className="text-[10px] text-cyber-muted font-mono ml-2 tracking-widest uppercase">{filteredShots.length} shots</span>
                    {source && (
                        <span className={`text-[9px] px-2 py-0.5 rounded-none border font-mono uppercase tracking-widest ml-2 ${source === 'firestore' ? 'bg-cyber-green/10 text-cyber-green border-cyber-green/50' :
                                source === 'nba_api' ? 'bg-cyber-blue/10 text-cyber-blue border-cyber-blue/50' :
                                    'bg-white/[0.02] text-cyber-muted border-cyber-border'
                            }`}>
                            {source === 'firestore' ? 'LIVE' : source === 'nba_api' ? 'NBA API' : source}
                        </span>
                    )}
                </h3>
                <select
                    value={selectedGame || ''}
                    onChange={(e) => setSelectedGame(e.target.value || null)}
                    className="bg-cyber-bg border border-cyber-border rounded-none px-3 py-1.5 text-cyber-text text-[10px] font-mono uppercase tracking-widest focus:border-cyber-blue outline-none cursor-pointer"
                >
                    <option value="">All Games ({shots.length} shots)</option>
                    {games.map(g => (
                        <option key={g.gameId} value={g.gameId}>
                            {g.gameDate} — {g.matchup}
                        </option>
                    ))}
                </select>
            </div>

            {/* Court SVG with clustering */}
            <div className="bg-cyber-surface border border-cyber-border rounded-none p-4 overflow-hidden relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                <CornerBrackets />
                <div className="aspect-[500/470] max-w-2xl mx-auto relative z-10">
                    <svg viewBox={`0 0 ${COURT_W} ${COURT_H}`} className="w-full h-full" style={{ background: 'linear-gradient(135deg, #0b1120, #080d16)' }}>
                        {/* Court markings */}
                        <rect x="0" y="0" width={COURT_W} height={COURT_H} fill="none" stroke="#334155" strokeWidth="2" />
                        {/* Basket */}
                        <circle cx={COURT_W / 2} cy={courtY(0)} r="8" fill="none" stroke="#f97316" strokeWidth="2" />
                        {/* Paint */}
                        <rect x={courtX(-80)} y={0} width={courtX(80) - courtX(-80)} height={courtY(190)} fill="rgba(249,115,22,0.05)" stroke="#475569" strokeWidth="1" />
                        {/* Free throw circle */}
                        <circle cx={COURT_W / 2} cy={courtY(190)} r={(courtX(60) - courtX(0))} fill="none" stroke="#475569" strokeWidth="1" strokeDasharray="6,6" />
                        {/* 3-point arc */}
                        <path d={`M ${courtX(-220)} 0 Q ${courtX(-220)} ${courtY(300)}, ${COURT_W / 2} ${courtY(375)} Q ${courtX(220)} ${courtY(300)}, ${courtX(220)} 0`}
                            fill="none" stroke="#475569" strokeWidth="1.5" />

                        {/* Clustered shots — size scales with frequency, color with FG% */}
                        {clusters.map((c, i) => {
                            const r = Math.min(18, 4 + Math.sqrt(c.total) * 2.5);
                            const color = getClusterColor(c.pct);
                            return (
                                <g key={i}>
                                    {/* Outer glow for hot zones */}
                                    {c.total >= 3 && (
                                        <circle cx={c.cx} cy={c.cy} r={r + 3} fill={color} opacity={0.15} />
                                    )}
                                    {/* Main dot */}
                                    <circle
                                        cx={c.cx}
                                        cy={c.cy}
                                        r={r}
                                        fill={color}
                                        opacity={Math.min(0.9, 0.4 + c.total * 0.05)}
                                        stroke={c.total > 1 ? '#fff' : 'none'}
                                        strokeWidth={c.total > 1 ? 0.5 : 0}
                                    />
                                    {/* Count badge for clusters of 2+ */}
                                    {c.total >= 2 && (
                                        <text
                                            x={c.cx}
                                            y={c.cy + 1}
                                            textAnchor="middle"
                                            dominantBaseline="middle"
                                            fontSize={r > 8 ? 8 : 6}
                                            fontWeight="bold"
                                            fill="#fff"
                                            opacity={0.95}
                                        >
                                            {c.total}
                                        </text>
                                    )}
                                </g>
                            );
                        })}
                    </svg>
                </div>

                {/* Legend */}
                <div className="flex items-center justify-center gap-6 mt-4 text-[9px] text-cyber-muted font-mono uppercase tracking-widest relative z-10">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-none" style={{ background: '#00e5a0' }} /> Hot (60%+)
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-none" style={{ background: '#f59e0b' }} /> Avg (35-45%)
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-none" style={{ background: '#ef4444' }} /> Cold (&lt;20%)
                    </div>
                    <div className="flex items-center gap-1 opacity-60">
                        <span className="border border-cyber-border/50 px-1 py-0.5">3</span> = shot count
                    </div>
                </div>
            </div>

            {/* Zone Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-cyber-surface border border-cyber-border rounded-none p-4 text-center relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <div className="text-[10px] text-cyber-muted font-display font-600 uppercase tracking-widest mb-1 relative z-10">Overall FG%</div>
                    <div className="text-2xl font-mono text-cyber-text relative z-10">{fgPct}%</div>
                    <div className="text-[10px] text-cyber-blue font-mono mt-0.5 opacity-80 uppercase tracking-wider relative z-10">{madeShots.length}/{filteredShots.length}</div>
                </div>
                <div className="bg-cyber-surface border border-cyber-border rounded-none p-4 text-center relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <div className="text-[10px] text-cyber-muted font-display font-600 uppercase tracking-widest mb-1 relative z-10">Paint (&lt;8ft)</div>
                    <div className={`text-2xl font-mono relative z-10 ${parseFloat(paintPct) >= 50 ? 'text-cyber-green' : 'text-cyber-text'}`}>{paintPct}%</div>
                    <div className="text-[10px] text-cyber-blue font-mono mt-0.5 opacity-80 uppercase tracking-wider relative z-10">{paintShots.filter(s => s.made).length}/{paintShots.length}</div>
                </div>
                <div className="bg-cyber-surface border border-cyber-border rounded-none p-4 text-center relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <div className="text-[10px] text-cyber-muted font-display font-600 uppercase tracking-widest mb-1 relative z-10">Mid-Range</div>
                    <div className="text-2xl font-mono text-cyber-text relative z-10">{midPct}%</div>
                    <div className="text-[10px] text-cyber-blue font-mono mt-0.5 opacity-80 uppercase tracking-wider relative z-10">{midShots.filter(s => s.made).length}/{midShots.length}</div>
                </div>
                <div className="bg-cyber-surface border border-cyber-border rounded-none p-4 text-center relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <div className="text-[10px] text-cyber-muted font-display font-600 uppercase tracking-widest mb-1 relative z-10">3-Point</div>
                    <div className={`text-2xl font-mono relative z-10 ${parseFloat(threePct) >= 36 ? 'text-cyber-green' : 'text-cyber-text'}`}>{threePct}%</div>
                    <div className="text-[10px] text-cyber-blue font-mono mt-0.5 opacity-80 uppercase tracking-wider relative z-10">{threeShots.filter(s => s.made).length}/{threeShots.length}</div>
                </div>
            </div>
        </div>
    );
}

export default function PlayerShotChart({ playerId, playerName }: PlayerShotChartProps) {
    return (
        <SectionErrorBoundary fallbackMessage="Shot Chart Visualization offline">
            <PlayerShotChartContent playerId={playerId} />
        </SectionErrorBoundary>
    );
}
