/**
 * Matchup War Room
 * ================
 * Team-to-team comparison dashboard with live roster validation.
 * 
 * Features:
 * - Dual dropdown team selectors (default: Tonight's Games)
 * - Health light indicators (green/yellow/red)
 * - Potential Heat Map for matchup EV
 * - What-If roster toggles
 */

import React, { useState, useEffect, useCallback } from 'react';
import './MatchupWarRoom.css';

// Types
interface Player {
    player_id: string;
    player_name: string;
    is_active: boolean;
    health_status: 'green' | 'yellow' | 'red';
    ev_points: number;
    ev_rebounds: number;
    ev_assists: number;
    archetype: string;
    matchup_advantage: 'advantaged' | 'countered' | 'neutral';
    friction_modifier: number;
    efficiency_grade: string;
    usage_boost: number;
    vacuum_beneficiary: boolean;
}

interface TeamData {
    team_id: string;
    team_name: string;
    offensive_archetype: string;
    defensive_profile: string;
    active_count: number;
    out_count: number;
    players: Player[];
}

interface MatchupData {
    home_team: TeamData;
    away_team: TeamData;
    matchup_edge: 'home' | 'away' | 'neutral';
    edge_reason: string;
    usage_vacuum_applied: string[];
    execution_time_ms: number;
    game_date: string;
}

interface Team {
    id: string;
    name: string;
    abbreviation: string;
}

interface TodaysGame {
    id: string;
    home_team: string;
    away_team: string;
    home_team_id: string;
    away_team_id: string;
    time: string;
    status: string;
}

// API Base URL
const API_BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app';

// Health Light Component
const HealthLight: React.FC<{ status: 'green' | 'yellow' | 'red' }> = ({ status }) => {
    const colors = {
        green: '#10b981',
        yellow: '#f59e0b',
        red: '#ef4444'
    };

    return (
        <span
            className="health-light"
            style={{ backgroundColor: colors[status] }}
            title={status === 'green' ? 'Active' : status === 'yellow' ? 'Game-Time Decision' : 'Out'}
        />
    );
};

// Matchup Advantage Icon
const MatchupIcon: React.FC<{ advantage: 'advantaged' | 'countered' | 'neutral' }> = ({ advantage }) => {
    const icons = {
        advantaged: { symbol: '⬆️', title: 'Matchup Advantaged', className: 'advantage-up' },
        countered: { symbol: '⬇️', title: 'Matchup Countered', className: 'advantage-down' },
        neutral: { symbol: '➡️', title: 'Neutral Matchup', className: 'advantage-neutral' }
    };

    const { symbol, title, className } = icons[advantage];

    return (
        <span className={`matchup-icon ${className}`} title={title}>
            {symbol}
        </span>
    );
};

// Efficiency Grade Badge
const GradeBadge: React.FC<{ grade: string }> = ({ grade }) => {
    const getGradeClass = (g: string) => {
        if (g.startsWith('A')) return 'grade-a';
        if (g.startsWith('B')) return 'grade-b';
        if (g.startsWith('C')) return 'grade-c';
        if (g.startsWith('D')) return 'grade-d';
        return 'grade-f';
    };

    return (
        <span className={`grade-badge ${getGradeClass(grade)}`}>
            {grade}
        </span>
    );
};

// Team Selector Dropdown
const TeamSelector: React.FC<{
    teams: Team[];
    selectedTeam: Team | null;
    onSelect: (team: Team) => void;
    label: string;
    tonightsGames?: TodaysGame[];
}> = ({ teams, selectedTeam, onSelect, label, tonightsGames }) => {
    return (
        <div className="team-selector">
            <label>{label}</label>
            <select
                value={selectedTeam?.id || ''}
                onChange={(e) => {
                    const team = teams.find(t => t.id === e.target.value);
                    if (team) onSelect(team);
                }}
            >
                <option value="">Select Team...</option>

                {tonightsGames && tonightsGames.length > 0 && (
                    <optgroup label="🏀 Tonight's Games">
                        {tonightsGames.map(game => (
                            <React.Fragment key={game.id}>
                                <option value={game.home_team_id}>
                                    {game.home_team} (Home) - {game.time}
                                </option>
                                <option value={game.away_team_id}>
                                    {game.away_team} (Away) - {game.time}
                                </option>
                            </React.Fragment>
                        ))}
                    </optgroup>
                )}

                <optgroup label="All Teams">
                    {teams.map(team => (
                        <option key={team.id} value={team.id}>
                            {team.name}
                        </option>
                    ))}
                </optgroup>
            </select>
        </div>
    );
};

