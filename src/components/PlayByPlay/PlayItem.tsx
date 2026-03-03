import React from 'react';
import { PlayEvent } from '../../hooks/useLivePlayByPlay';
import './PlayByPlay.css';

interface Props {
    play: PlayEvent;
}

export function PlayItem({ play }: Props) {
    let type = 'Neutral';
    if (play.shotResult === 'Made' || play.isScoringPlay) type = 'Made';
    else if (play.shotResult === 'Missed') type = 'Missed';
    else if (play.eventType.toLowerCase().includes('foul')) type = 'Foul';
    else if (play.eventType.toLowerCase().includes('turnover')) type = 'Turnover';

    const descRaw = play.description || play.eventType;
    let descStyled = play.primaryPlayerName
        ? descRaw.replace(play.primaryPlayerName, `<span class="player-name primary">${play.primaryPlayerName}</span>`)
        : descRaw;

    if (play.secondaryPlayerName) {
        descStyled = descStyled.replace(play.secondaryPlayerName, `<span class="player-name secondary">${play.secondaryPlayerName}</span>`);
    }

    const hasSecondaryPlayer = !!play.secondaryPlayerId;

    return (
        <div className={`play-item type-${type}`}>
            <div className="play-time">
                <div className="clock">{play.clock}</div>
                <div className="period">Q{play.period}</div>
            </div>

            <div className={`play-avatar ${hasSecondaryPlayer ? 'has-secondary' : ''}`}>
                <div className="avatar-group">
                    {play.primaryPlayerId ? (
                        <img
                            className="primary-img"
                            src={`https://cdn.nba.com/headshots/nba/latest/260x190/${play.primaryPlayerId}.png`}
                            alt="Player"
                            onError={(e) => {
                                (e.target as HTMLImageElement).src = 'https://www.nba.com/stats/media/img/no-headshot.png';
                            }}
                        />
                    ) : (
                        <div className="placeholder primary-img" />
                    )}

                    {hasSecondaryPlayer && (
                        <img
                            className="secondary-img"
                            src={`https://cdn.nba.com/headshots/nba/latest/260x190/${play.secondaryPlayerId}.png`}
                            alt="Secondary Player"
                            onError={(e) => {
                                (e.target as HTMLImageElement).src = 'https://www.nba.com/stats/media/img/no-headshot.png';
                            }}
                        />
                    )}
                </div>
            </div>

            <div className="play-content">
                <div className="desc" dangerouslySetInnerHTML={{ __html: descStyled }} />
                <div className="play-badges">
                    {play.teamTricode && (
                        <span className="badge type-team">
                            {play.teamTricode}
                        </span>
                    )}
                    {play.pointsValue > 0 && (
                        <span className={`badge ${play.pointsValue === 3 ? 'type-3pt' : ''}`}>
                            +{play.pointsValue} PTS
                        </span>
                    )}
                    {play.shotDistance !== null && play.shotDistance !== undefined && (
                        <span className="badge">🎯 {play.shotDistance} ft</span>
                    )}
                    {type === 'Foul' && <span className="badge type-foul">⚡ FOUL</span>}
                    {play.shotResult === 'Made' && play.secondaryPlayerId && (
                        <span className="badge type-assist">AST</span>
                    )}
                </div>
            </div>

            <div className="play-score">
                {play.awayScore} - {play.homeScore}
            </div>
        </div>
    );
}
