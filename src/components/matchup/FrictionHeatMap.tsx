import React from 'react';
import './FrictionHeatMap.css';

interface MatchupData {
    player_id: string;
    player_name: string;
    position: string;
    opponent_id: string;
    opponent_name: string;
    matchup_grade: 'A+' | 'A' | 'B' | 'C' | 'D' | 'F';
    friction_pct: number;  // -12% to +12%
    is_frost: boolean;  // True if disadvantageous matchup
    radar_stats: {
        scoring: number;
        defense: number;
        playmaking: number;
        athleticism: number;
        shooting: number;
    };
}

interface FrictionHeatMapProps {
    matchups: MatchupData[];
    showFrostOverlay?: boolean;
}

const gradeColors: Record<string, string> = {
    'A+': '#22c55e',
    'A': '#4ade80',
    'B': '#a3e635',
    'C': '#fbbf24',
    'D': '#fb923c',
    'F': '#ef4444',
};

const FrictionHeatMap: React.FC<FrictionHeatMapProps> = ({
    matchups,
    showFrostOverlay = true
}) => {
    const renderRadarChart = (stats: MatchupData['radar_stats'], isFrost: boolean) => {
        const categories = Object.keys(stats) as (keyof typeof stats)[];
        const numCategories = categories.length;
        const angleSlice = (Math.PI * 2) / numCategories;
        const radius = 40;
        const centerX = 50;
        const centerY = 50;

        // Create path for radar shape
        const points = categories.map((cat, i) => {
            const value = stats[cat] / 100;
            const angle = angleSlice * i - Math.PI / 2;
            return {
                x: centerX + Math.cos(angle) * radius * value,
                y: centerY + Math.sin(angle) * radius * value,
            };
        });

        const pathD = points.map((p, i) =>
            `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
        ).join(' ') + ' Z';

        return (
            <svg viewBox="0 0 100 100" className="radar-chart">
                {/* Grid circles */}
                {[0.25, 0.5, 0.75, 1].map(scale => (
                    <circle
                        key={scale}
                        cx={centerX}
                        cy={centerY}
                        r={radius * scale}
                        className="radar-grid"
                    />
                ))}

                {/* Axis lines */}
                {categories.map((_, i) => {
                    const angle = angleSlice * i - Math.PI / 2;
                    return (
                        <line
                            key={i}
                            x1={centerX}
                            y1={centerY}
                            x2={centerX + Math.cos(angle) * radius}
                            y2={centerY + Math.sin(angle) * radius}
                            className="radar-axis"
                        />
                    );
                })}

                {/* Data polygon */}
                <path d={pathD} className={`radar-data ${isFrost ? 'frost' : ''}`} />

                {/* Data points */}
                {points.map((p, i) => (
                    <circle
                        key={i}
                        cx={p.x}
                        cy={p.y}
                        r={3}
                        className="radar-point"
                    />
                ))}

                {/* Labels */}
                {categories.map((cat, i) => {
                    const angle = angleSlice * i - Math.PI / 2;
                    const labelRadius = radius + 12;
                    return (
                        <text
                            key={cat}
                            x={centerX + Math.cos(angle) * labelRadius}
                            y={centerY + Math.sin(angle) * labelRadius}
                            className="radar-label"
                            textAnchor="middle"
                            dominantBaseline="middle"
                        >
                            {String(cat || '').slice(0, 3).toUpperCase()}
                        </text>
                    );
                })}
            </svg>
        );
    };

    return (
        <div className="friction-heatmap">
            <div className="heatmap-header">
                <h3>🌡️ Matchup Friction Map</h3>
                <div className="legend">
                    <span className="legend-item advantage">🔥 Advantage</span>
                    <span className="legend-item neutral">➖ Neutral</span>
                    <span className="legend-item frost">❄️ Frost</span>
                </div>
            </div>

            <div className="matchup-grid">
                {matchups.map(matchup => (
                    <div
                        key={matchup.player_id}
                        className={`matchup-card ${matchup.is_frost ? 'frost-overlay' : ''}`}
                    >
                        {matchup.is_frost && showFrostOverlay && (
                            <div className="frost-indicator">
                                <span className="frost-icon">❄️</span>
                                <span className="frost-label">{matchup.friction_pct}%</span>
                            </div>
                        )}

                        <div className="matchup-header">
                            <span className="player-name">{matchup.player_name}</span>
                            <span
                                className="matchup-grade"
                                style={{ color: gradeColors[matchup.matchup_grade] }}
                            >
                                {matchup.matchup_grade}
                            </span>
                        </div>

                        <div className="matchup-vs">
                            vs <span className="opponent">{matchup.opponent_name}</span>
                        </div>

                        <div className="radar-container">
                            {renderRadarChart(matchup.radar_stats, matchup.is_frost)}
                        </div>

                        <div className={`friction-badge ${matchup.friction_pct > 0 ? 'boost' : 'suppressed'}`}>
                            {matchup.friction_pct > 0 ? '+' : ''}{matchup.friction_pct}% Impact
                        </div>

                        {/* Traffic Light Indicator */}
                        <div className="traffic-light">
                            <span className={`light ${matchup.matchup_grade.startsWith('A') ? 'active green' : ''}`} />
                            <span className={`light ${matchup.matchup_grade === 'B' || matchup.matchup_grade === 'C' ? 'active yellow' : ''}`} />
                            <span className={`light ${matchup.matchup_grade === 'D' || matchup.matchup_grade === 'F' ? 'active red' : ''}`} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default FrictionHeatMap;
