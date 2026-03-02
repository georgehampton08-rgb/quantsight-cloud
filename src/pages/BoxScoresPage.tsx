/**
 * Box Scores Page
 * ================
 * Two-tab layout:
 *   "Today"   → live/upcoming games via existing useLiveStats hook (zero disruption)
 *   "History" → past dates with final scores from /api/box-scores Firestore endpoint
 *
 * Vertical scroll is enabled on the entire card list for mobile.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useLiveStats, LiveGame } from '../hooks/useLiveStats';
import { API_BASE } from '../config/apiConfig';
import './MatchupLabPage.css';

// ─── Types ────────────────────────────────────────────────────────────────────

interface HistoricalGame {
    game_id: string;
    matchup: string;
    home_team: string;
    away_team: string;
    home_score: number;
    away_score: number;
    status: string;
    winner: string;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

/** Live game card shown in Today tab */
const LiveGameCard: React.FC<{ game: LiveGame }> = ({ game }) => {
    const isLive = game.status === 'LIVE' || game.status === 'HALFTIME';
    const isFinal = game.status === 'FINAL';
    const isUpcoming = game.status === 'UPCOMING';

    const homeWon = isFinal && game.home_score > game.away_score;
    const awayWon = isFinal && game.away_score > game.home_score;

    return (
        <div className={`glass-card p-5 relative overflow-hidden transition-all duration-300 ${isLive ? 'border border-red-500/30' : ''}`}>
            {/* Live pulse bar */}
            {isLive && (
                <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-red-500 to-transparent animate-pulse" />
            )}

            {/* Status badge */}
            <div className="flex justify-between items-center mb-4">
                <span className="text-xs text-slate-500 font-mono">{game.game_id || '—'}</span>
                {isLive && (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-500/20 border border-red-500/30 text-red-400 text-xs font-bold">
                        <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
                        LIVE · Q{game.period} {game.clock}
                    </span>
                )}
                {game.status === 'HALFTIME' && (
                    <span className="px-2.5 py-1 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-bold">HALFTIME</span>
                )}
                {isFinal && (
                    <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-bold">FINAL</span>
                )}
                {isUpcoming && (
                    <span className="px-2.5 py-1 rounded-full bg-slate-700/60 border border-slate-600/40 text-slate-400 text-xs font-bold">
                        {game.clock || 'UPCOMING'}
                    </span>
                )}
            </div>

            {/* Score display */}
            <div className="flex items-center justify-between gap-4">
                {/* Away team */}
                <div className={`flex-1 text-center ${awayWon ? 'opacity-100' : isFinal ? 'opacity-50' : ''}`}>
                    <div className={`text-3xl font-bold font-mono mb-1 ${awayWon ? 'text-emerald-400' : 'text-white'}`}>
                        {isUpcoming ? '—' : game.away_score}
                    </div>
                    <div className={`text-sm font-bold tracking-wider ${awayWon ? 'text-emerald-300' : 'text-slate-300'}`}>
                        {game.away_team}
                    </div>
                    {awayWon && <div className="text-[10px] text-emerald-500 mt-1 font-bold uppercase tracking-widest">W</div>}
                </div>

                {/* Divider */}
                <div className="flex flex-col items-center gap-1">
                    <span className="text-slate-600 font-mono text-lg">@</span>
                    {isLive && (
                        <div className="text-xs text-slate-500 font-mono text-center">
                            {Math.abs(game.home_score - game.away_score) <= 5
                                ? <span className="text-amber-400 animate-pulse">CLOSE</span>
                                : `+${Math.abs(game.home_score - game.away_score)}`
                            }
                        </div>
                    )}
                </div>

                {/* Home team */}
                <div className={`flex-1 text-center ${homeWon ? 'opacity-100' : isFinal ? 'opacity-50' : ''}`}>
                    <div className={`text-3xl font-bold font-mono mb-1 ${homeWon ? 'text-emerald-400' : 'text-white'}`}>
                        {isUpcoming ? '—' : game.home_score}
                    </div>
                    <div className={`text-sm font-bold tracking-wider ${homeWon ? 'text-emerald-300' : 'text-slate-300'}`}>
                        {game.home_team}
                    </div>
                    {homeWon && <div className="text-[10px] text-emerald-500 mt-1 font-bold uppercase tracking-widest">W</div>}
                </div>
            </div>
        </div>
    );
};

