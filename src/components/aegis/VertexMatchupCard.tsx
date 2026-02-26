import React from 'react';
import { Swords, TrendingUp, TrendingDown, Minus, Zap, Target, AlertTriangle } from 'lucide-react';
import { ApiContract } from '../../api/client';

// Inlined from removed aegisApi.ts
interface PlayerMatchupPlayer { name: string; score: number; }
interface PlayerMatchup {
    player_a: PlayerMatchupPlayer;
    player_b: PlayerMatchupPlayer;
    advantage: 'A' | 'B' | 'EVEN';
    advantage_degree: number;
    categories: Record<string, 'A' | 'B' | 'EVEN'>;
    analysis: string;
    engine_stats?: { analysis_mode?: string; cache_hit_rate?: number; avg_analysis_time_ms?: number };
}

interface VertexMatchupCardProps {
    playerAId: string;
    playerBId: string;
    season?: string;
    onClose?: () => void;
}

const CategoryBar: React.FC<{
    category: string;
    winner: 'A' | 'B' | 'EVEN';
}> = ({ category, winner }) => {
    const formatCategory = (cat: string) => cat.replace(/_/g, ' ').replace('avg', '').trim();

    return (
        <div className="flex items-center gap-3 py-2">
            <div className="w-24 text-xs text-slate-500 uppercase tracking-wider">
                {formatCategory(category)}
            </div>
            <div className="flex-1 flex items-center gap-2">
                <div className={`flex-1 h-2 rounded-full ${winner === 'A' ? 'bg-emerald-500' : 'bg-slate-700'}`} />
                <div className="w-8 text-center">
                    {winner === 'A' ? (
                        <TrendingUp className="w-4 h-4 text-emerald-400 mx-auto" />
                    ) : winner === 'B' ? (
                        <TrendingDown className="w-4 h-4 text-red-400 mx-auto" />
                    ) : (
                        <Minus className="w-4 h-4 text-slate-500 mx-auto" />
                    )}
                </div>
                <div className={`flex-1 h-2 rounded-full ${winner === 'B' ? 'bg-red-500' : 'bg-slate-700'}`} />
            </div>
        </div>
    );
};

export default function VertexMatchupCard({ playerAId, playerBId, season = '2024-25', onClose }: VertexMatchupCardProps) {
    const [matchup, setMatchup] = React.useState<PlayerMatchup | null>(null);
    const [loading, setLoading] = React.useState(true);
    const [error, setError] = React.useState<string | null>(null);

    React.useEffect(() => {
        const fetchMatchup = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await ApiContract.execute<PlayerMatchup>(null, {
                    path: `aegis/matchup?player_a=${playerAId}&player_b=${playerBId}&season=${season}`
                });
                if (res.data) setMatchup(res.data);
                else throw new Error('No matchup data returned');
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Matchup analysis failed');
            } finally {
                setLoading(false);
            }
        };

        if (playerAId && playerBId) {
            fetchMatchup();
        }
    }, [playerAId, playerBId, season]);

    if (loading) {
        return (
            <div className="p-8 rounded-xl border border-orange-700/30 bg-orange-900/10 animate-pulse">
                <div className="flex items-center justify-center gap-3">
                    <Swords className="w-6 h-6 text-orange-400 animate-spin" />
                    <span className="text-orange-400">Analyzing matchup...</span>
                </div>
            </div>
        );
    }

    if (error || !matchup) {
        return (
            <div className="p-6 rounded-xl border border-red-700/30 bg-red-900/10">
                <div className="flex items-center gap-3 text-red-400">
                    <AlertTriangle className="w-5 h-5" />
                    <span>{error || 'Unable to analyze matchup'}</span>
                </div>
            </div>
        );
    }

    const advantageColor = matchup.advantage === 'A'
        ? 'text-emerald-400'
        : matchup.advantage === 'B'
            ? 'text-red-400'
            : 'text-yellow-400';

    const advantageText = matchup.advantage === 'A'
        ? `${matchup.player_a.name} has the edge`
        : matchup.advantage === 'B'
            ? `${matchup.player_b.name} has the edge`
            : 'Even matchup';

    return (
        <div className="rounded-xl border border-orange-700/30 bg-slate-900/80 overflow-hidden">
            {/* Header */}
            <div className="bg-gradient-to-r from-orange-900/30 to-slate-900 p-6">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <Swords className="w-6 h-6 text-orange-400" />
                        <span className="text-sm uppercase tracking-wider text-orange-400 font-bold">Vertex Analysis</span>
                    </div>
                    {onClose && (
                        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
                            ✕
                        </button>
                    )}
                </div>

                {/* Player Comparison */}
                <div className="flex items-center justify-between">
                    <div className="flex-1 text-center">
                        <div className="text-2xl font-bold text-white">{matchup.player_a.name}</div>
                        <div className="text-3xl font-bold text-emerald-400 mt-2">{matchup.player_a.score.toFixed(1)}</div>
                        <div className="text-xs text-slate-500 uppercase mt-1">Score</div>
                    </div>

                    <div className="px-8 flex flex-col items-center">
                        <div className="text-4xl font-bold text-slate-600">VS</div>
                        <div className={`text-xs uppercase tracking-wider mt-2 ${advantageColor}`}>
                            {(matchup.advantage_degree * 100).toFixed(0)}% confidence
                        </div>
                    </div>

                    <div className="flex-1 text-center">
                        <div className="text-2xl font-bold text-white">{matchup.player_b.name}</div>
                        <div className="text-3xl font-bold text-red-400 mt-2">{matchup.player_b.score.toFixed(1)}</div>
                        <div className="text-xs text-slate-500 uppercase mt-1">Score</div>
                    </div>
                </div>
            </div>

            {/* Categories */}
            <div className="p-6 border-t border-slate-800">
                <h4 className="text-xs uppercase tracking-wider text-slate-500 mb-4">Category Breakdown</h4>
                <div className="space-y-1">
                    {Object.entries(matchup.categories).map(([category, winner]) => (
                        <CategoryBar
                            key={category}
                            category={category}
                            winner={winner}
                        />
                    ))}
                </div>
            </div>

            {/* Analysis */}
            <div className="p-6 border-t border-slate-800 bg-slate-900/50">
                <div className="flex items-start gap-3">
                    <Target className={`w-5 h-5 mt-0.5 ${advantageColor}`} />
                    <div>
                        <div className={`font-bold ${advantageColor}`}>{advantageText}</div>
                        <p className="text-sm text-slate-400 mt-1">{matchup.analysis}</p>
                    </div>
                </div>
            </div>

            {/* Footer Stats */}
            <div className="p-4 border-t border-slate-800 bg-slate-950/50 flex items-center justify-between text-xs text-slate-600">
                <div className="flex items-center gap-2">
                    <Zap className="w-3 h-3" />
                    <span>Mode: {matchup.engine_stats?.analysis_mode || 'standard'}</span>
                </div>
                <div>
                    Cache: {((matchup.engine_stats?.cache_hit_rate || 0) * 100).toFixed(0)}%
                </div>
                <div>
                    Analysis: {(matchup.engine_stats?.avg_analysis_time_ms || 0).toFixed(0)}ms
                </div>
            </div>
        </div>
    );
}
