import { useEffect, useState } from 'react';
import HeroSection from '../components/profile/HeroSection';
import NarrativeBlock from '../components/profile/NarrativeBlock';
import MatchupRadar from '../components/matchup/MatchupRadar';
import InsightBanner from '../components/matchup/InsightBanner';
import ProbabilityGauge from '../components/profile/ProbabilityGauge';
import MetricCard from '../components/common/MetricCard';
import ConfidenceRing from '../components/common/ConfidenceRing';
import Sparkline from '../components/common/Sparkline';
import { PlayerApi, MatchupResult } from '../services/playerApi';
import DataProvenanceBadge from '../components/common/DataProvenanceBadge';
import { useDataFreshness } from '../hooks/useDataFreshness';
import { useToast } from '../context/ToastContext';
import { useNavigate, useParams } from 'react-router-dom';
import { ApiContract } from '../api/client';
import { GameLogsViewer } from '../components/player/GameLogsViewer';
import { H2HHistoryPanel } from '../components/player/H2HHistoryPanel';
import { useOrbital } from '../context/OrbitalContext';
import ProjectionMatrix from '../components/aegis/ProjectionMatrix';
import PlayTypeEfficiency from '../components/aegis/PlayTypeEfficiency';
import EnrichedPlayerCard from '../components/profile/EnrichedPlayerCard';
import { useSimulation } from '../hooks/useSimulation';

