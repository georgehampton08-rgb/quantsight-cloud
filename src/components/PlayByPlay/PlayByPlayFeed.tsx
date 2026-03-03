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

    // Derive latest score and clock for header
    let homeScore = 0;
    let awayScore = 0;
    let clock = '12:00';
    let period = 1;
    let homeTeam = 'HOME';
    let awayTeam = 'AWAY';

    if (plays.length > 0) {
        const last = plays[plays.length - 1]; // Already sorted by sequence number
        homeScore = last.homeScore;
        awayScore = last.awayScore;
        clock = last.clock;
        period = last.period;

        // Find team names (ESPN gives text "Dallas Mavericks", CDN gives Tricode "DAL")
        // This is rough fallback logic, ideally we pull this from the LiveGame list or a /teams resource.
        const hd = plays.find(p => p.homeScore > 0 || p.teamTricode);
        if (hd?.teamTricode) {
            // Quick extraction
            homeTeam = "HOME"; // Requires mapping if not using CDN
            awayTeam = "AWAY";
        }
    }

    return (
        <div className="pbp-container">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ margin: 0, color: '#f8fafc', fontSize: '24px' }}>Live Play-by-Play</h2>
                <ConnectionStatus isConnected={isConnected} isReconnecting={isReconnecting} error={error} />
            </div>

            <LiveGameSelector activeGameId={activeGameId} onSelectGame={setActiveGameId} />

            {activeGameId ? (
                <div className="pbp-feed-layout">
                    {/* Left/Top Column: Court Visualizer */}
                    <div className="chart-col">
                        <GameScoreHeader
                            homeScore={homeScore}
                            awayScore={awayScore}
                            homeTeam={homeTeam}
                            awayTeam={awayTeam}
                            clock={clock}
                            period={period}
                            status={isConnected ? "live" : "offline"}
                        />

                        <div style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 'bold', color: '#f1f5f9' }}>
                            Action Map
                        </div>
                        <InteractiveShotChart plays={plays} />
                        <div style={{ marginTop: '16px', fontSize: '12px', color: '#94a3b8', lineHeight: '1.5' }}>
                            <strong>Real-Time Graphing:</strong> Shots are plotted as soon as the sequence reaches the frontend. Hover over points for player telemetry.
                        </div>
                    </div>

                    {/* Right/Bottom Column: Plays Stream */}
                    <div className="feed-col">
                        <div className="plays-list-container" ref={scrollRef}>
                            {plays.length === 0 ? (
                                <div style={{ padding: '20px', color: '#64748b', textAlign: 'center' }}>
                                    Awaiting pulse data...
                                </div>
                            ) : (
                                plays.map(p => <PlayItem key={`${p.playId}-${p.sequenceNumber}`} play={p} />)
                            )}
                        </div>
                    </div>
                </div>
            ) : (
                <div style={{
                    padding: '40px', background: '#1e293b', borderRadius: '12px',
                    color: '#cbd5e1', textAlign: 'center', border: '1px dashed #475569'
                }}>
                    Please select a live game from the selector above to stream the Play-by-Play dashboard.
                </div>
            )}
        </div>
    );
}