// Roster Pane with Toggles
const RosterPane: React.FC<{
    team: TeamData;
    excludedPlayers: Set<string>;
    onTogglePlayer: (playerId: string) => void;
}> = ({ team, excludedPlayers, onTogglePlayer }) => {
    return (
        <div className="roster-pane">
            <div className="roster-header">
                <h3>{team.team_name}</h3>
                <div className="team-meta">
                    <span className="archetype-tag offensive">{team.offensive_archetype}</span>
                    <span className="archetype-tag defensive">{team.defensive_profile}</span>
                </div>
                <div className="roster-counts">
                    <span className="count active">{team.active_count} Active</span>
                    <span className="count out">{team.out_count} Out</span>
                </div>
            </div>

            <div className="roster-list">
                {team.players.map(player => (
                    <div
                        key={player.player_id}
                        className={`roster-player ${!player.is_active ? 'out' : ''} ${excludedPlayers.has(player.player_id) ? 'excluded' : ''}`}
                    >
                        <label className="player-toggle">
                            <input
                                type="checkbox"
                                checked={player.is_active && !excludedPlayers.has(player.player_id)}
                                onChange={() => onTogglePlayer(player.player_id)}
                                disabled={!player.is_active}
                            />
                            <HealthLight status={player.health_status} />
                            <span className="player-name">{player.player_name}</span>
                        </label>
                        {player.vacuum_beneficiary && (
                            <span className="vacuum-badge" title="Usage boost from teammate out">
                                ⚡ +{(player.usage_boost * 100).toFixed(1)}%
                            </span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

// Potential Heat Map Grid
const PotentialHeatMap: React.FC<{
    homePlayers: Player[];
    awayPlayers: Player[];
    excludedPlayers: Set<string>;
}> = ({ homePlayers, awayPlayers, excludedPlayers }) => {
    const allPlayers = [
        ...homePlayers.map(p => ({ ...p, side: 'home' as const })),
        ...awayPlayers.map(p => ({ ...p, side: 'away' as const }))
    ]
        .filter(p => p.is_active && !excludedPlayers.has(p.player_id))
        .sort((a, b) => b.ev_points - a.ev_points);

    return (
        <div className="heat-map-container">
            <h3>📊 Potential Heat Map</h3>
            <div className="heat-map-grid">
                <div className="heat-map-header">
                    <span className="col-side">Team</span>
                    <span className="col-player">Player</span>
                    <span className="col-ev">EV Pts</span>
                    <span className="col-ev">EV Reb</span>
                    <span className="col-ev">EV Ast</span>
                    <span className="col-matchup">Matchup</span>
                    <span className="col-archetype">Archetype</span>
                    <span className="col-grade">Grade</span>
                </div>

                {allPlayers.slice(0, 15).map(player => (
                    <div
                        key={player.player_id}
                        className={`heat-map-row side-${player.side}`}
                    >
                        <span className={`col-side side-indicator ${player.side}`}>
                            {player.side === 'home' ? '🏠' : '🚗'}
                        </span>
                        <span className="col-player">
                            <HealthLight status={player.health_status} />
                            {player.player_name}
                        </span>
                        <span className={`col-ev ev-value ${player.ev_points >= 20 ? 'high' : player.ev_points >= 12 ? 'medium' : 'low'}`}>
                            {player.ev_points.toFixed(1)}
                        </span>
                        <span className="col-ev ev-value">{player.ev_rebounds.toFixed(1)}</span>
                        <span className="col-ev ev-value">{player.ev_assists.toFixed(1)}</span>
                        <span className="col-matchup">
                            <MatchupIcon advantage={player.matchup_advantage} />
                        </span>
                        <span className="col-archetype">
                            <span className="archetype-chip">{player.archetype}</span>
                        </span>
                        <span className="col-grade">
                            <GradeBadge grade={player.efficiency_grade} />
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};

// Heartbeat Status Indicator
const HeartbeatStatus: React.FC<{
    status: 'idle' | 'loading' | 'syncing' | 'ready' | 'error';
    message?: string;
}> = ({ status, message }) => {
    const statusConfig = {
        idle: { color: '#64748b', text: 'Ready' },
        loading: { color: '#3b82f6', text: 'Loading...' },
        syncing: { color: '#f59e0b', text: message || 'Syncing rosters...' },
        ready: { color: '#10b981', text: message || 'Sync complete' },
        error: { color: '#ef4444', text: message || 'Error' }
    };

    const config = statusConfig[status];

    return (
        <div className="heartbeat-status" style={{ borderColor: config.color }}>
            <span
                className={`heartbeat-pulse ${status === 'syncing' || status === 'loading' ? 'active' : ''}`}
                style={{ backgroundColor: config.color }}
            />
            <span className="heartbeat-text">{config.text}</span>
        </div>
    );
};

// Main Component
const MatchupWarRoom: React.FC = () => {
    // State
    const [teams, setTeams] = useState<Team[]>([]);
    const [todaysGames, setTodaysGames] = useState<TodaysGame[]>([]);
    const [homeTeam, setHomeTeam] = useState<Team | null>(null);
    const [awayTeam, setAwayTeam] = useState<Team | null>(null);
    const [matchupData, setMatchupData] = useState<MatchupData | null>(null);
    const [excludedPlayers, setExcludedPlayers] = useState<Set<string>>(new Set());
    const [syncStatus, setSyncStatus] = useState<'idle' | 'loading' | 'syncing' | 'ready' | 'error'>('idle');
    const [statusMessage, setStatusMessage] = useState<string>('');
    const [error, setError] = useState<string | null>(null);

    // Fetch teams on mount
    useEffect(() => {
        const fetchTeams = async () => {
            try {
                const response = await fetch(`${API_BASE}/teams`);
                const data = await response.json();
                setTeams(data.teams || []);
            } catch (err) {
                console.error('Failed to fetch teams:', err);
            }
        };

        const fetchTodaysGames = async () => {
            try {
                const response = await fetch(`${API_BASE}/schedule`);
                const data = await response.json();

                // Map games with team IDs
                const games = (data.games || []).map((g: any) => ({
                    ...g,
                    home_team_id: g.home_team_id || '',
                    away_team_id: g.away_team_id || ''
                }));

                setTodaysGames(games);
            } catch (err) {
                console.error('Failed to fetch schedule:', err);
            }
        };

        fetchTeams();
        fetchTodaysGames();
    }, []);

    // Run matchup analysis when both teams selected
    const runMatchup = useCallback(async () => {
        if (!homeTeam || !awayTeam) return;

        setSyncStatus('loading');
        setStatusMessage(`Validating ${homeTeam.name} roster...`);
        setError(null);

        try {
            // Simulate heartbeat communication
            await new Promise(r => setTimeout(r, 300));
            setSyncStatus('syncing');
            setStatusMessage(`Checking ${awayTeam.name} roster...`);

            const response = await fetch(
                `${API_BASE}/aegis/matchup?home_team_id=${homeTeam.id}&away_team_id=${awayTeam.id}`
            );

            if (!response.ok) {
                throw new Error(`Matchup analysis failed: ${response.statusText}`);
            }

            const data = await response.json();
            setMatchupData(data);

            setSyncStatus('ready');
            setStatusMessage(`Analysis complete in ${data.execution_time_ms.toFixed(0)}ms`);

        } catch (err: any) {
            setError(err.message);
            setSyncStatus('error');
            setStatusMessage(err.message);
        }
    }, [homeTeam, awayTeam]);

    // Auto-run matchup when teams change
    useEffect(() => {
        if (homeTeam && awayTeam) {
            setExcludedPlayers(new Set()); // Reset exclusions
            runMatchup();
        }
    }, [homeTeam, awayTeam, runMatchup]);

    // Toggle player exclusion for What-If
    const togglePlayer = (playerId: string) => {
        setExcludedPlayers(prev => {
            const next = new Set(prev);
            if (next.has(playerId)) {
                next.delete(playerId);
            } else {
                next.add(playerId);
            }
            return next;
        });
    };

    return (
        <div className="matchup-war-room">
            <div className="war-room-header">
                <h1>🎯 Matchup War Room</h1>
                <HeartbeatStatus status={syncStatus} message={statusMessage} />
            </div>

            {/* Team Selectors */}
            <div className="team-selectors">
                <TeamSelector
                    teams={teams}
                    selectedTeam={homeTeam}
                    onSelect={setHomeTeam}
                    label="Home Team"
                    tonightsGames={todaysGames}
                />
                <div className="vs-divider">VS</div>
                <TeamSelector
                    teams={teams}
                    selectedTeam={awayTeam}
                    onSelect={setAwayTeam}
                    label="Away Team"
                    tonightsGames={todaysGames}
                />
            </div>

            {/* Error Display */}
            {error && (
                <div className="error-banner">
                    ⚠️ {error}
                </div>
            )}

            {/* Matchup Edge Banner */}
            {matchupData && (
                <div className={`matchup-edge-banner edge-${matchupData.matchup_edge}`}>
                    <span className="edge-label">
                        {matchupData.matchup_edge === 'home'
                            ? `🏠 ${matchupData.home_team.team_name} Favored`
                            : matchupData.matchup_edge === 'away'
                                ? `🚗 ${matchupData.away_team.team_name} Favored`
                                : '⚖️ Even Matchup'
                        }
                    </span>
                    <span className="edge-reason">{matchupData.edge_reason}</span>
                </div>
            )}

            {/* Roster Panes */}
            {matchupData && (
                <div className="roster-panes">
                    <RosterPane
                        team={matchupData.home_team}
                        excludedPlayers={excludedPlayers}
                        onTogglePlayer={togglePlayer}
                    />
                    <RosterPane
                        team={matchupData.away_team}
                        excludedPlayers={excludedPlayers}
                        onTogglePlayer={togglePlayer}
                    />
                </div>
            )}

            {/* Heat Map Grid */}
            {matchupData && (
                <PotentialHeatMap
                    homePlayers={matchupData.home_team.players}
                    awayPlayers={matchupData.away_team.players}
                    excludedPlayers={excludedPlayers}
                />
            )}

            {/* Usage Vacuum Notice */}
            {matchupData && matchupData.usage_vacuum_applied.length > 0 && (
                <div className="vacuum-notice">
                    ⚡ Usage Vacuum Active: {matchupData.usage_vacuum_applied.length} high-usage player(s) OUT.
                    Shots redistributed to active teammates.
                </div>
            )}
        </div>
    );
};

export default MatchupWarRoom;
