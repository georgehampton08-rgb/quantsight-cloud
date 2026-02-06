/**
 * ProjectionMatrix Component
 * Displays Floor/EV/Ceiling projections from Monte Carlo simulation
 */
import { SimulationResult, StatProjection } from '../../services/aegisApi';
import FatigueBreakdownChip from '../common/FatigueBreakdownChip';
import GameModeIndicator from '../common/GameModeIndicator';
import DefenderImpactTooltip from '../common/DefenderImpactTooltip';

interface ProjectionMatrixProps {
    simulation: SimulationResult | null;
    loading?: boolean;
    onRefresh?: () => void;
}

// Grade colors
const gradeColors: Record<string, string> = {
    'A': 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    'B': 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    'C': 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    'D': 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    'F': 'text-red-400 bg-red-500/10 border-red-500/30',
};

export default function ProjectionMatrix({ simulation, loading, onRefresh }: ProjectionMatrixProps) {

    if (loading) {
        return (
            <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-6 animate-pulse">
                <div className="flex items-center justify-between mb-6">
                    <div className="h-6 w-48 bg-slate-700 rounded" />
                    <div className="h-8 w-16 bg-slate-700 rounded" />
                </div>
                <div className="grid grid-cols-3 gap-4">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="h-32 bg-slate-700/50 rounded-lg" />
                    ))}
                </div>
            </div>
        );
    }

    if (!simulation) {
        return (
            <div className="bg-slate-800/50 backdrop-blur-sm border border-dashed border-slate-700/50 rounded-xl p-8 text-center">
                <div className="text-3xl mb-4">🎲</div>
                <div className="text-slate-400">No simulation data</div>
                <div className="text-xs text-slate-600 mt-2">Select an opponent to run projection</div>
            </div>
        );
    }

    const {
        projections,
        confidence,
        modifiers,
        execution_time_ms,
        schedule_context,
        game_mode,
        momentum,
        defender_profile
    } = simulation;

    const renderStatBar = (stat: keyof StatProjection, label: string) => {
        const floor = projections.floor[stat] || 0;
        const ev = projections.expected_value[stat] || 0;
        const ceiling = projections.ceiling[stat] || 0;

        const maxVal = Math.max(ceiling * 1.1, 40);
        const floorPct = (floor / maxVal) * 100;
        const evPct = (ev / maxVal) * 100;
        const ceilingPct = (ceiling / maxVal) * 100;

        const barContent = (
            <div className="group relative">
                <div className="flex items-center justify-between mb-3 gap-4">
                    <span className="text-xs uppercase text-slate-500 tracking-wider font-medium">{label}</span>
                    <span className="text-sm font-mono text-financial-accent font-bold">{ev.toFixed(1)}</span>
                </div>

                {/* Projection bar */}
                <div className="h-6 bg-slate-900 rounded-lg relative overflow-hidden">
                    {/* Floor zone (red) */}
                    <div
                        className="absolute inset-y-0 left-0 bg-red-500/30"
                        style={{ width: `${floorPct}%` }}
                    />

                    {/* EV zone (green) */}
                    <div
                        className="absolute inset-y-0 bg-gradient-to-r from-emerald-500/50 to-emerald-500/30"
                        style={{ left: `${floorPct}%`, width: `${evPct - floorPct}%` }}
                    />

                    {/* Ceiling zone (blue) */}
                    <div
                        className="absolute inset-y-0 bg-blue-500/30"
                        style={{ left: `${evPct}%`, width: `${ceilingPct - evPct}%` }}
                    />

                    {/* Markers */}
                    <div
                        className="absolute inset-y-0 w-0.5 bg-red-400"
                        style={{ left: `${floorPct}%` }}
                    />
                    <div
                        className="absolute inset-y-0 w-1 bg-emerald-400"
                        style={{ left: `${evPct}%` }}
                    />
                    <div
                        className="absolute inset-y-0 w-0.5 bg-blue-400"
                        style={{ left: `${ceilingPct}%` }}
                    />
                </div>

                {/* Values below bar - properly spaced */}
                <div className="flex items-center justify-between mt-2 text-xs font-mono">
                    <span className="text-red-400">{floor.toFixed(1)}</span>
                    <span className="text-emerald-400 font-bold">{ev.toFixed(1)}</span>
                    <span className="text-blue-400">{ceiling.toFixed(1)}</span>
                </div>
            </div>
        );

        if (stat === 'points' && defender_profile) {
            return (
                <DefenderImpactTooltip
                    defenderName={defender_profile.primary_defender}
                    dfgPct={defender_profile.dfg_pct}
                    pctPlusminus={defender_profile.pct_plusminus}
                >
                    {barContent}
                </DefenderImpactTooltip>
            );
        }

        return barContent;
    };

    return (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-4 sm:p-6">
            {/* Header */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4 sm:mb-6">
                <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                    <span className="text-lg">🎲</span>
                    <h3 className="text-base sm:text-lg font-bold text-slate-200">Projection Matrix</h3>
                    <GameModeIndicator
                        blowoutPct={game_mode?.blowout_pct || 0}
                        clutchPct={game_mode?.clutch_pct || 0}
                    />
                    <span className="text-xs text-slate-600 font-mono hidden sm:inline">{execution_time_ms}ms</span>
                </div>

                {/* Confluence Grade Badge */}
                <div className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg border font-bold ${gradeColors[confidence.grade] || gradeColors.C}`}>
                    <span className="text-base sm:text-lg">{confidence.grade}</span>
                    <span className="text-xs ml-1 opacity-75">{confidence.score.toFixed(0)}</span>
                </div>
            </div>

            {/* Modifiers Bar */}
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mb-4 sm:mb-6">
                <span className="px-2 py-1 bg-slate-900/50 rounded text-xs text-slate-400 border border-slate-700/50 truncate max-w-[120px] sm:max-w-none">
                    🏀 {modifiers.archetype}
                </span>

                <FatigueBreakdownChip
                    isB2B={schedule_context.is_b2b}
                    daysRest={schedule_context.days_rest}
                    modifier={schedule_context.modifier}
                />

                {modifiers.usage_boost > 0 && (
                    <span className="px-2 py-1 bg-purple-900/30 border border-purple-500/20 rounded text-xs text-purple-400">
                        📈 +{(modifiers.usage_boost * 100).toFixed(0)}% USG
                    </span>
                )}

                {momentum.hot_streak && (
                    <span className="px-2 py-1 bg-orange-500/10 border border-orange-500/30 rounded text-xs text-orange-400 animate-pulse">
                        🔥 Hot Streak
                    </span>
                )}

                {defender_profile && (
                    <DefenderImpactTooltip
                        defenderName={defender_profile.primary_defender || 'Unknown Defender'}
                        dfgPct={defender_profile.dfg_pct || 0}
                        pctPlusminus={defender_profile.pct_plusminus || 0}
                    >
                        <span className="px-2 py-1 bg-slate-900/50 rounded text-xs text-slate-400 border border-slate-700/50 cursor-help hover:border-slate-500/50 transition-colors truncate max-w-[100px] sm:max-w-none">
                            🛡️ {defender_profile.primary_defender || 'Defender'}
                        </span>
                    </DefenderImpactTooltip>
                )}
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-2 sm:gap-4 mb-4 text-xs">
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-red-500/50 rounded" />
                    <span className="text-slate-500">Floor (20th)</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-emerald-500/50 rounded" />
                    <span className="text-slate-500">Expected (Mean)</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-blue-500/50 rounded" />
                    <span className="text-slate-500">Ceiling (80th)</span>
                </div>
            </div>

            {/* Stat Bars */}
            <div className="space-y-6">
                {renderStatBar('points', 'Points')}
                {renderStatBar('rebounds', 'Rebounds')}
                {renderStatBar('assists', 'Assists')}
                {renderStatBar('threes', '3-Pointers')}
            </div>

            {/* Refresh Button */}
            {onRefresh && (
                <button
                    onClick={onRefresh}
                    className="mt-6 w-full py-2 text-sm text-slate-400 hover:text-financial-accent border border-slate-700 hover:border-financial-accent rounded-lg transition-all"
                >
                    🔄 Re-run Simulation
                </button>
            )}
        </div>
    );
}