/** Historical game card shown in History tab */
const HistoricalGameCard: React.FC<{ game: HistoricalGame }> = ({ game }) => {
    const homeWon = game.winner === game.home_team;
    const awayWon = game.winner === game.away_team;

    return (
        <div className="glass-card p-5 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />

            {/* Header */}
            <div className="flex justify-between items-center mb-4">
                <span className="text-xs text-slate-500 font-mono">{game.game_id}</span>
                <span className="px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
                    FINAL
                </span>
            </div>

            {/* Score */}
            <div className="flex items-center justify-between gap-4">
                {/* Away */}
                <div className={`flex-1 text-center ${awayWon ? 'opacity-100' : 'opacity-50'}`}>
                    <div className={`text-3xl font-bold font-mono mb-1 ${awayWon ? 'text-emerald-400' : 'text-white'}`}>
                        {game.away_score}
                    </div>
                    <div className={`text-sm font-bold tracking-wider ${awayWon ? 'text-emerald-300' : 'text-slate-400'}`}>
                        {game.away_team}
                    </div>
                    {awayWon && <div className="text-[10px] text-emerald-500 mt-1 font-bold uppercase tracking-widest">W</div>}
                </div>

                <div className="text-slate-600 font-mono text-lg">@</div>

                {/* Home */}
                <div className={`flex-1 text-center ${homeWon ? 'opacity-100' : 'opacity-50'}`}>
                    <div className={`text-3xl font-bold font-mono mb-1 ${homeWon ? 'text-emerald-400' : 'text-white'}`}>
                        {game.home_score}
                    </div>
                    <div className={`text-sm font-bold tracking-wider ${homeWon ? 'text-emerald-300' : 'text-slate-400'}`}>
                        {game.home_team}
                    </div>
                    {homeWon && <div className="text-[10px] text-emerald-500 mt-1 font-bold uppercase tracking-widest">W</div>}
                </div>
            </div>
        </div>
    );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

type TabId = 'today' | 'history';

const BoxScoresPage: React.FC = () => {
    // ── Tab state ──────────────────────────────────────────────────────────
    const [activeTab, setActiveTab] = useState<TabId>('today');

    // ── Live data (Today tab) ──────────────────────────────────────────────
    const {
        games: liveGames,
        isConnected,
        isConnecting,
        lastUpdate,
    } = useLiveStats();

    const sortedLiveGames = [...liveGames].sort((a, b) => {
        const order: Record<string, number> = { LIVE: 0, HALFTIME: 1, UPCOMING: 2, FINAL: 3 };
        return (order[a.status] ?? 4) - (order[b.status] ?? 4);
    });

    // ── History state ──────────────────────────────────────────────────────
    const getTodayStr = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD in local time

    const [availableDates, setAvailableDates] = useState<string[]>([]);
    const [selectedDate, setSelectedDate] = useState<string>(getTodayStr());
    const [historicalGames, setHistoricalGames] = useState<HistoricalGame[]>([]);
    const [histLoading, setHistLoading] = useState(false);
    const [histError, setHistError] = useState<string | null>(null);
    const [datesLoaded, setDatesLoaded] = useState(false);

    // Fetch available dates on mount (used for dot indicators)
    useEffect(() => {
        const fetchDates = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/box-scores/dates`);
                if (res.ok) {
                    const data = await res.json();
                    const dates: string[] = data.dates || [];
                    setAvailableDates(dates);
                    // Auto-select most recent date if it exists and is not today
                    if (dates.length > 0 && dates[0] !== getTodayStr()) {
                        setSelectedDate(dates[0]);
                    }
                }
            } catch {
                // Non-critical — dot indicators just won't show
            } finally {
                setDatesLoaded(true);
            }
        };
        fetchDates();
    }, []);

    // Fetch historical games when date changes (History tab)
    const fetchHistorical = useCallback(async (date: string) => {
        setHistLoading(true);
        setHistError(null);
        setHistoricalGames([]);
        try {
            const res = await fetch(`${API_BASE}/api/box-scores?date=${date}`);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Server error ${res.status}`);
            }
            const data = await res.json();
            setHistoricalGames(data.games || []);
        } catch (err: any) {
            setHistError(err.message || 'Failed to load box scores.');
        } finally {
            setHistLoading(false);
        }
    }, []);

    // Trigger fetch when History tab is active and date changes
    useEffect(() => {
        if (activeTab === 'history') {
            fetchHistorical(selectedDate);
        }
    }, [activeTab, selectedDate, fetchHistorical]);

    const hasData = availableDates.includes(selectedDate);

    // ── Render ─────────────────────────────────────────────────────────────
    return (
        <div className="matchup-lab-page h-full flex flex-col p-4 sm:p-6">

            {/* ── Header ───────────────────────────────────────────────── */}
            <header className="lab-header mb-5 flex-shrink-0">
                <div className="header-content">
                    <div className="header-title flex flex-wrap items-center gap-3">
                        <span className="lab-icon text-2xl">📊</span>
                        <h1 className="text-2xl sm:text-3xl">Box Scores</h1>
                        {activeTab === 'today' && (
                            <span className={`ai-badge text-xs border px-2.5 py-1 rounded-full whitespace-nowrap ${isConnected
                                    ? 'bg-green-500/20 text-green-400 border-green-500/30'
                                    : isConnecting
                                        ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                                        : 'bg-red-500/20 text-red-400 border-red-500/30'
                                }`}>
                                <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${isConnected ? 'bg-green-500' : isConnecting ? 'bg-amber-500 animate-pulse' : 'bg-red-500'
                                    }`} />
                                {isConnected ? 'LIVE FEED' : isConnecting ? 'CONNECTING…' : 'DISCONNECTED'}
                            </span>
                        )}
                        {activeTab === 'today' && lastUpdate && (
                            <span className="text-xs text-slate-500 ml-auto hidden sm:block">
                                Updated {new Date(lastUpdate).toLocaleTimeString()}
                            </span>
                        )}
                    </div>
                </div>
            </header>

            {/* ── Tabs ─────────────────────────────────────────────────── */}
            <div className="flex gap-1 mb-5 flex-shrink-0 bg-slate-800/60 rounded-xl p-1 max-w-xs">
                {([['today', '📡 Today'], ['history', '🗂️ History']] as [TabId, string][]).map(([id, label]) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`flex-1 py-2 px-3 rounded-lg text-sm font-semibold transition-all duration-200 ${activeTab === id
                                ? 'bg-financial-accent/20 text-financial-accent shadow'
                                : 'text-slate-400 hover:text-slate-200'
                            }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* ── History: Date picker row ──────────────────────────────── */}
            {activeTab === 'history' && (
                <div className="flex flex-wrap items-center gap-3 mb-5 flex-shrink-0">
                    <div className="relative">
                        <input
                            id="box-scores-date-picker"
                            type="date"
                            value={selectedDate}
                            max={getTodayStr()}
                            onChange={e => setSelectedDate(e.target.value)}
                            className="bg-slate-800/80 border border-slate-700/60 text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-financial-accent/60 cursor-pointer"
                        />
                    </div>

                    {/* Dot indicator */}
                    {datesLoaded && (
                        <span className={`flex items-center gap-1.5 text-xs ${hasData ? 'text-emerald-400' : 'text-slate-500'}`}>
                            <span className={`w-2 h-2 rounded-full ${hasData ? 'bg-emerald-500' : 'bg-slate-600'}`} />
                            {hasData ? 'Game data saved' : 'No saved data'}
                        </span>
                    )}

                    {/* Quick-jump buttons for recent available dates */}
                    {availableDates.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap">
                            {availableDates.slice(0, 5).map(d => (
                                <button
                                    key={d}
                                    onClick={() => setSelectedDate(d)}
                                    className={`text-xs px-2.5 py-1 rounded-lg border transition-all duration-150 ${selectedDate === d
                                            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                                            : 'bg-slate-800/60 border-slate-700/50 text-slate-400 hover:text-slate-200 hover:border-slate-500'
                                        }`}
                                >
                                    {d.slice(5)} {/* MM-DD */}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* ── Scrollable content area ───────────────────────────────── */}
            <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent pb-6">

                {/* ── TODAY TAB ─────────────────────────────────────────── */}
                {activeTab === 'today' && (
                    <>
                        {sortedLiveGames.length > 0 ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                {sortedLiveGames.map(game => (
                                    <LiveGameCard key={game.game_id} game={game} />
                                ))}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-64 text-center gap-4">
                                <div className="text-5xl">🏀</div>
                                <div className="text-slate-400 text-lg font-medium">
                                    {isConnecting ? 'Connecting to live feed…' : 'No games scheduled today'}
                                </div>
                                {!isConnecting && (
                                    <p className="text-slate-500 text-sm max-w-sm">
                                        Check the History tab to browse past game results.
                                    </p>
                                )}
                            </div>
                        )}
                    </>
                )}

                {/* ── HISTORY TAB ───────────────────────────────────────── */}
                {activeTab === 'history' && (
                    <>
                        {histLoading && (
                            <div className="flex items-center justify-center h-48 gap-3 text-slate-400">
                                <span className="w-5 h-5 border-2 border-financial-accent/40 border-t-financial-accent rounded-full animate-spin" />
                                Loading box scores…
                            </div>
                        )}

                        {histError && !histLoading && (
                            <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm max-w-lg">
                                <span className="text-lg flex-shrink-0">⚠️</span>
                                <div>
                                    <div className="font-semibold mb-1">Failed to load box scores</div>
                                    <div className="text-red-400/70">{histError}</div>
                                </div>
                            </div>
                        )}

                        {!histLoading && !histError && historicalGames.length > 0 && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                {historicalGames.map(game => (
                                    <HistoricalGameCard key={game.game_id} game={game} />
                                ))}
                            </div>
                        )}

                        {!histLoading && !histError && historicalGames.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-64 text-center gap-4">
                                <div className="text-5xl">📭</div>
                                <div className="text-slate-400 text-lg font-medium">
                                    No game records for {selectedDate}
                                </div>
                                <p className="text-slate-500 text-sm max-w-sm">
                                    {availableDates.length > 0
                                        ? <>
                                            Try one of the available dates: <span className="text-emerald-400">{availableDates[0]}</span> is the most recent.
                                        </>
                                        : 'This may be an NBA off day, or game data has not been saved yet.'
                                    }
                                </p>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default BoxScoresPage;
