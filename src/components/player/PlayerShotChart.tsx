import { useEffect, useState } from 'react';
import { ApiContract } from '../../api/client';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';
import { Activity, ShieldAlert, Target } from 'lucide-react';

interface ShotAttempt {
    sequenceNumber: number;
    gameId: string;
    gameDate: string;
    matchup: string;
    playerId: string | number;
    playerName: string;
    teamTricode: string;
    shotType: string;
    distance: number | null;
    shotArea: string | null;
    made: boolean;
    period: number;
    clock: string;
    x: number | null;
    y: number | null;
    pointsValue: number;
}

interface PlayerShotChartProps {
    playerId: string;
    playerName?: string;
}

// NBA court is 94ft × 50ft. Shot chart shows half court (47×50).
// NBA API coordinates: x ∈ [-250, 250], y ∈ [-50, 420]
const COURT_W = 500;
const COURT_H = 470;

function courtX(x: number): number {
    return ((x + 250) / 500) * COURT_W;
}
function courtY(y: number): number {
    return ((y + 50) / 470) * COURT_H;
}

function PlayerShotChartContent({ playerId, playerName }: PlayerShotChartProps) {
    const [shots, setShots] = useState<ShotAttempt[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedGame, setSelectedGame] = useState<string | null>(null);

    useEffect(() => {
        if (!playerId || playerId === '0') return;

        const fetchShots = async () => {
            setLoading(true);
            setError(null);
            try {
                const base = import.meta.env.VITE_API_URL || 'https://quantsight-cloud-458498663186.us-central1.run.app';
                const res = await fetch(`${base}/v1/games/players/${playerId}/shots?limit=500`);
                if (!res.ok) throw new Error(`Shot data unavailable (${res.status})`);
                const data = await res.json();
                setShots(data.shots || []);
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
            <div className="flex flex-col items-center justify-center py-16 space-y-4 border border-slate-800 rounded-xl bg-slate-900/30">
                <Activity className="w-8 h-8 text-slate-500 animate-spin" />
                <div className="text-sm text-slate-400 font-mono tracking-widest">LOADING SHOT VECTORS...</div>
            </div>
        );
    }

    if (error || shots.length === 0) {
        return (
            <div className="p-8 text-center border border-slate-700/50 rounded-xl bg-slate-800/20 text-slate-400">
                <Target className="w-10 h-10 mx-auto mb-4 opacity-50" />
                <p className="text-sm font-bold mb-1">No Shot Chart Data Available</p>
                <p className="text-xs text-slate-500">
                    {error || 'Shot data is populated from tracked live games. Check back after game tracking.'}
                </p>
            </div>
        );
    }

    // Get unique games for the filter
    const games = Array.from(new Set(shots.map(s => s.gameId))).map(gid => {
        const shot = shots.find(s => s.gameId === gid);
        return { gameId: gid, gameDate: shot?.gameDate || '', matchup: shot?.matchup || gid };
    });
    games.sort((a, b) => (b.gameDate || '').localeCompare(a.gameDate || ''));

    const filteredShots = selectedGame ? shots.filter(s => s.gameId === selectedGame) : shots;
    const madeShots = filteredShots.filter(s => s.made);
    const missedShots = filteredShots.filter(s => !s.made);
    const fgPct = filteredShots.length > 0 ? ((madeShots.length / filteredShots.length) * 100).toFixed(1) : '0';

    // Zone breakdown
    const paintShots = filteredShots.filter(s => (s.distance || 0) < 8);
    const midShots = filteredShots.filter(s => (s.distance || 0) >= 8 && (s.distance || 0) < 23);
    const threeShots = filteredShots.filter(s => (s.distance || 0) >= 23);
    const paintPct = paintShots.length > 0 ? ((paintShots.filter(s => s.made).length / paintShots.length) * 100).toFixed(1) : '—';
    const midPct = midShots.length > 0 ? ((midShots.filter(s => s.made).length / midShots.length) * 100).toFixed(1) : '—';
    const threePct = threeShots.length > 0 ? ((threeShots.filter(s => s.made).length / threeShots.length) * 100).toFixed(1) : '—';

    return (
        <div className="space-y-6">
            {/* Game Selector */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
                    <span>🎯</span> Shot Chart
                    <span className="text-xs text-slate-500 font-mono ml-2">{filteredShots.length} shots</span>
                </h3>
                <select
                    value={selectedGame || ''}
                    onChange={(e) => setSelectedGame(e.target.value || null)}
                    className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm"
                >
                    <option value="">All Games ({shots.length} shots)</option>
                    {games.map(g => (
                        <option key={g.gameId} value={g.gameId}>
                            {g.gameDate} — {g.matchup}
                        </option>
                    ))}
                </select>
            </div>

            {/* Court SVG */}
            <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-4 overflow-hidden">
                <div className="aspect-[500/470] max-w-2xl mx-auto relative">
                    <svg viewBox={`0 0 ${COURT_W} ${COURT_H}`} className="w-full h-full" style={{ background: 'linear-gradient(135deg, #1a2332, #0f1923)' }}>
                        {/* Court markings */}
                        <rect x="0" y="0" width={COURT_W} height={COURT_H} fill="none" stroke="#334155" strokeWidth="2" />
                        {/* Basket */}
                        <circle cx={COURT_W / 2} cy={courtY(0)} r="8" fill="none" stroke="#f97316" strokeWidth="2" />
                        {/* Paint */}
                        <rect x={courtX(-80)} y={0} width={courtX(80) - courtX(-80)} height={courtY(190)} fill="rgba(249,115,22,0.05)" stroke="#475569" strokeWidth="1" />
                        {/* Free throw circle */}
                        <circle cx={COURT_W / 2} cy={courtY(190)} r={(courtX(60) - courtX(0))} fill="none" stroke="#475569" strokeWidth="1" strokeDasharray="6,6" />
                        {/* 3-point arc (simplified) */}
                        <path d={`M ${courtX(-220)} 0 Q ${courtX(-220)} ${courtY(300)}, ${COURT_W / 2} ${courtY(375)} Q ${courtX(220)} ${courtY(300)}, ${courtX(220)} 0`}
                            fill="none" stroke="#475569" strokeWidth="1.5" />

                        {/* Missed shots */}
                        {missedShots.map((s, i) => (
                            s.x !== null && s.y !== null && (
                                <g key={`miss-${i}`}>
                                    <line x1={courtX(s.x) - 4} y1={courtY(s.y) - 4} x2={courtX(s.x) + 4} y2={courtY(s.y) + 4} stroke="#ef4444" strokeWidth="1.5" opacity="0.6" />
                                    <line x1={courtX(s.x) + 4} y1={courtY(s.y) - 4} x2={courtX(s.x) - 4} y2={courtY(s.y) + 4} stroke="#ef4444" strokeWidth="1.5" opacity="0.6" />
                                </g>
                            )
                        ))}
                        {/* Made shots */}
                        {madeShots.map((s, i) => (
                            s.x !== null && s.y !== null && (
                                <circle key={`made-${i}`} cx={courtX(s.x)} cy={courtY(s.y)} r="4" fill="#22c55e" opacity="0.7" />
                            )
                        ))}
                    </svg>
                </div>

                {/* Legend */}
                <div className="flex items-center justify-center gap-6 mt-4 text-xs text-slate-500">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full bg-emerald-500" /> Made
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 flex items-center justify-center text-red-500 font-bold">✕</div> Missed
                    </div>
                </div>
            </div>

            {/* Zone Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">Overall FG%</div>
                    <div className="text-2xl font-black text-white">{fgPct}%</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{madeShots.length}/{filteredShots.length}</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">Paint (&lt;8ft)</div>
                    <div className={`text-2xl font-black ${parseFloat(paintPct) >= 50 ? 'text-emerald-400' : 'text-white'}`}>{paintPct}%</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{paintShots.filter(s => s.made).length}/{paintShots.length}</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">Mid-Range</div>
                    <div className="text-2xl font-black text-white">{midPct}%</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{midShots.filter(s => s.made).length}/{midShots.length}</div>
                </div>
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 text-center">
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">3-Point</div>
                    <div className={`text-2xl font-black ${parseFloat(threePct) >= 36 ? 'text-emerald-400' : 'text-white'}`}>{threePct}%</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{threeShots.filter(s => s.made).length}/{threeShots.length}</div>
                </div>
            </div>
        </div>
    );
}

export default function PlayerShotChart({ playerId, playerName }: PlayerShotChartProps) {
    return (
        <SectionErrorBoundary fallbackMessage="Shot Chart Visualization offline">
            <PlayerShotChartContent playerId={playerId} playerName={playerName} />
        </SectionErrorBoundary>
    );
}
