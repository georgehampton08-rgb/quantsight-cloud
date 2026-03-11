import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useLivePlayByPlay } from '../../hooks/useLivePlayByPlay';
import { PlayItem } from './PlayItem';
import { InteractiveShotChart } from './InteractiveShotChart';
import { GameScoreHeader } from './GameScoreHeader';
import { ConnectionStatus } from './ConnectionStatus';
import { LiveGameSelector } from './LiveGameSelector';
import { ApiContract } from '../../api/client';
import './PlayByPlay.css';

// Today in local YYYY-MM-DD
function todayLocal(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const MIN_DATE = '2025-10-01'; // NBA season start

export function PlayByPlayFeed() {
    const today = useMemo(() => todayLocal(), []);
    const [selectedDate, setSelectedDate] = useState<string>(today);
    const [activeGameId, setActiveGameId] = useState<string | null>(null);

    // Historical: cached plays only (no SSE)
    const [historicalPlays, setHistoricalPlays] = useState<any[]>([]);
    const [historicalLoading, setHistoricalLoading] = useState(false);

    // Live mode when date is today
    const isLiveMode = selectedDate === today;

    // Selected historical game metadata (for score header even when plays are empty)
    const [selectedGameMeta, setSelectedGameMeta] = useState<{
        homeTeam: string; awayTeam: string;
        scoreHome?: number; scoreAway?: number;
    } | null>(null);

    // Live mode: use the real-time hook
    const { plays: livePlays, isConnected, isReconnecting, error } = useLivePlayByPlay(
        isLiveMode ? activeGameId : null
    );

    const plays = isLiveMode ? livePlays : historicalPlays;
    const scrollRef = useRef<HTMLDivElement>(null);

    // Reset selected game when date changes
    useEffect(() => {
        setActiveGameId(null);
        setHistoricalPlays([]);
        setSelectedGameMeta(null);
    }, [selectedDate]);

    // Historical: load cached plays when a past game is selected
    useEffect(() => {
        if (isLiveMode || !activeGameId) return;
        setHistoricalLoading(true);
        setHistoricalPlays([]);
        ApiContract.executeWeb<{ plays: any[] }>({
            path: `v1/games/${activeGameId}/plays?limit=2000`
        }).then(res => {
            setHistoricalPlays(res?.plays ?? []);
        }).catch(err => {
            console.error('Failed to load historical plays:', err);
        }).finally(() => setHistoricalLoading(false));
    }, [activeGameId, isLiveMode]);

    // Auto-scroll to latest play in live mode
    useEffect(() => {
        if (!isLiveMode) return;
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [livePlays, isLiveMode]);

    // Score + clock derived from last play (or historical metadata)
    let homeScore = selectedGameMeta?.scoreHome ?? 0;
    let awayScore = selectedGameMeta?.scoreAway ?? 0;
    let clock = '12:00', period = 1;
    let homeTeam = selectedGameMeta?.homeTeam ?? 'HOME';
    let awayTeam = selectedGameMeta?.awayTeam ?? 'AWAY';
    if (plays.length > 0) {
        const last = plays[plays.length - 1];
        homeScore = last.homeScore ?? homeScore;
        awayScore = last.awayScore ?? awayScore;
        clock = last.clock;
        period = last.period;
    }

    return (
        <div className="pbp-container">
            {/* Header row */}
            <div className="pbp-header-row">
                <h2>{isLiveMode ? 'Live Play-by-Play' : `Play-by-Play — ${selectedDate}`}</h2>
                {isLiveMode
                    ? <ConnectionStatus isConnected={isConnected} isReconnecting={isReconnecting} error={error} />
                    : <span className="pbp-mode-badge historical">HISTORICAL</span>
                }
            </div>

            {/* Date selector row */}
            <div className="pbp-date-row">
                <button
                    id="pbp-date-prev"
                    className="pbp-date-nav-btn"
                    onClick={() => {
                        const d = new Date(selectedDate);
                        d.setDate(d.getDate() - 1);
                        const iso = d.toISOString().split('T')[0];
                        if (iso >= MIN_DATE) setSelectedDate(iso);
                    }}
                    title="Previous day"
                >
                    ‹
                </button>

                <input
                    id="pbp-date-input"
                    type="date"
                    className="pbp-date-input"
                    value={selectedDate}
                    min={MIN_DATE}
                    max={today}
                    onChange={e => setSelectedDate(e.target.value)}
                />

                <button
                    id="pbp-date-next"
                    className="pbp-date-nav-btn"
                    disabled={selectedDate >= today}
                    onClick={() => {
                        const d = new Date(selectedDate);
                        d.setDate(d.getDate() + 1);
                        const iso = d.toISOString().split('T')[0];
                        if (iso <= today) setSelectedDate(iso);
                    }}
                    title="Next day"
                >
                    ›
                </button>

                {selectedDate !== today && (
                    <button
                        id="pbp-date-today"
                        className="pbp-date-today-btn"
                        onClick={() => setSelectedDate(today)}
                    >
                        Today
                    </button>
                )}
            </div>

            {/* Game selector — passes date so it fetches the right games */}
            <LiveGameSelector
                activeGameId={activeGameId}
                onSelectGame={setActiveGameId}
                onSelectGameFull={(g) => setSelectedGameMeta({
                    homeTeam: g.homeTeam,
                    awayTeam: g.awayTeam,
                    scoreHome: g.scoreHome,
                    scoreAway: g.scoreAway,
                })}
                date={selectedDate}
                isLiveMode={isLiveMode}
            />

            {activeGameId ? (
                <div className="pbp-feed-layout">
                    {/* Left: Score + Court + Legend */}
                    <div className="chart-col">
                        <GameScoreHeader
                            homeScore={homeScore}
                            awayScore={awayScore}
                            homeTeam={homeTeam}
                            awayTeam={awayTeam}
                            clock={clock}
                            period={period}
                            status={isLiveMode && isConnected ? 'live' : 'offline'}
                        />

                        <div style={{ fontSize: '15px', fontWeight: '700', color: '#f1f5f9', letterSpacing: '0.3px' }}>
                            Action Map
                        </div>

                        <InteractiveShotChart plays={plays} />

                        <div className="chart-legend">
                            <div className="chart-legend-item"><span className="legend-dot made" />Made</div>
                            <div className="chart-legend-item"><span className="legend-dot missed" />Missed</div>
                            <div className="chart-legend-item"><span className="legend-dot three-made" />3PT Made</div>
                            <div className="chart-legend-item"><span className="legend-dot three-missed" />3PT Missed</div>
                            <div className="chart-legend-item"><span className="legend-dot foul" />Foul</div>
                        </div>

                        <div style={{ fontSize: '11px', color: '#64748b', lineHeight: '1.5' }}>
                            Hover or tap a dot for player telemetry.
                        </div>
                    </div>

                    {/* Right: Play feed */}
                    <div className="feed-col">
                        <div className="plays-list-container" ref={scrollRef}>
                            {historicalLoading ? (
                                <div className="awaiting-pulse">Loading historical plays...</div>
                            ) : plays.length === 0 ? (
                                <div className="awaiting-pulse">
                                    {isLiveMode ? 'Awaiting pulse data...' : 'No play data for this game.'}
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
                    <p>
                        {isLiveMode
                            ? <>Select a game above to stream<br />the live Play-by-Play dashboard.</>
                            : <>Select a game above to view<br />Play-by-Play from {selectedDate}.</>}
                    </p>
                </div>
            )}
        </div>
    );
}


