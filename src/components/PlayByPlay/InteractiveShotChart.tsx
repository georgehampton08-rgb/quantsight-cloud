import React, { useState } from 'react';
import { PlayEvent } from '../../hooks/useLivePlayByPlay';
import './PlayByPlay.css';

interface Props {
    plays: PlayEvent[];
}

export function InteractiveShotChart({ plays }: Props) {
    const [hoveredPlay, setHoveredPlay] = useState<PlayEvent | null>(null);

    const shootingPlays = plays.filter(
        (p) => p.isShootingPlay && p.coordinateX !== null && p.coordinateY !== null && p.coordinateX !== undefined
    );

    return (
        <div className="chart-container">
            <svg className="svg-court" viewBox="0 0 940 500" xmlns="http://www.w3.org/2000/svg">
                <rect x="0" y="0" width="940" height="500" fill="rgba(0,0,0,0.15)" />
                <line x1="470" y1="0" x2="470" y2="500" />
                <circle cx="470" cy="250" r="60" />

                <rect x="0" y="170" width="190" height="160" fill="rgba(0,0,0,0.1)" />
                <rect x="0" y="190" width="190" height="120" />
                <path d="M 190 190 A 60 60 0 0 1 190 310" fill="none" />
                <path d="M 190 190 A 60 60 0 0 0 190 310" style={{ strokeDasharray: "4 4" }} />
                <line x1="0" y1="30" x2="140" y2="30" />
                <line x1="0" y1="470" x2="140" y2="470" />
                <path d="M 140 30 A 237.5 237.5 0 0 1 140 470" />
                <line x1="40" y1="220" x2="40" y2="280" stroke="#fff" strokeWidth="4" />
                <circle cx="52.5" cy="250" r="7.5" stroke="#f97316" strokeWidth="3" />

                <rect x="750" y="170" width="190" height="160" fill="rgba(0,0,0,0.1)" />
                <rect x="750" y="190" width="190" height="120" />
                <path d="M 750 190 A 60 60 0 0 0 750 310" fill="none" />
                <path d="M 750 190 A 60 60 0 0 1 750 310" style={{ strokeDasharray: "4 4" }} />
                <line x1="940" y1="30" x2="800" y2="30" />
                <line x1="940" y1="470" x2="800" y2="470" />
                <path d="M 800 30 A 237.5 237.5 0 0 0 800 470" />
                <line x1="900" y1="220" x2="900" y2="280" stroke="#fff" strokeWidth="4" />
                <circle cx="887.5" cy="250" r="7.5" stroke="#f97316" strokeWidth="3" />

                {shootingPlays.map((p) => {
                    const rawY = p.coordinateY || 0;
                    const rawX = p.coordinateX || 0;

                    let cx = Math.max(10, Math.min(930, rawY * 10));
                    let cy = Math.max(10, Math.min(490, rawX * 10));

                    let is3Pt = false;
                    let isFoul = false;

                    if (p.description) {
                        const desc = p.description.toLowerCase();
                        if (desc.includes('3-pt') || desc.includes('3pt') || desc.includes('3 point')) is3Pt = true;
                        if (desc.includes('foul')) isFoul = true;
                    }

                    const isMade = !!(p.isScoringPlay || p.shotResult === 'Made');
                    let baseClass = isMade ? 'made' : 'missed';
                    if (is3Pt) baseClass += '-3pt';
                    if (!isMade && isFoul) baseClass = 'foul';

                    return (
                        <circle
                            key={`${p.playId}-${p.sequenceNumber || 0}`}
                            className={`shot-point ${baseClass}`}
                            cx={cx}
                            cy={cy}
                            r={isMade ? 6 : 5}
                            fillOpacity={isMade ? 1 : 0.6}
                            onMouseEnter={() => setHoveredPlay(p)}
                            onMouseLeave={() => setHoveredPlay(null)}
                            onClick={() => setHoveredPlay(p)}
                        />
                    );
                })}
            </svg>

            {hoveredPlay && (
                <div className="tooltip-card">
                    <div className="headshot-group">
                        {hoveredPlay.primaryPlayerId && (
                            <img
                                className="headshot primary"
                                src={`https://cdn.nba.com/headshots/nba/latest/1040x760/${hoveredPlay.primaryPlayerId}.png`}
                                alt={hoveredPlay.primaryPlayerName || 'Player'}
                                onError={(e) => {
                                    (e.target as HTMLImageElement).src = 'https://www.nba.com/stats/media/img/no-headshot.png';
                                }}
                            />
                        )}
                        {hoveredPlay.secondaryPlayerId && (
                            <img
                                className="headshot secondary"
                                src={`https://cdn.nba.com/headshots/nba/latest/1040x760/${hoveredPlay.secondaryPlayerId}.png`}
                                alt={hoveredPlay.secondaryPlayerName || 'Secondary Player'}
                                onError={(e) => {
                                    (e.target as HTMLImageElement).src = 'https://www.nba.com/stats/media/img/no-headshot.png';
                                }}
                            />
                        )}
                    </div>

                    <div className="player-name">
                        {hoveredPlay.primaryPlayerName || 'Unknown Player'}
                        {hoveredPlay.teamTricode && <span style={{ color: '#94a3b8', fontSize: '10px', marginLeft: '6px' }}>{hoveredPlay.teamTricode}</span>}
                    </div>
                    {hoveredPlay.secondaryPlayerName && (
                        <div className="secondary-name">w/ {hoveredPlay.secondaryPlayerName}</div>
                    )}
                    <div className="desc">{hoveredPlay.description}</div>
                    <div className="meta">
                        <span>Period {hoveredPlay.period} • {hoveredPlay.clock}</span>
                        <span>
                            {hoveredPlay.shotArea ? `${hoveredPlay.shotArea} • ` : ''}
                            {hoveredPlay.shotDistance ? `${hoveredPlay.shotDistance} ft` : ''}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
