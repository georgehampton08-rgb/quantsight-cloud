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
import { useSearchParams } from 'react-router-dom';
import { useLiveStats, LiveGame } from '../hooks/useLiveStats';
import { API_BASE } from '../config/apiConfig';
import CornerBrackets from '../components/common/CornerBrackets';

// Only accept YYYY-MM-DD strings — guards against game IDs returned by the API
// when the backend Firestore parent docs don't exist as explicit documents.
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

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
const LiveGameCard: React.FC<{ game: LiveGame; index: number }> = ({ game, index }) => {
    const isLive = game.status === 'LIVE' || game.status === 'HALFTIME';
    const isFinal = game.status === 'FINAL';
    const isUpcoming = game.status === 'UPCOMING';

    const homeWon = isFinal && game.home_score > game.away_score;
    const awayWon = isFinal && game.away_score > game.home_score;
    const isClose = isLive && Math.abs(game.home_score - game.away_score) <= 5;

    return (
        <div className={`relative bg-cyber-surface overflow-hidden opacity-0 animate-[stagger-reveal_0.2s_cubic-bezier(0.2,0,0,1)_forwards]`}
             style={{
               border: `1px solid ${isLive ? 'rgba(0,255,136,0.4)' : '#1a2332'}`,
               clipPath: 'polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))',
               animationDelay: `${index * 50}ms`
             }}>
            {/* Live scan-line */}
            {isLive && (
                <div className="absolute inset-x-0 w-full h-px bg-cyber-green opacity-20 animate-[scan-line_4s_linear_infinite]" />
            )}

            {/* Status badge */}
            <div className="flex justify-between items-center px-4 py-3 border-b border-cyber-border/50">
                <span className="text-[10px] text-cyber-muted font-mono tracking-[0.2em] uppercase">{game.game_id || '—'}</span>
                {isLive && (
                    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-cyber-green/5 border border-cyber-green text-cyber-green text-[10px] font-display font-600 tracking-[0.2em] uppercase">
                        <span className="w-1.5 h-1.5 bg-cyber-green shadow-[0_0_10px_rgba(0,255,136,0.8)] animate-[signal-pulse_2s_ease-in-out_infinite]" />
                        LIVE · Q{game.period} {game.clock}
                    </span>
                )}
                {game.status === 'HALFTIME' && (
                    <span className="px-2.5 py-1 bg-cyber-gold/5 border border-cyber-gold text-cyber-gold text-[10px] font-display font-600 tracking-[0.2em] uppercase">HALFTIME</span>
                )}
                {isFinal && (
                    <span className="px-2.5 py-1 bg-cyber-border border top-0 border-transparent text-cyber-muted text-[10px] font-display font-600 tracking-[0.2em] uppercase">FINAL</span>
                )}
                {isUpcoming && (
                    <span className="px-2.5 py-1 border border-cyber-border text-cyber-muted text-[10px] font-display font-600 tracking-[0.2em] uppercase">
                        {game.clock || 'UPCOMING'}
                    </span>
                )}
            </div>

            {/* Score display */}
            <div className="flex items-center justify-between gap-4 p-5">
                {/* Away team */}
                <div className={`flex-1 text-center ${awayWon ? 'opacity-100' : isFinal ? 'opacity-50' : ''}`}>
                    <div className={`text-4xl font-bold font-mono tabular-nums mb-1 ${awayWon ? 'text-cyber-green' : 'text-cyber-text'}`}>
                        {isUpcoming ? '—' : game.away_score}
                    </div>
                    <div className={`text-xl font-display font-700 tracking-[0.08em] uppercase ${awayWon ? 'text-cyber-green' : 'text-slate-300'}`}>
                        {game.away_team}
                    </div>
                    {awayWon && <div className="text-[10px] text-cyber-green mt-1 font-bold font-display uppercase tracking-widest">W</div>}
                </div>

                {/* Score Diff / VS */}
                <div className="flex flex-col items-center justify-center min-w-[3rem]">
                    <span className="text-cyber-muted font-mono text-xs mb-1">VS</span>
                    {isLive && (
                        <div className={`font-mono text-[10px] tracking-widest tabular-nums text-center border px-2 py-0.5 ${isClose ? 'text-cyber-gold border-cyber-gold animate-[data-flicker_3s_ease-in-out_infinite]' : 'text-cyber-text border-cyber-border'}`}>
                            {isClose ? 'CLOSE' : `+${Math.abs(game.home_score - game.away_score)}`}
                        </div>
                    )}
                </div>

                {/* Home team */}
                <div className={`flex-1 text-center ${homeWon ? 'opacity-100' : isFinal ? 'opacity-50' : ''}`}>
                    <div className={`text-4xl font-bold font-mono tabular-nums mb-1 ${homeWon ? 'text-cyber-green' : 'text-cyber-text'}`}>
                        {isUpcoming ? '—' : game.home_score}
                    </div>
                    <div className={`text-xl font-display font-700 tracking-[0.08em] uppercase ${homeWon ? 'text-cyber-green' : 'text-slate-300'}`}>
                        {game.home_team}
                    </div>
                    {homeWon && <div className="text-[10px] text-cyber-green mt-1 font-bold font-display uppercase tracking-widest">W</div>}
                </div>
            </div>
        </div>
    );
};

