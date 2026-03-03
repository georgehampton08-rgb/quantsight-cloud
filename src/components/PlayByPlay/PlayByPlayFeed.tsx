import React, { useState, useEffect, useRef } from 'react';
import { useLivePlayByPlay } from '../../hooks/useLivePlayByPlay';
import { PlayItem } from './PlayItem';
import { InteractiveShotChart } from './InteractiveShotChart';
import { GameScoreHeader } from './GameScoreHeader';
import { ConnectionStatus } from './ConnectionStatus';
import { LiveGameSelector } from './LiveGameSelector';
import './PlayByPlay.css';

export function PlayByPlayFeed() {
    const [activeGameId, setActiveGameId] = useState<string | null>(null);
    const { plays, isConnected, isReconnecting, error } = useLivePlayByPlay(activeGameId);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to latest play
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [plays]);

    // Derive latest score and clock from last play
    let homeScore = 0;
    let awayScore = 0;
    let clock = '12:00';
    let period = 1;
    let homeTeam = 'HOME';
    let awayTeam = 'AWAY';

    if (plays.length > 0) {
        const last = plays[plays.length - 1];
        homeScore = last.homeScore;
        awayScore = last.awayScore;
        clock = last.clock;
        period = last.period;
    }

    return (
        <div className="pbp-container">
            {/* Header: title + connection pill */}
            <div className="pbp-header-row">
                <h2>Live Play-by-Play</h2>
                <ConnectionStatus isConnected={isConnected} isReconnecting={isReconnecting} error={error} />
            </div>

            {/* Horizontally scrolling game selector */}
            <LiveGameSelector activeGameId={activeGameId} onSelectGame={setActiveGameId} />

            {activeGameId ? (
                <div className="pbp-feed-layout">
                    {/* Left/Top Column: Score + Court + Legend */}
                    <div className="chart-col">
                        <GameScoreHeader
                            homeScore={homeScore}
                            awayScore={awayScore}
                            homeTeam={homeTeam}
                            awayTeam={awayTeam}
                            clock={clock}
                            period={period}
                            status={isConnected ? 'live' : 'offline'}
                        />

                        <div style={{ fontSize: '15px', fontWeight: '700', color: '#f1f5f9', letterSpacing: '0.3px' }}>
                            Action Map
                        </div>

                        <InteractiveShotChart plays={plays} />

                        {/* Shot type legend */}
                        <div className="chart-legend">
                            <div className="chart-legend-item">
                                <span className="legend-dot made" />Made
                            </div>
                            <div className="chart-legend-item">
                                <span className="legend-dot missed" />Missed
                            </div>
                            <div className="chart-legend-item">
                                <span className="legend-dot three" />3-Pointer
                            </div>
                            <div className="chart-legend-item">
                                <span className="legend-dot foul" />Foul Play
                            </div>
                        </div>

                        <div style={{ fontSize: '11px', color: '#64748b', lineHeight: '1.5' }}>
                            Hover or tap a dot for player telemetry.
                        </div>
                    </div>

                    {/* Right/Bottom Column: Scrollable play feed */}
                    <div className="feed-col">
                        <div className="plays-list-container" ref={scrollRef}>
                            {plays.length === 0 ? (
                                <div className="awaiting-pulse">
                                    Awaiting pulse data...
                                </div>
                            ) : (
                                plays.map(p => <PlayItem key={`${p.playId}-${p.sequenceNumber}`} play={p} />)
                            )}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="pbp-empty-state">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 8v4l3 3" />
                    </svg>
                    <p>Select a game above to stream<br />the live Play-by-Play dashboard.</p>
                </div>
            )}
        </div>
    );
}
