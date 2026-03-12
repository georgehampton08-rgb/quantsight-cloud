import React, { useState, useEffect } from 'react';
import { ApiContract } from '../api/client';
import CornerBrackets from '../components/common/CornerBrackets';

// Types
interface Game {
    game_id: string;
    home_team: string;
    away_team: string;
    game_time: string;
    status: string;
    display: string;
}

interface StatProjection {
    baseline: number;
    projected: number;
    delta: number;
    h2h_avg: number | null;
    h2h_games: number;
    grade: string;
    grade_label: string;
    form: string;
    confidence: number;
}

interface PlayerProjection {
    player_id: string;
    player_name: string;
    team: string;
    position?: string;
    opponent: string;
    projections: {
        pts: StatProjection;
        reb: StatProjection;
        ast: StatProjection;
        '3pm': StatProjection;
    };
    form_label: string;
    classification?: 'TARGET' | 'FADE' | 'NEUTRAL';
    overall_grade?: string;
    aggregate_score?: number;
    injury_status?: string;
    is_available?: boolean;
}

interface Insights {
    summary: string;
    top_plays: any[];
    fade_plays: any[];
    ai_powered: boolean;
}

interface AnalysisResult {
    success: boolean;
    game: string;
    projections: PlayerProjection[];
    insights: Insights;
    ai_powered: boolean;
    matchup_context: any;
}

// Grade color mapping
const gradeColors: Record<string, string> = {
    'A+': '#00ff88',
    'A': '#22D3EE',
    'B': '#f59e0b',
    'C': '#f59e0b',
    'D': '#ef4444',
    'D-': '#ef4444',
    'F': '#ef4444',
    '?': '#94a3b8',
};

const formIcons: Record<string, string> = {
    'HOT': 'UP',
    'COLD': 'DN',
    'UP': 'UP',
    'DOWN': 'DN',
    'RISING': 'UP',
    'COOLING': 'DN',
    'STEADY': 'EQ',
    'NEUTRAL': 'EQ',
};

// Classification colors
const classificationStyles: Record<string, { bg: string; text: string }> = {
    'TARGET': { bg: 'bg-cyber-green/10', text: 'text-cyber-green' },
    'FADE': { bg: 'bg-cyber-red/10', text: 'text-cyber-red' },
    'NEUTRAL': { bg: 'bg-cyber-surface', text: 'text-cyber-muted' },
};

// Position badge colors
const positionColors: Record<string, string> = {
    'G': 'text-cyber-blue', 'PG': 'text-cyber-blue', 'SG': 'text-cyber-blue',
    'F': 'text-cyber-gold', 'SF': 'text-cyber-gold', 'PF': 'text-cyber-gold',
    'C': 'text-cyber-green',
};