/** Historical game card shown in History tab */
const HistoricalGameCard: React.FC<{ game: HistoricalGame; index: number }> = ({ game, index }) => {
    const homeWon = game.winner === game.home_team;
    const awayWon = game.winner === game.away_team;

    return (
        <div className="relative bg-cyber-surface opacity-0 animate-[stagger-reveal_0.2s_cubic-bezier(0.2,0,0,1)_forwards]"
             style={{ border: '1px solid #1a2332', animationDelay: `${index * 50}ms` }}>
            <CornerBrackets />
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/8 to-transparent pointer-events-none" />

            {/* Header */}
            <div className="flex justify-between items-center px-4 py-3 border-b border-cyber-border/50 relative z-10">
                <span className="text-[10px] text-cyber-muted font-mono tracking-[0.2em] uppercase">{game.game_id}</span>
                <span className="px-2.5 py-1 bg-cyber-border text-cyber-muted text-[10px] font-display font-600 tracking-[0.2em] uppercase">
                    FINAL
                </span>
            </div>

            {/* Score */}
            <div className="flex items-center justify-between gap-4 p-5 relative z-10">
                {/* Away */}
                <div className={`flex-1 text-center ${awayWon ? 'opacity-100' : 'opacity-50'}`}>
                    <div className={`text-4xl font-bold font-mono mb-1 tabular-nums ${awayWon ? 'text-cyber-green' : 'text-cyber-text'}`}>
                        {game.away_score}
                    </div>
                    <div className={`text-xl font-display font-700 tracking-[0.08em] uppercase ${awayWon ? 'text-cyber-green' : 'text-slate-400'}`}>
                        {game.away_team}
                    </div>
                    {awayWon && <div className="text-[10px] text-cyber-green mt-1 font-bold font-display uppercase tracking-widest">W</div>}
                </div>

                <div className="flex flex-col items-center justify-center min-w-[3rem]">
                    <span className="text-cyber-muted font-mono text-xs">@</span>
                </div>

                {/* Home */}
                <div className={`flex-1 text-center ${homeWon ? 'opacity-100' : 'opacity-50'}`}>
                    <div className={`text-4xl font-bold font-mono mb-1 tabular-nums ${homeWon ? 'text-cyber-green' : 'text-cyber-text'}`}>
                        {game.home_score}
                    </div>
                    <div className={`text-xl font-display font-700 tracking-[0.08em] uppercase ${homeWon ? 'text-cyber-green' : 'text-slate-400'}`}>
                        {game.home_team}
                    </div>
                    {homeWon && <div className="text-[10px] text-cyber-green mt-1 font-bold font-display uppercase tracking-widest">W</div>}
                </div>
            </div>
        </div>
    );
};