export default function PlayerProfilePage() {
    const { id } = useParams<{ id: string }>();
    const { selectedPlayer, setSelectedPlayer } = useOrbital();
    const navigate = useNavigate();

    // If no ID is provided, defer to global state or show empty state
    const targetId = id;

    const [loading, setLoading] = useState(!!targetId);
    const [matchupData, setMatchupData] = useState<MatchupResult | null>(null);
    const [activeTab, setActiveTab] = useState<'Overview' | 'Projection' | 'Matchup' | 'GameLogs' | 'Advanced' | 'ShotChart'>('Overview');
    const [currentOpponent, setCurrentOpponent] = useState<string>('1610612738'); // Default to Celtics
    const [teams, setTeams] = useState<{ team_id: string, name: string, abbreviation: string }[]>([]);
    const { showToast } = useToast();

    // Radar dimensions from API (real math!)
    const [radarData, setRadarData] = useState<{
        player: { scoring: number; playmaking: number; rebounding: number; defense: number; pace: number } | null;
        opponent: { scoring: number; playmaking: number; rebounding: number; defense: number; pace: number } | null;
    }>({ player: null, opponent: null });

    // Fetch all teams for dropdown
    useEffect(() => {
        const fetchTeams = async () => {
            try {
                const res = await ApiContract.execute<any>('getTeams', { path: 'teams' });
                const data = res.data;
                if (data.teams) {
                    setTeams(data.teams);
                }
            } catch (e) {
                console.error('Failed to fetch teams:', e);
            }
        };
        fetchTeams();
    }, []);

    // Simulation hook
    const { simulation, loading: simLoading, runSimulation, forceRefreshAndRun, refreshStatus } = useSimulation({
        playerId: targetId || '0',
        opponentId: currentOpponent
    });

    const { setSimulationResult } = useOrbital();

    // Sync simulation to context
    useEffect(() => {
        if (simulation) {
            setSimulationResult(simulation as unknown as Record<string, unknown>);
        }
    }, [simulation, setSimulationResult]);

    // Auto-run simulation when player or opponent changes
    useEffect(() => {
        if (targetId && currentOpponent && activeTab === 'Projection') {
            runSimulation(currentOpponent);
        }
    }, [targetId, currentOpponent, activeTab]);

    // Fetch REAL radar dimensions when Matchup tab is active
    useEffect(() => {
        if (!targetId || activeTab !== 'Matchup') return;

        const fetchRadar = async () => {
            try {
                const base = import.meta.env.VITE_API_URL || '';
                const res = await fetch(`${base}/radar/${targetId}?opponent_id=${currentOpponent}`);
                if (!res.ok) throw new Error(`Radar fetch failed: ${res.status}`);
                const data = await res.json();
                if (data.player_stats && data.opponent_defense) {
                    setRadarData({
                        player: data.player_stats,
                        opponent: data.opponent_defense
                    });
                    console.log('[RADAR] Loaded real dimensions:', data);
                }
            } catch (e) {
                console.warn('[RADAR] Failed to load, using defaults:', e);
            }
        };
        fetchRadar();
    }, [targetId, currentOpponent, activeTab]);

    // Mock last updated
    const mockLastUpdated = new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString();
    const { freshness, isRefreshing, forceRefresh } = useDataFreshness(targetId || '0', mockLastUpdated);

    useEffect(() => {
        if (!targetId) return;

        const loadData = async () => {
            // Context Logic: "The One-Truth Rule"
            if (selectedPlayer && selectedPlayer.id === targetId) {
                console.log(`[OrbitalContext] CACHE HIT: Using global state for player ${targetId}`);
                setLoading(false);
            } else {
                console.log(`[OrbitalContext] CACHE MISS: Fetching fresh data for player ${targetId}`);
                setLoading(true);
                try {
                    const data = await PlayerApi.getProfile(targetId);
                    setSelectedPlayer(data); // UPDATE GLOBAL TRUTH
                } catch (e) {
                    console.error("Failed to load profile", e);
                } finally {
                    setLoading(false);
                }
            }

            // Fetch matchup with TODAY's opponent (dynamic from schedule)
            try {
                // Get today's schedule to find if player's team has a game
                let opponent = 'NBA'; // Default fallback

                try {
                    const res = await ApiContract.execute<any>('getSchedule', { path: 'schedule' });
                    const schedule = res.data;

                    if (schedule?.games?.length > 0) {
                        // Try to find a game involving the player's team
                        const playerTeam = selectedPlayer?.team;
                        const todaysGame = schedule.games.find((g: any) =>
                            g.home_team === playerTeam || g.away_team === playerTeam
                        );

                        if (todaysGame) {
                            opponent = todaysGame.home_team === playerTeam
                                ? todaysGame.away_team
                                : todaysGame.home_team;
                        } else {
                            // No game today for this team, use first game's teams for preview
                            opponent = schedule.games[0]?.home_team || 'NBA';
                        }
                    }
                } catch (schedErr) {
                    console.warn('Schedule fetch failed, using default opponent', schedErr);
                }

                const matchup = await PlayerApi.analyzeMatchup(targetId, opponent);
                setMatchupData(matchup);
            } catch (e) {
                console.error("Failed to load matchup", e);
            }
        };
        loadData();
    }, [targetId, selectedPlayer, setSelectedPlayer]);

    const handleForceRefresh = async () => {
        if (!selectedPlayer) return;

        showToast('Refreshing player data...', 'info');
        await forceRefresh(selectedPlayer.name);

        // Also refresh simulation if on Projection tab
        if (activeTab === 'Projection' && currentOpponent) {
            await runSimulation(currentOpponent);
        }

        if (freshness.status === 'live') {
            showToast('Data updated successfully!', 'success');
        } else {
            showToast('No new data available.', 'info');
        }
    };

    if (loading) return <div className="p-8 text-financial-accent animate-pulse">Initializing Neural Link...</div>;

    // Empty State (No ID or No Player Found)
    if (!targetId || !selectedPlayer) return (
        <div className="flex flex-col items-center justify-center p-12 space-y-6 border border-slate-800 rounded-2xl bg-slate-900/50 mt-8 max-w-2xl mx-auto">
            <div className="text-4xl">🔍</div>
            <div className="text-xl font-mono text-white">Search Protocol Initiated</div>
            <div className="text-sm text-slate-500 max-w-md text-center">
                System is ready. Use the <strong>Search Bar</strong> above to locate any player to begin analysis.
            </div>
            <button
                onClick={() => navigate('/')}
                className="px-6 py-3 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-financial-accent border border-slate-700 hover:border-financial-accent transition-all"
            >
                Return to Command Center
            </button>
        </div>
    );

    const profile = selectedPlayer; // Alias for easier refactor compatibility

    const tabs = [
        { id: 'Overview', label: 'Overview', icon: '📊' },
        { id: 'Projection', label: 'Monte Carlo', icon: '🎲' },
        { id: 'Matchup', label: 'Matchup Intelligence', icon: '⚔️' },
        { id: 'GameLogs', label: 'Game Logs', icon: '📋' },
        { id: 'Advanced', label: 'Advanced Stats', icon: '📈' },
        { id: 'ShotChart', label: 'Shot Chart', icon: '🎯' }
    ] as const;

    return (
        <div className="h-full overflow-y-auto">
            <div className="max-w-7xl mx-auto pb-12 p-6">
                <HeroSection player={profile} />

                {/* Tab Navigation */}
                <div className="flex gap-1 sm:gap-2 border-b border-slate-800 pb-4 mb-6 sm:mb-8 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-1 sm:gap-2 text-[10px] sm:text-sm tracking-widest uppercase font-bold px-3 sm:px-6 py-2 sm:py-3 border-b-2 transition-all whitespace-nowrap shrink-0 ${activeTab === tab.id
                                ? 'border-financial-accent text-financial-accent bg-financial-accent/5'
                                : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-slate-800/30'
                                }`}
                        >
                            <span>{tab.icon}</span>
                            <span className="hidden sm:inline">{tab.label}</span>
                            <span className="sm:hidden">{tab.id}</span>
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="animate-in fade-in duration-300">
                    {activeTab === 'Overview' && (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div className="space-y-6">
                                <MetricCard title="Model Confidence" value={`${profile.stats?.confidence || 0}%`} subValue="High Certainty">
                                    <ConfidenceRing score={profile.stats?.confidence || 0} size={60} />
                                </MetricCard>

                                <MetricCard title="PPG Trend" value={profile.stats?.ppg || 0} subValue="Last 5 Games">
                                    <Sparkline data={profile.stats?.trend || []} width={80} height={30} />
                                </MetricCard>

                                <ProbabilityGauge hitProbability={profile.hitProbability} impliedOdds={profile.impliedOdds} />
                            </div>

                            <div className="lg:col-span-2 space-y-6">
                                <NarrativeBlock text={profile.narrative} />
                                <EnrichedPlayerCard playerId={targetId || '0'} playerName={profile.name} />
                            </div>
                        </div>
                    )}

                    {activeTab === 'GameLogs' && targetId && (
                        <div className="space-y-6">
                            <GameLogsViewer playerId={targetId} />

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                                {/* H2H Viewer with context from Matchup/Projection (currentOpponent) */}
                                <div className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <h3 className="text-sm font-bold text-slate-400">Target Opponent</h3>
                                        <select
                                            value={currentOpponent}
                                            onChange={(e) => setCurrentOpponent(e.target.value)}
                                            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm"
                                        >
                                            {teams.map((team) => (
                                                <option key={team.team_id} value={team.team_id}>
                                                    {team.name}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                    <H2HHistoryPanel playerId={targetId} opponentId={currentOpponent} />
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'Projection' && (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                            <ProjectionMatrix
                                simulation={simulation}
                                loading={simLoading}
                                onRefresh={() => forceRefreshAndRun(currentOpponent)}
                            />

                            <div className="space-y-4">
                                <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-6">
                                    <h3 className="text-lg font-bold text-slate-200 mb-4 flex items-center gap-2">
                                        <span>⚡</span>
                                        Quick Sim
                                    </h3>
                                    <div className="space-y-3">
                                        <label className="block text-sm text-slate-400">Opponent Team</label>
                                        <select
                                            value={currentOpponent}
                                            onChange={(e) => setCurrentOpponent(e.target.value)}
                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-white"
                                        >
                                            {teams.length > 0 ? (
                                                teams.map((team) => (
                                                    <option key={team.team_id} value={team.team_id}>
                                                        {team.name}
                                                    </option>
                                                ))
                                            ) : (
                                                <>
                                                    <option value="1610612744">Golden State Warriors</option>
                                                    <option value="1610612747">Los Angeles Lakers</option>
                                                    <option value="1610612738">Boston Celtics</option>
                                                    <option value="1610612748">Miami Heat</option>
                                                    <option value="1610612743">Denver Nuggets</option>
                                                </>
                                            )}
                                        </select>
                                        <button
                                            onClick={() => runSimulation(currentOpponent)}
                                            disabled={simLoading}
                                            className="w-full py-3 bg-financial-accent/20 hover:bg-financial-accent/30 border border-financial-accent text-financial-accent rounded-lg transition-all disabled:opacity-50"
                                        >
                                            {simLoading ? 'Running...' : '🚀 Run 50,000 Simulations'}
                                        </button>
                                    </div>
                                </div>

                                {simulation && (
                                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
                                        <div className="text-xs text-slate-500 uppercase mb-2">Simulation Info</div>
                                        <div className="grid grid-cols-2 gap-2 text-sm">
                                            <div className="text-slate-400">Archetype:</div>
                                            <div className="text-white font-mono">{simulation.modifiers?.archetype || 'N/A'}</div>
                                            <div className="text-slate-400">Fatigue:</div>
                                            <div className={(simulation.modifiers?.fatigue || 0) < 0 ? 'text-red-400' : 'text-emerald-400'}>
                                                {(simulation.modifiers?.fatigue || 0) !== 0 ? `${(simulation.modifiers?.fatigue || 0) > 0 ? '+' : ''}${((simulation.modifiers?.fatigue || 0) * 100).toFixed(0)}%` : 'None'}
                                            </div>
                                            <div className="text-slate-400">Usage Boost:</div>
                                            <div className="text-purple-400">
                                                {(simulation.modifiers?.usage_boost || 0) > 0 ? `+${((simulation.modifiers?.usage_boost || 0) * 100).toFixed(0)}%` : 'None'}
                                            </div>
                                            <div className="text-slate-400">Runtime:</div>
                                            <div className="text-slate-300 font-mono">{simulation.execution_time_ms}ms</div>
                                        </div>

                                        {/* Refresh status indicator */}
                                        {refreshStatus && (
                                            <div className="mt-3 pt-3 border-t border-slate-700">
                                                <div className="text-xs text-emerald-400">
                                                    ✓ {refreshStatus.message}
                                                    {refreshStatus.gamesAdded > 0 && ` (+${refreshStatus.gamesAdded} games)`}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {activeTab === 'Matchup' && (
                        <>
                            {matchupData && matchupData.insight ? (
                                <div className="space-y-6">
                                    <InsightBanner
                                        text={matchupData.insight?.text || 'Analyzing matchup...'}
                                        type={matchupData.insight?.type || 'neutral'}
                                    />

                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                        <MatchupRadar
                                            playerStats={radarData.player || { scoring: 50, playmaking: 50, rebounding: 50, defense: 50, pace: 50 }}
                                            opponentDefense={radarData.opponent || { scoring: 50, playmaking: 50, rebounding: 50, defense: 50, pace: 50 }}
                                        />

                                        <div className="space-y-4">
                                            <MetricCard
                                                title="Points Over Avg (Bleed)"
                                                value={matchupData.defense_matrix?.paoa ?
                                                    (matchupData.defense_matrix.paoa > 0 ? `+${matchupData.defense_matrix.paoa}` : `${matchupData.defense_matrix.paoa}`)
                                                    : 'N/A'}
                                                subValue={matchupData.defense_matrix?.paoa && matchupData.defense_matrix.paoa > 0 ? "Favorable Matchup" : "Unfavorable Logic"}
                                                className={matchupData.defense_matrix?.paoa && matchupData.defense_matrix.paoa > 0 ? "border-emerald-500/30 bg-emerald-900/10" : ""}
                                            />
                                            <MetricCard
                                                title="Nemesis Vector"
                                                value={matchupData.nemesis_vector?.grade || 'N/A'}
                                                subValue={matchupData.nemesis_vector?.status || ''}
                                            />
                                            <MetricCard
                                                title="Pace Friction"
                                                value={matchupData.pace_friction?.multiplier ? `${matchupData.pace_friction.multiplier}x` : 'N/A'}
                                                subValue={matchupData.pace_friction?.projected_pace ? `Projected Pace: ${matchupData.pace_friction.projected_pace}` : ''}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="p-8 text-slate-500 animate-pulse">Loading Matchup Matrix...</div>
                            )}
                        </>
                    )}

                    {activeTab === 'Advanced' && (
                        <div className="space-y-6">
                            {/* Play Type Efficiency - Full Width */}
                            {targetId && (
                                <PlayTypeEfficiency playerId={targetId} />
                            )}

                            {/* Advanced Metrics Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                <MetricCard title="True Shooting %" value="62.4%" subValue="League Avg: 57.1%" />
                                <MetricCard title="Usage Rate" value="28.3%" subValue="High Volume" />
                                <MetricCard title="PER" value="24.7" subValue="Elite Efficiency" />
                                <MetricCard title="Win Shares" value="8.2" subValue="Season Total" />
                                <MetricCard title="BPM" value="+6.8" subValue="Box Plus/Minus" />
                                <MetricCard title="VORP" value="4.3" subValue="Value Over Replacement" />

                                <div className="md:col-span-2 lg:col-span-3 bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-6">
                                    <h3 className="text-lg font-bold text-slate-200 mb-4">Advanced Metrics Breakdown</h3>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                        <div className="bg-slate-900/50 p-3 rounded">
                                            <div className="text-xs text-slate-500 uppercase mb-1">AST%</div>
                                            <div className="text-lg font-mono text-blue-400">32.1%</div>
                                        </div>
                                        <div className="bg-slate-900/50 p-3 rounded">
                                            <div className="text-xs text-slate-500 uppercase mb-1">REB%</div>
                                            <div className="text-lg font-mono text-green-400">18.5%</div>
                                        </div>
                                        <div className="bg-slate-900/50 p-3 rounded">
                                            <div className="text-xs text-slate-500 uppercase mb-1">STL%</div>
                                            <div className="text-lg font-mono text-yellow-400">2.3%</div>
                                        </div>
                                        <div className="bg-slate-900/50 p-3 rounded">
                                            <div className="text-xs text-slate-500 uppercase mb-1">BLK%</div>
                                            <div className="text-lg font-mono text-red-400">1.8%</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'ShotChart' && (
                        <div className="space-y-6">
                            <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 rounded-xl p-8">
                                <h3 className="text-lg font-bold text-slate-200 mb-6 flex items-center gap-2">
                                    <span>🎯</span>
                                    Shot Distribution Heat Map
                                </h3>
                                <div className="aspect-square max-w-2xl mx-auto bg-slate-900/50 rounded-lg border border-dashed border-slate-700 flex items-center justify-center">
                                    <div className="text-center text-slate-500">
                                        <div className="text-4xl mb-4">🏀</div>
                                        <div className="text-sm">Shot Chart Visualization</div>
                                        <div className="text-xs opacity-50 mt-2">Coming Soon</div>
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <MetricCard title="3PT%" value="38.2%" subValue="Above League Avg" />
                                <MetricCard title="FG% (Paint)" value="64.1%" subValue="Elite Finishing" />
                                <MetricCard title="Mid-Range %" value="42.7%" subValue="Solid" />
                            </div>
                        </div>
                    )}
                </div>

                {/* Data Provenance Footer - Fixed spacing */}
                {profile && (
                    <div className="mt-8 pt-6 border-t border-slate-800">
                        <DataProvenanceBadge
                            status={freshness.status === 'checking' ? 'fresh' : freshness.status}
                            lastUpdated={freshness.lastUpdated}
                            source={freshness.source}
                            onRefresh={handleForceRefresh}
                            isRefreshing={isRefreshing}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
