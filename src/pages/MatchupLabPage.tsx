import React, { useState, useEffect } from 'react';
import './MatchupLabPage.css';
import { ApiContract } from '../api/client';

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
    'A': '#22dd66',
    'B': '#88cc44',
    'C': '#ccaa22',
    'D': '#ff8844',
    'D-': '#ff6622',
    'F': '#ff4444',
    '?': '#666666',
};

const formIcons: Record<string, string> = {
    'HOT': '🔥',
    'COLD': '❄️',
    'UP': '📈',
    'DOWN': '📉',
    'RISING': '📈',
    'COOLING': '📉',
    'STEADY': '➖',
    'NEUTRAL': '➖',
};

// Classification colors
const classificationStyles: Record<string, { bg: string; text: string; icon: string }> = {
    'TARGET': { bg: '#22c55e20', text: '#22c55e', icon: '🎯' },
    'FADE': { bg: '#ef444420', text: '#ef4444', icon: '🚫' },
    'NEUTRAL': { bg: '#94a3b820', text: '#94a3b8', icon: '➖' },
};

// Position badge colors
const positionColors: Record<string, string> = {
    'G': '#3b82f6', 'PG': '#3b82f6', 'SG': '#3b82f6',
    'F': '#f59e0b', 'SF': '#f59e0b', 'PF': '#f59e0b',
    'C': '#8b5cf6',
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
            className="grade-chip"
            style={{ backgroundColor: gradeColors[grade] || '#666' }}
        >
            {grade}
        </span>
    );

    const renderFormIcon = (form: string) => (
        <span className="form-icon" title={form}>
            {formIcons[form] || '➖'}
        </span>
    );

    const renderProjectionRow = (player: PlayerProjection) => {
        const statKey = activeStat as keyof typeof player.projections;
        const proj = player.projections[statKey];
        if (!proj) return null;

        const deltaClass = proj.delta > 0 ? 'positive' : proj.delta < 0 ? 'negative' : 'neutral';
        const classStyle = classificationStyles[player.classification || 'NEUTRAL'];
        const posColor = positionColors[player.position || 'G'] || '#666';

        return (
            <tr key={`${player.player_id}-${activeStat}`} className="projection-row">
                <td className="player-name">
                    <img
                        src={`https://cdn.nba.com/headshots/nba/latest/260x190/${player.player_id}.png`}
                        alt={player.player_name}
                        className="player-mini-avatar"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                    <div className="player-info">
                        <span>{player.player_name}</span>
                        {player.position && (
                            <span className="position-badge" style={{ background: posColor }}>
                                {player.position}
                            </span>
                        )}
                    </div>
                </td>
                <td className="team">
                    <span className="classification-badge" style={{ background: classStyle.bg, color: classStyle.text }}>
                        {classStyle.icon} {player.classification || 'NEUTRAL'}
                    </span>
                </td>
                <td className="baseline">{proj.baseline.toFixed(1)}</td>
                <td className="projected">{proj.projected.toFixed(1)}</td>
                <td className={`delta ${deltaClass}`}>
                    {proj.delta > 0 ? '+' : ''}{proj.delta.toFixed(1)}
                </td>
                <td className="grade">{renderGradeChip(proj.grade)}</td>
                <td className="h2h">
                    {proj.h2h_avg !== null ? `${proj.h2h_avg.toFixed(1)} (${proj.h2h_games}g)` : '-'}
                </td>
                <td className="form">{renderFormIcon(player.form_label)}</td>
                <td className="confidence">
                    <div className="confidence-bar">
                        <div
                            className="confidence-fill"
                            style={{ width: `${proj.confidence}%` }}
                        />
                        <span>{proj.confidence}%</span>
                    </div>
                </td>
            </tr>
        );
    };

    return (
        <div className="matchup-lab-page h-full flex flex-col w-full">
            {/* Header */}
            <header className="lab-header flex-shrink-0">
                <div className="header-content max-w-7xl mx-auto">
                    <div className="header-title">
                        <span className="lab-icon">🔬</span>
                        <h1>Matchup Lab</h1>
                        <span className="ai-badge">AI-Powered</span>
                    </div>

                    <div className="game-selector">
                        {loadingGames ? (
                            <div className="loading-games">Loading games...</div>
                        ) : (
                            <>
                                <select
                                    value={selectedGame?.game_id || ''}
                                    onChange={(e) => {
                                        const game = games.find(g => g.game_id === e.target.value);
                                        setSelectedGame(game || null);
                                        setAnalysis(null);
                                    }}
                                >
                                    {games.map(g => (
                                        <option key={g.game_id} value={g.game_id}>
                                            {g.status === 'live' ? '🔴 ' : g.status === 'final' ? '✅ ' : '⏰ '}
                                            {g.display}
                                        </option>
                                    ))}
                                </select>

                                <button
                                    className="analyze-btn"
                                    onClick={analyzeMatchup}
                                    disabled={loading || !selectedGame}
                                >
                                    {loading ? (
                                        <>
                                            <span className="spinner" />
                                            Analyzing...
                                        </>
                                    ) : (
                                        <>
                                            <span className="btn-icon">🔮</span>
                                            Analyze Matchup
                                        </>
                                    )}
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </header>

            <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="max-w-7xl mx-auto w-full pb-8">
                    {/* Error display */}
                    {error && (
                        <div className="error-banner">
                            <span>⚠️</span> {error}
                        </div>
                    )}

                    {/* Loading state */}
                    {loading && (
                        <div className="loading-overlay">
                            <div className="loading-content">
                                <div className="pulse-ring" />
                                <span>Calculating Confluence...</span>
                            </div>
                        </div>
                    )}

                    {/* Analysis Results */}
                    {analysis && !loading && (
                        <div className="analysis-results">
                            {/* AI Insights Card */}
                            <section className="insights-card glass-card">
                                <div className="card-header">
                                    <span className="card-icon">🤖</span>
                                    <h2>Gemini AI Insights</h2>
                                    {analysis.ai_powered && <span className="ai-live-badge">LIVE</span>}
                                </div>
                                <div className="insights-content">
                                    <p className="ai-summary">{analysis.insights?.summary || 'Analyzing matchup data...'}</p>
                                </div>
                            </section>

                            {/* Top & Fade Plays */}
                            <div className="plays-grid">
                                <section className="top-plays glass-card">
                                    <div className="card-header">
                                        <span className="card-icon">🔥</span>
                                        <h2>Top Plays</h2>
                                    </div>
                                    <ul className="plays-list">
                                        {(analysis.insights?.top_plays || []).slice(0, 5).map((play: any, i: number) => (
                                            <li key={i} className="play-item top">
                                                <span className="play-player">{play.player}</span>
                                                <span className="play-stat">{play.stat}</span>
                                                <span className="play-proj">{play.projected?.toFixed(1)}</span>
                                                {renderGradeChip(play.grade)}
                                            </li>
                                        ))}
                                    </ul>
                                </section>

                                <section className="fade-plays glass-card">
                                    <div className="card-header">
                                        <span className="card-icon">❄️</span>
                                        <h2>Fade Plays</h2>
                                    </div>
                                    <ul className="plays-list">
                                        {(analysis.insights?.fade_plays || []).slice(0, 5).map((play: any, i: number) => (
                                            <li key={i} className="play-item fade">
                                                <span className="play-player">{play.player}</span>
                                                <span className="play-stat">{play.stat}</span>
                                                <span className="play-proj">{play.projected?.toFixed(1)}</span>
                                                <span className="play-reason">{play.reason}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </section>
                            </div>

                            {/* Projections Table */}
                            <section className="projections-section glass-card">
                                <div className="card-header">
                                    <span className="card-icon">📊</span>
                                    <h2>Player Projections</h2>

                                    <div className="stat-tabs">
                                        {(['pts', 'reb', 'ast', '3pm'] as const).map(stat => (
                                            <button
                                                key={stat}
                                                className={`stat-tab ${activeStat === stat ? 'active' : ''}`}
                                                onClick={() => setActiveStat(stat)}
                                            >
                                                {stat?.toUpperCase() || ''}
                                            </button>
                                        ))}
                                    </div>

                                    {/* Team Tabs */}
                                    <div className="team-tabs">
                                        <button
                                            className={`team-tab ${activeTeam === 'all' ? 'active' : ''}`}
                                            onClick={() => setActiveTeam('all')}
                                        >
                                            All Players
                                        </button>
                                        <button
                                            className={`team-tab ${activeTeam === 'home' ? 'active' : ''}`}
                                            onClick={() => setActiveTeam('home')}
                                        >
                                            🏠 {selectedGame?.home_team || 'Home'}
                                        </button>
                                        <button
                                            className={`team-tab ${activeTeam === 'away' ? 'active' : ''}`}
                                            onClick={() => setActiveTeam('away')}
                                        >
                                            ✈️ {selectedGame?.away_team || 'Away'}
                                        </button>
                                    </div>
                                </div>

                                <div className="table-container">
                                    <table className="projections-table">
                                        <thead>
                                            <tr>
                                                <th>Player</th>
                                                <th>Class</th>
                                                <th>Base</th>
                                                <th>Proj</th>
                                                <th>Δ</th>
                                                <th>Grade</th>
                                                <th>H2H</th>
                                                <th>Form</th>
                                                <th>Conf</th>
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
                            <section className="context-card glass-card">
                                <div className="card-header">
                                    <span className="card-icon">⚡</span>
                                    <h2>Matchup Context</h2>
                                </div>
                                <div className="context-grid">
                                    <div className="context-item">
                                        <span className="context-label">Pace</span>
                                        <span className="context-value">
                                            {analysis.matchup_context?.projected_pace?.toFixed(1) || 'N/A'}
                                        </span>
                                    </div>
                                    <div className="context-item">
                                        <span className="context-label">{selectedGame?.home_team} DEF</span>
                                        <span className="context-value">
                                            {analysis.matchup_context?.home_defense?.opp_pts?.toFixed(1) || 'N/A'} PPG
                                        </span>
                                    </div>
                                    <div className="context-item">
                                        <span className="context-label">{selectedGame?.away_team} DEF</span>
                                        <span className="context-value">
                                            {analysis.matchup_context?.away_defense?.opp_pts?.toFixed(1) || 'N/A'} PPG
                                        </span>
                                    </div>
                                </div>
                            </section>
                        </div>
                    )}

                    {/* Empty State */}
                    {!analysis && !loading && !error && (
                        <div className="empty-state">
                            <div className="empty-icon">🔬</div>
                            <h2>Select a Game to Analyze</h2>
                            <p>Choose a matchup and click "Analyze Matchup" to generate AI-powered projections.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default MatchupLabPage;