const MatchupLabPage: React.FC = () => {
    const [games, setGames] = useState<Game[]>([]);
    const [selectedGame, setSelectedGame] = useState<Game | null>(null);
    const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [loadingGames, setLoadingGames] = useState(true);
    const [activeStat, setActiveStat] = useState<'pts' | 'reb' | 'ast' | '3pm'>('pts');
    const [activeTeam, setActiveTeam] = useState<'all' | 'home' | 'away'>('all');
    const [error, setError] = useState<string | null>(null);

    // Fetch games on mount
    useEffect(() => {
        fetchGames();
    }, []);

    const fetchGames = async () => {
        try {
            setLoadingGames(true);
            const res = await ApiContract.execute<any>('getMatchupLabGames', { path: 'matchup-lab/games' });
            const data = res.data;
            setGames(data.games || []);
            if (data.games?.length > 0) {
                setSelectedGame(data.games[0]);
            }
        } catch (err) {
            console.error('Failed to fetch games:', err);
            setError('Failed to load games');
        } finally {
            setLoadingGames(false);
        }
    };

    // Auto-analyze when game is selected
    useEffect(() => {
        if (selectedGame && !analysis) {
            analyzeMatchup();
        }
    }, [selectedGame]);

    const analyzeMatchup = async () => {
        if (!selectedGame) return;

        setLoading(true);
        setError(null);
        setAnalysis(null);

        try {
            // Use new endpoint with query params
            const params = new URLSearchParams({
                game_id: selectedGame.game_id,
                home_team: selectedGame.home_team,
                away_team: selectedGame.away_team
            });

            const res = await ApiContract.execute<any>('analyzeMatchupLab', {
                path: `matchup/analyze?${params.toString()}`
            });
            const data = res.data;

            if (data.success) {
                setAnalysis(data as AnalysisResult);
            } else {
                // Handle error - convert objects to strings
                const errorMsg = typeof data.detail === 'object'
                    ? JSON.stringify(data.detail)
                    : (data.detail || 'Analysis failed');
                setError(errorMsg);
            }
        } catch (err) {
            console.error('Analysis error:', err);
            setError('Failed to analyze matchup');
        } finally {
            setLoading(false);
        }
    };

    const renderGradeChip = (grade: string) => (
        <span
            className="px-2 py-0.5 text-[10px] font-mono font-bold tracking-widest text-cyber-bg rounded-none"
            style={{ backgroundColor: gradeColors[grade] || '#666' }}
        >
            {grade}
        </span>
    );

    const renderFormIcon = (form: string) => (
        <span className="font-mono text-[10px] tracking-widest text-cyber-muted px-1 border border-cyber-border/50" title={form}>
            {formIcons[form] || 'EQ'}
        </span>
    );

    const renderProjectionRow = (player: PlayerProjection) => {
        const statKey = activeStat as keyof typeof player.projections;
        const proj = player.projections[statKey];
        if (!proj) return null;

        const deltaClass = proj.delta > 0 ? 'text-cyber-green' : proj.delta < 0 ? 'text-cyber-red' : 'text-cyber-muted';
        const classStyle = classificationStyles[player.classification || 'NEUTRAL'];
        const posColor = positionColors[player.position || 'G'] || 'text-cyber-muted';

        return (
            <tr key={`${player.player_id}-${activeStat}`} className="border-b border-cyber-border/50 hover:bg-white/[0.03] transition-colors">
                <td className="p-3 sticky left-0 z-10 bg-cyber-surface shadow-[4px_0_12px_rgba(0,0,0,0.5)]">
                    <div className="flex items-center gap-3">
                        <img
                            src={`https://cdn.nba.com/headshots/nba/latest/260x190/${player.player_id}.png`}
                            alt={player.player_name}
                            className="w-8 h-8 object-cover object-top border border-cyber-border rounded-none"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                        />
                        <div className="flex flex-col">
                            <span className="font-display font-600 tracking-[0.05em] uppercase text-cyber-text text-xs whitespace-nowrap">{player.player_name}</span>
                            {player.position && (
                                <span className={`font-mono text-[9px] tracking-widest ${posColor}`}>
                                    {player.position}
                                </span>
                            )}
                        </div>
                    </div>
                </td>
                <td className="p-3">
                    <span className={`px-2 py-1 text-[9px] font-display font-600 tracking-widest uppercase border border-cyber-border/50 ${classStyle.bg} ${classStyle.text}`}>
                        {player.classification || 'NEUTRAL'}
                    </span>
                </td>
                <td className="p-3 font-mono text-cyber-muted tabular-nums">{proj.baseline.toFixed(1)}</td>
                <td className="p-3 font-mono font-bold text-cyber-text tabular-nums">{proj.projected.toFixed(1)}</td>
                <td className={`p-3 font-mono font-bold tabular-nums ${deltaClass}`}>
                    {proj.delta > 0 ? '+' : ''}{proj.delta.toFixed(1)}
                </td>
                <td className="p-3">{renderGradeChip(proj.grade)}</td>
                <td className="p-3 font-mono text-xs text-cyber-muted tabular-nums">
                    {proj.h2h_avg !== null ? `${proj.h2h_avg.toFixed(1)} (${proj.h2h_games}g)` : '-'}
                </td>
                <td className="p-3">{renderFormIcon(player.form_label)}</td>
                <td className="p-3">
                    <div className="relative w-16 h-1 border border-cyber-border/50 bg-black overflow-hidden mt-1">
                        <div
                            className="absolute top-0 left-0 h-full bg-cyber-blue shadow-[0_0_8px_rgba(34,211,238,0.5)]"
                            style={{ width: `${proj.confidence}%` }}
                        />
                    </div>
                    <span className="font-mono text-[9px] tracking-widest text-cyber-text mt-1 block">{proj.confidence}%</span>
                </td>
            </tr>
        );
    };

    return (
        <div className="h-full flex flex-col w-full bg-cyber-bg font-sans">
            {/* Header */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                 style={{
                   backgroundImage: 'linear-gradient(#00ff88 1px, transparent 1px), linear-gradient(90deg, #00ff88 1px, transparent 1px)',
                   backgroundSize: '32px 32px',
                 }} />
            <header className="flex-shrink-0 border-b border-cyber-border bg-cyber-bg relative z-10 px-6 py-4">
                <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between md:items-center gap-4">
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text flex items-center gap-3 border-l-4 border-cyber-blue pl-2">
                            Matchup Lab
                        </h1>
                        <span className="text-[9px] bg-cyber-blue/10 text-cyber-blue border border-cyber-blue px-2 py-0.5 rounded-none font-display font-600 uppercase tracking-[0.2em] shadow-[0_0_8px_rgba(34,211,238,0.2)]">AI-Powered</span>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
                        {loadingGames ? (
                            <div className="text-[10px] font-mono tracking-widest text-cyber-muted uppercase animate-pulse">Loading games...</div>
                        ) : (
                            <>
                                <select
                                    value={selectedGame?.game_id || ''}
                                    onChange={(e) => {
                                        const game = games.find(g => g.game_id === e.target.value);
                                        setSelectedGame(game || null);
                                        setAnalysis(null);
                                    }}
                                    className="bg-cyber-surface border border-cyber-border rounded-none px-3 py-2 text-[10px] font-mono tracking-widest uppercase text-cyber-text outline-none focus:border-cyber-blue transition-colors"
                                >
                                    {games.map(g => (
                                        <option key={g.game_id} value={g.game_id}>
                                            {g.status === 'live' ? 'LIVE: ' : g.status === 'final' ? 'FINAL: ' : 'UPCOMING: '}
                                            {g.display}
                                        </option>
                                    ))}
                                </select>

                                <button
                                    className="bg-cyber-blue/10 hover:bg-cyber-blue/20 border border-cyber-blue text-cyber-blue font-display font-600 tracking-[0.1em] uppercase px-6 py-2 rounded-none transition-all duration-100 disabled:opacity-50 disabled:bg-cyber-surface text-xs whitespace-nowrap"
                                    onClick={analyzeMatchup}
                                    disabled={loading || !selectedGame}
                                >
                                    {loading ? (
                                        <>
                                            <span className="animate-pulse">ANALYZING...</span>
                                        </>
                                    ) : (
                                        <>
                                            ANALYZE MATCHUP
                                        </>
                                    )}
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </header>

            <div className="flex-1 min-h-0 overflow-y-auto w-full relative z-10 p-6">
                <div className="max-w-7xl mx-auto w-full pb-8">
                    {/* Error display */}
                    {error && (
                        <div className="bg-cyber-red/10 border border-cyber-red text-cyber-red p-4 mb-6 rounded-none text-xs font-mono tracking-widest uppercase flex items-center gap-2">
                            <span className="animate-pulse">ERR</span> {error}
                        </div>
                    )}

                    {/* Loading state */}
                    {loading && (
                        <div className="flex flex-col items-center justify-center py-20">
                            <div className="w-16 h-16 border-2 border-dashed border-cyber-blue rounded-full animate-spin mb-4" />
                            <span className="text-cyber-blue font-mono tracking-[0.2em] font-bold uppercase animate-[data-flicker_3s_ease-in-out_infinite]">Calculating Confluence...</span>
                        </div>
                    )}

                    {/* Analysis Results */}
                    {analysis && !loading && (
                        <div className="flex flex-col gap-6">
                            {/* AI Insights Card */}
                            <section className="relative bg-cyber-surface border border-cyber-border p-6 shadow-none" style={{ border: '1px solid #1a2332' }}>
                                <CornerBrackets />
                                <div className="flex items-center justify-between border-b border-cyber-border/50 pb-3 mb-4 relative z-10">
                                    <h2 className="text-[10px] font-display font-700 tracking-[0.2em] uppercase text-cyber-text flex items-center gap-2">
                                        Gemini AI Insights
                                    </h2>
                                    {analysis.ai_powered && <span className="text-[9px] font-mono tracking-widest text-cyber-green bg-cyber-green/10 border border-cyber-green px-2 py-0.5 animate-pulse">LIVE</span>}
                                </div>
                                <div className="relative z-10">
                                    <p className="text-sm font-mono leading-relaxed text-cyber-muted">{analysis.insights?.summary || 'Analyzing matchup data...'}</p>
                                </div>
                            </section>

                            {/* Top & Fade Plays */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <section className="relative bg-cyber-surface border border-cyber-border p-6 shadow-none" style={{ border: '1px solid #1a2332' }}>
                                    <CornerBrackets />
                                    <div className="border-b border-cyber-border/50 pb-3 mb-4 relative z-10">
                                        <h2 className="text-[10px] font-display font-700 tracking-[0.2em] uppercase text-cyber-green flex items-center gap-2">
                                            Top Target Plays
                                        </h2>
                                    </div>
                                    <ul className="flex flex-col gap-2 relative z-10">
                                        {(analysis.insights?.top_plays || []).slice(0, 5).map((play: any, i: number) => (
                                            <li key={i} className="flex flex-wrap sm:flex-nowrap items-center gap-3 p-3 bg-cyber-green/5 border-l-2 border-cyber-green hover:bg-cyber-green/10 transition-colors">
                                                <span className="font-display font-600 uppercase tracking-widest text-cyber-text text-xs flex-grow">{play.player}</span>
                                                <span className="font-mono text-[10px] bg-cyber-surface border border-cyber-border px-2 py-0.5 text-cyber-muted">{play.stat}</span>
                                                <span className="font-mono font-bold text-cyber-green tabular-nums">{play.projected?.toFixed(1)}</span>
                                                {renderGradeChip(play.grade)}
                                            </li>
                                        ))}
                                    </ul>
                                </section>

                                <section className="relative bg-cyber-surface border border-cyber-border p-6 shadow-none" style={{ border: '1px solid #1a2332' }}>
                                    <CornerBrackets />
                                    <div className="border-b border-cyber-border/50 pb-3 mb-4 relative z-10">
                                        <h2 className="text-[10px] font-display font-700 tracking-[0.2em] uppercase text-cyber-red flex items-center gap-2">
                                            Identified Fade Targets
                                        </h2>
                                    </div>
                                    <ul className="flex flex-col gap-2 relative z-10">
                                        {(analysis.insights?.fade_plays || []).slice(0, 5).map((play: any, i: number) => (
                                            <li key={i} className="flex flex-wrap sm:flex-nowrap items-center gap-3 p-3 bg-cyber-red/5 border-l-2 border-cyber-red hover:bg-cyber-red/10 transition-colors">
                                                <span className="font-display font-600 uppercase tracking-widest text-cyber-text text-xs flex-grow">{play.player}</span>
                                                <span className="font-mono text-[10px] bg-cyber-surface border border-cyber-border px-2 py-0.5 text-cyber-muted">{play.stat}</span>
                                                <span className="font-mono font-bold text-cyber-red tabular-nums">{play.projected?.toFixed(1)}</span>
                                                <span className="font-mono text-[9px] text-cyber-red tracking-widest hidden sm:block truncate w-32" title={play.reason}>{play.reason}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </section>
                            </div>

                            {/* Projections Table */}
                            <section className="relative bg-cyber-surface border border-cyber-border p-0 sm:p-6 shadow-none flex flex-col" style={{ border: '1px solid #1a2332' }}>
                                <CornerBrackets />
                                <div className="p-4 sm:p-0 flex flex-col sm:flex-row justify-between sm:items-end gap-4 border-b border-cyber-border/50 pb-4 mb-4 relative z-10">
                                    <h2 className="text-[10px] font-display font-700 tracking-[0.2em] uppercase text-cyber-text">Player Projections</h2>

                                    <div className="flex flex-wrap gap-2">
                                        {(['pts', 'reb', 'ast', '3pm'] as const).map(stat => (
                                            <button
                                                key={stat}
                                                className={`px-3 py-1 text-[10px] font-display font-600 tracking-[0.1em] uppercase border transition-colors ${activeStat === stat ? 'bg-cyber-blue/10 border-cyber-blue text-cyber-blue' : 'bg-transparent border-cyber-border text-cyber-muted hover:text-cyber-text'}`}
                                                onClick={() => setActiveStat(stat)}
                                            >
                                                {stat?.toUpperCase() || ''}
                                            </button>
                                        ))}
                                    </div>

                                    {/* Team Tabs */}
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            className={`px-3 py-1 text-[10px] font-display font-600 tracking-[0.1em] uppercase border transition-colors ${activeTeam === 'all' ? 'bg-cyber-surface border-cyber-muted text-cyber-text' : 'bg-transparent border-cyber-border text-cyber-muted hover:text-cyber-text'}`}
                                            onClick={() => setActiveTeam('all')}
                                        >
                                            All Players
                                        </button>
                                        <button
                                            className={`px-3 py-1 text-[10px] font-display font-600 tracking-[0.1em] uppercase border transition-colors ${activeTeam === 'home' ? 'bg-cyber-surface border-cyber-muted text-cyber-text' : 'bg-transparent border-cyber-border text-cyber-muted hover:text-cyber-text'}`}
                                            onClick={() => setActiveTeam('home')}
                                        >
                                            [H] {selectedGame?.home_team || 'Home'}
                                        </button>
                                        <button
                                            className={`px-3 py-1 text-[10px] font-display font-600 tracking-[0.1em] uppercase border transition-colors ${activeTeam === 'away' ? 'bg-cyber-surface border-cyber-muted text-cyber-text' : 'bg-transparent border-cyber-border text-cyber-muted hover:text-cyber-text'}`}
                                            onClick={() => setActiveTeam('away')}
                                        >
                                            [A] {selectedGame?.away_team || 'Away'}
                                        </button>
                                    </div>
                                </div>

                                <div className="overflow-x-auto w-full relative z-10 scrollbar-premium">
                                    <table className="w-full text-left border-collapse min-w-[800px]">
                                        <thead>
                                            <tr className="border-b border-cyber-border/50 bg-cyber-surface text-cyber-muted text-[10px] font-display font-600 tracking-[0.2em] uppercase">
                                                <th className="p-3 sticky left-0 z-20 bg-cyber-surface shadow-[4px_0_12px_rgba(0,0,0,0.5)]">Player</th>
                                                <th className="p-3">Class</th>
                                                <th className="p-3">Base</th>
                                                <th className="p-3 text-cyber-text">Proj</th>
                                                <th className="p-3">Δ</th>
                                                <th className="p-3">Grade</th>
                                                <th className="p-3">H2H Avg</th>
                                                <th className="p-3">Form</th>
                                                <th className="p-3">Conf</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {analysis.projections
                                                .filter(p => {
                                                    if (activeTeam === 'all') return true;
                                                    if (activeTeam === 'home') return p.team === selectedGame?.home_team;
                                                    if (activeTeam === 'away') return p.team === selectedGame?.away_team;
                                                    return true;
                                                })
                                                .sort((a, b) => {
                                                    const projA = a.projections[activeStat];
                                                    const projB = b.projections[activeStat];
                                                    return (projB?.projected || 0) - (projA?.projected || 0);
                                                })
                                                .map(player => renderProjectionRow(player))}
                                        </tbody>
                                    </table>
                                </div>
                            </section>

                            {/* Matchup Context */}
                            <section className="relative bg-cyber-surface border border-cyber-border p-6 shadow-none" style={{ border: '1px solid #1a2332' }}>
                                <CornerBrackets />
                                <div className="border-b border-cyber-border/50 pb-3 mb-4 relative z-10">
                                    <h2 className="text-[10px] font-display font-700 tracking-[0.2em] uppercase text-cyber-text">Matchup Context Matrix</h2>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative z-10">
                                    <div className="flex flex-col text-center p-4 bg-white/[0.02] border border-cyber-border/50">
                                        <span className="text-[10px] font-display tracking-widest text-cyber-muted uppercase mb-2">Projected Pace</span>
                                        <span className="text-2xl font-mono font-bold text-cyber-text">
                                            {analysis.matchup_context?.projected_pace?.toFixed(1) || 'N/A'}
                                        </span>
                                    </div>
                                    <div className="flex flex-col text-center p-4 bg-white/[0.02] border border-cyber-border/50">
                                        <span className="text-[10px] font-display tracking-widest text-cyber-muted uppercase mb-2">[{selectedGame?.home_team}] DEF Rating</span>
                                        <span className="text-2xl font-mono font-bold text-cyber-text">
                                            {analysis.matchup_context?.home_defense?.opp_pts?.toFixed(1) || 'N/A'} PPG
                                        </span>
                                    </div>
                                    <div className="flex flex-col text-center p-4 bg-white/[0.02] border border-cyber-border/50">
                                        <span className="text-[10px] font-display tracking-widest text-cyber-muted uppercase mb-2">[{selectedGame?.away_team}] DEF Rating</span>
                                        <span className="text-2xl font-mono font-bold text-cyber-text">
                                            {analysis.matchup_context?.away_defense?.opp_pts?.toFixed(1) || 'N/A'} PPG
                                        </span>
                                    </div>
                                </div>
                            </section>
                        </div>
                    )}

                    {/* Empty State */}
                    {!analysis && !loading && !error && (
                        <div className="flex flex-col items-center justify-center p-16 mt-8 relative bg-cyber-surface border border-cyber-border shadow-none" style={{ border: '1px solid #1a2332' }}>
                            <CornerBrackets />
                            <div className="relative w-16 h-16 flex items-center justify-center mb-6">
                                <div className="absolute inset-0 border border-cyber-blue opacity-50 rotate-45 animate-[spin_10s_linear_infinite]" />
                                <span className="text-cyber-blue font-mono font-bold tracking-[0.2em] relative z-10">STANDBY</span>
                            </div>
                            <h2 className="text-xl font-display font-700 tracking-[0.1em] uppercase block text-cyber-text mb-2">Select a Game to Analyze</h2>
                            <p className="text-[10px] font-mono tracking-widest uppercase text-cyber-muted text-center max-w-sm">Choose a matchup and initiate sequence to generate AI-powered projections.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MatchupLabPage;