// ─── Main Page ────────────────────────────────────────────────────────────────

type TabId = 'today' | 'history';

const BoxScoresPage: React.FC = () => {
    // ── Tab state — preserved in URL so refresh keeps the right tab ──────
    const [searchParams, setSearchParams] = useSearchParams();
    const activeTab = (searchParams.get('tab') as TabId) === 'history' ? 'history' : 'today';
    const setActiveTab = (tab: TabId) => setSearchParams({ tab }, { replace: true });

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
                    // Filter to valid YYYY-MM-DD strings only.
                    // The backend may return game IDs if Firestore parent docs
                    // don't exist as explicit documents yet.
                    const dates: string[] = (data.dates || []).filter((d: string) => DATE_RE.test(d));
                    setAvailableDates(dates);
                    // Auto-select most recent valid date if not today
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
        <div className="h-full flex flex-col p-4 sm:p-6 bg-cyber-bg relative z-10 w-full">
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                 style={{
                   backgroundImage: 'linear-gradient(#00ff88 1px, transparent 1px), linear-gradient(90deg, #00ff88 1px, transparent 1px)',
                   backgroundSize: '32px 32px',
                 }} />

            {/* ── Header ───────────────────────────────────────────────── */}
            <header className="mb-5 flex-shrink-0 relative z-10">
                <div className="header-content">
                    <div className="header-title flex flex-wrap items-center gap-3">
                        <h1 className="text-3xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text">Box Scores</h1>
                        {activeTab === 'today' && (
                            <span className={`px-2.5 py-1 text-[10px] font-display font-600 tracking-[0.2em] uppercase border whitespace-nowrap ${isConnected
                                ? 'bg-cyber-green/5 text-cyber-green border-cyber-green'
                                : isConnecting
                                    ? 'bg-cyber-gold/5 text-cyber-gold border-cyber-gold'
                                    : 'bg-cyber-red/5 text-cyber-red border-cyber-red'
                                }`}>
                                <span className={`inline-block w-1.5 h-1.5 rounded-none mr-1.5 ${isConnected ? 'bg-cyber-green' : isConnecting ? 'bg-cyber-gold animate-pulse' : 'bg-cyber-red'
                                    }`} />
                                {isConnected ? 'LIVE FEED' : isConnecting ? 'CONNECTING…' : 'DISCONNECTED'}
                            </span>
                        )}
                        {activeTab === 'today' && lastUpdate && (
                            <span className="text-[10px] font-mono tracking-widest uppercase text-cyber-muted ml-auto hidden sm:block">
                                Updated {new Date(lastUpdate).toLocaleTimeString()}
                            </span>
                        )}
                    </div>
                </div>
            </header>

            {/* ── Tabs ─────────────────────────────────────────────────── */}
            <div className="flex gap-4 mb-5 flex-shrink-0 border-b border-cyber-border relative z-10 w-full">
                {([['today', 'Today'], ['history', 'History']] as [TabId, string][]).map(([id, label]) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`py-2 px-1 text-xs font-display font-600 tracking-[0.12em] uppercase transition-all duration-100 border-b-2
                            ${activeTab === id
                            ? 'border-cyber-green text-cyber-green'
                            : 'border-transparent text-cyber-muted hover:text-cyber-text'
                            }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* ── History: Date picker row ──────────────────────────────── */}
            {activeTab === 'history' && (
                <div className="flex flex-wrap items-center gap-3 mb-5 flex-shrink-0 relative z-10">
                    <div className="relative">
                        <input
                            id="box-scores-date-picker"
                            type="date"
                            value={selectedDate}
                            max={getTodayStr()}
                            onChange={e => setSelectedDate(e.target.value)}
                            style={{ colorScheme: 'dark' }}
                            className="bg-cyber-surface border border-cyber-border text-cyber-text font-mono text-xs rounded-sm px-3 py-2 focus:outline-none focus:border-cyber-blue cursor-pointer"
                        />
                    </div>

                    {/* Dot indicator */}
                    {datesLoaded && (
                        <span className={`flex items-center gap-1.5 text-[10px] font-display font-600 tracking-[0.1em] uppercase ${hasData ? 'text-cyber-green' : 'text-cyber-muted'}`}>
                            <span className={`w-1.5 h-1.5 rounded-none ${hasData ? 'bg-cyber-green' : 'bg-cyber-border'}`} />
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
                                    className={`text-[10px] uppercase font-mono tracking-widest px-2.5 py-1 rounded-sm border transition-all duration-100 ${selectedDate === d
                                        ? 'bg-cyber-green/10 border-cyber-green/40 text-cyber-green'
                                        : 'bg-cyber-surface border-cyber-border text-cyber-muted hover:text-cyber-text hover:border-cyber-text'
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
            <div className="flex-1 min-h-0 overflow-y-auto scrollbar-premium pb-6 relative z-10">

                {/* ── TODAY TAB ─────────────────────────────────────────── */}
                {activeTab === 'today' && (
                    <>
                        {sortedLiveGames.length > 0 ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                {sortedLiveGames.map((game, i) => (
                                    <LiveGameCard key={game.game_id} game={game} index={i} />
                                ))}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-56 gap-4">
                                <div className="relative w-12 h-12 flex items-center justify-center">
                                    <CornerBrackets color="#1a2332" size={14} />
                                    <span className="font-mono text-[10px] text-cyber-muted tracking-[0.3em]">NULL</span>
                                </div>
                                <p className="font-display font-600 text-xs tracking-[0.15em] uppercase text-cyber-muted">
                                    {isConnecting ? 'CONNECTING TO LIVE FEED' : 'NO GAMES SCHEDULED TODAY'}
                                </p>
                            </div>
                        )}
                    </>
                )}

                {/* ── HISTORY TAB ───────────────────────────────────────── */}
                {activeTab === 'history' && (
                    <>
                        {histLoading && (
                            <div className="flex items-center gap-3">
                                <span className="w-4 h-4 border border-cyber-green/30 border-t-cyber-green rounded-full animate-spin" />
                                <span className="font-mono text-[10px] text-cyber-muted tracking-[0.2em] uppercase">Loading…</span>
                            </div>
                        )}

                        {histError && !histLoading && (
                            <div className="flex items-start gap-3 p-4" style={{ background: 'rgba(255,45,85,0.06)', border: '1px solid rgba(255,45,85,0.2)' }}>
                                <span className="font-mono text-[#ff2d55] text-[10px] font-bold tracking-[0.2em] flex-shrink-0">ERR</span>
                                <div>
                                    <p className="font-display font-600 text-xs tracking-[0.1em] uppercase text-[#ff2d55] mb-1">Failed to load box scores</p>
                                    <p className="font-mono text-[10px] text-[#ff2d55]/60">{histError}</p>
                                </div>
                            </div>
                        )}

                        {!histLoading && !histError && historicalGames.length > 0 && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                                {historicalGames.map((game, i) => (
                                    <HistoricalGameCard key={game.game_id} game={game} index={i} />
                                ))}
                            </div>
                        )}

                        {!histLoading && !histError && historicalGames.length === 0 && (
                            <div className="flex flex-col items-center justify-center h-56 gap-4">
                                <div className="relative w-12 h-12 flex items-center justify-center">
                                    <CornerBrackets color="#1a2332" size={14} />
                                    <span className="font-mono text-[10px] text-cyber-muted tracking-[0.3em]">NULL</span>
                                </div>
                                <p className="font-display font-600 text-xs tracking-[0.15em] uppercase text-cyber-muted">No game records for {selectedDate}</p>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default BoxScoresPage;
