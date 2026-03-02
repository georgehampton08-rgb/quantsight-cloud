import React, { useEffect, useState, useCallback } from 'react';
import { Focus, Activity, Calendar } from 'lucide-react';
import { ApiContract } from '../../api/client';
import { API_BASE } from '../../config/apiConfig';
import { SectionErrorBoundary } from '../common/SectionErrorBoundary';

// ─── Types ────────────────────────────────────────────────────────────────────

interface BoxScorePlayer {
    player_id: string;
    player_name?: string;
    name?: string;
    team_abbreviation?: string;
    team_tricode?: string;
    start_position?: string | null;
    min?: string | null;
    minutes?: string | null;
    pts: number;
    reb: number;
    ast: number;
    stl: number;
    blk: number;
    tov: number;
    fgm: number;
    fga: number;
    fg3m: number;
    fg3a: number;
    ftm: number;
    fta: number;
    plus_minus: number;
}

interface BoxScoreGame {
    gameId: string;
    game_id?: string;
    game_date?: string;
    matchup?: string;
    home: string;
    away: string;
    home_team?: string | any;
    away_team?: string | any;
    home_score: number;
    away_score: number;
    status: string;
    volatility?: string;
}

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

const getTodayStr = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD local

// ─── Player row (shared between live and historical views) ────────────────────

const renderPlayerRow = (p: BoxScorePlayer) => {
    const minVal = p.min || p.minutes || '';
    const dnp = minVal === null || minVal === '0:00' || minVal === '' || minVal === '0';
    const efficiency = dnp ? 0 : (p.pts + p.reb + p.ast + p.stl + p.blk - (p.fga - p.fgm) - (p.fta - p.ftm) - p.tov);
    const getPtsColor = (pts: number) => pts >= 30 ? 'text-emerald-400 font-bold' : pts >= 20 ? 'text-emerald-500/80 font-bold' : 'text-slate-300';
    const playerName = p.player_name || p.name || '';

    return (
        <tr key={p.player_id} className="bg-slate-900/40 hover:bg-slate-800/60 transition-colors border-b border-slate-800/50 last:border-0 group">
            <td className="px-2 py-2 sm:px-4 sm:py-3 whitespace-nowrap sticky left-0 z-10 bg-slate-900/90 group-hover:bg-slate-800/90 backdrop-blur-sm shadow-[4px_0_8px_rgba(0,0,0,0.1)] transition-colors border-r border-slate-800/30">
                <div className="flex items-center gap-2">
                    {p.start_position && <span className="text-[10px] bg-slate-800 text-slate-400 px-1 py-0.5 rounded font-bold w-6 text-center">{p.start_position}</span>}
                    <span className={`text-xs sm:text-sm font-bold ${dnp ? 'text-slate-500' : 'text-slate-200'} truncate max-w-[100px] sm:max-w-none`}>{playerName}</span>
                </div>
            </td>
            {dnp ? (
                <td colSpan={8} className="px-2 py-3 text-[10px] sm:text-xs text-slate-500 italic text-center uppercase tracking-widest whitespace-nowrap">
                    Did Not Play
                </td>
            ) : (
                <>
                    <td className="px-1 py-2 sm:px-4 sm:py-3 text-center text-[10px] sm:text-xs text-slate-400 font-mono">{minVal}</td>
                    <td className={`px-1 py-2 sm:px-4 sm:py-3 text-center text-xs sm:text-sm ${getPtsColor(p.pts)}`}>{p.pts}</td>
                    <td className="px-1 py-2 sm:px-4 sm:py-3 text-center text-xs sm:text-sm text-slate-300">{p.reb}</td>
                    <td className="px-1 py-2 sm:px-4 sm:py-3 text-center text-xs sm:text-sm text-slate-300">{p.ast}</td>
                    <td className="px-1 py-2 sm:px-4 sm:py-3 text-center text-[10px] sm:text-xs text-slate-400 font-mono hidden md:table-cell">{p.fgm}/{p.fga}</td>
                    <td className="px-1 py-2 sm:px-4 sm:py-3 text-center text-[10px] sm:text-xs text-slate-400 font-mono hidden lg:table-cell">{p.fg3m}/{p.fg3a}</td>
                    <td className={`px-1 py-2 sm:px-4 sm:py-3 text-center text-[10px] sm:text-xs font-bold ${p.plus_minus > 0 ? 'text-emerald-400' : p.plus_minus < 0 ? 'text-red-400' : 'text-slate-500'}`}>
                        {p.plus_minus > 0 ? `+${p.plus_minus}` : p.plus_minus}
                    </td>
                    <td className="px-1 py-2 sm:px-4 sm:py-3 text-center text-xs text-slate-500 font-mono hidden sm:table-cell">{efficiency}</td>
                </>
            )}
        </tr>
    );
};

const TableHeader = () => (
    <thead className="text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-900/90 sticky top-0 z-20 shadow-sm backdrop-blur-md border-b border-slate-700/50">
        <tr>
            <th className="px-1 py-3 sm:px-4 sticky left-0 z-30 bg-slate-900/95 backdrop-blur-sm shadow-[4px_0_8px_rgba(0,0,0,0.1)] border-r border-slate-800/30">Player</th>
            <th className="px-1 py-3 sm:px-4 text-center">MIN</th>
            <th className="px-1 py-3 sm:px-4 text-center text-slate-200">PTS</th>
            <th className="px-1 py-3 sm:px-4 text-center">REB</th>
            <th className="px-1 py-3 sm:px-4 text-center">AST</th>
            <th className="px-1 py-3 sm:px-4 text-center hidden md:table-cell">FG</th>
            <th className="px-1 py-3 sm:px-4 text-center hidden lg:table-cell">3PT</th>
            <th className="px-1 py-3 sm:px-4 text-center">+/-</th>
            <th className="px-1 py-3 sm:px-4 text-center hidden sm:table-cell">EFF</th>
        </tr>
    </thead>
);

// ─── Main Component ───────────────────────────────────────────────────────────

export function BoxScoreViewerContent() {
    // ── Date state ─────────────────────────────────────────────────────────
    const [selectedDate, setSelectedDate] = useState<string>(getTodayStr());
    const [availableDates, setAvailableDates] = useState<string[]>([]);
    const isToday = selectedDate === getTodayStr();

    // ── Live state (today) ─────────────────────────────────────────────────
    const [loading, setLoading] = useState(false);
    const [games, setGames] = useState<BoxScoreGame[]>([]);
    const [selectedGame, setSelectedGame] = useState<string | null>(null);
    const [boxScores, setBoxScores] = useState<{
        home: BoxScorePlayer[];
        away: BoxScorePlayer[];
        game_info?: BoxScoreGame;
    } | null>(null);

    // ── Historical state (past dates) ──────────────────────────────────────
    const [histGames, setHistGames] = useState<HistoricalGame[]>([]);
    const [selectedHistGame, setSelectedHistGame] = useState<string | null>(null);
    const [histBoxScore, setHistBoxScore] = useState<{
        home: BoxScorePlayer[];
        away: BoxScorePlayer[];
        game_info?: any;
    } | null>(null);
    const [histLoading, setHistLoading] = useState(false);
    const [histError, setHistError] = useState<string | null>(null);

    // ── Fetch available dates for dot indicators ───────────────────────────
    useEffect(() => {
        fetch(`${API_BASE}/api/box-scores/dates`)
            .then(r => r.ok ? r.json() : null)
            .then(d => d?.dates && setAvailableDates(d.dates))
            .catch(() => { });
    }, []);

    // ── LIVE: load today's schedule ────────────────────────────────────────
    const loadGames = useCallback(async () => {
        if (!isToday) return;
        setLoading(true);
        try {
            const res = await ApiContract.execute<{ games: BoxScoreGame[] }>(null, { path: 'schedule' });
            if (res.data?.games) {
                setGames(res.data.games);
                const firstStarted = res.data.games.find(g => g.status === 'LIVE' || g.status === 'FINAL');
                const first = firstStarted || res.data.games[0];
                if (first) setSelectedGame(first.gameId || first.game_id || null);
            }
        } catch (e) {
            console.error('Failed to load schedule', e);
        } finally {
            setLoading(false);
        }
    }, [isToday]);

    useEffect(() => {
        if (isToday) {
            setHistGames([]);
            setHistBoxScore(null);
            setHistError(null);
            loadGames();
        }
    }, [isToday, loadGames]);

    // ── LIVE: load box score for selected game ─────────────────────────────
    useEffect(() => {
        if (!isToday || !selectedGame) return;
        const loadBoxScore = async () => {
            setLoading(true);
            try {
                const res = await ApiContract.execute<any>(null, { path: `pulse/boxscore/${selectedGame}` });
                if (res.data) { setBoxScores(res.data); return; }
            } catch { }
            try {
                const fallback = await ApiContract.execute<any>(null, { path: `boxscore/${selectedGame}` });
                if (fallback.data?.home_team) {
                    setBoxScores({
                        home: fallback.data.home_team.players || [],
                        away: fallback.data.away_team.players || [],
                        game_info: {
                            gameId: fallback.data.game_id || selectedGame,
                            home_team: fallback.data.home_team.abbreviation,
                            away_team: fallback.data.away_team.abbreviation,
                            home: fallback.data.home_team.abbreviation,
                            away: fallback.data.away_team.abbreviation,
                            home_score: games.find(g => (g.game_id || g.gameId) === selectedGame)?.home_score || 0,
                            away_score: games.find(g => (g.game_id || g.gameId) === selectedGame)?.away_score || 0,
                            status: games.find(g => (g.game_id || g.gameId) === selectedGame)?.status || 'FINAL',
                        }
                    });
                } else {
                    setBoxScores(fallback.data);
                }
            } catch {
                setBoxScores(null);
            } finally {
                setLoading(false);
            }
        };
        loadBoxScore();
    }, [selectedGame, isToday]);

    // ── HISTORICAL: load final scores for selected past date ───────────────
    useEffect(() => {
        if (isToday) return;
        setHistLoading(true);
        setHistError(null);
        setHistGames([]);
        setHistBoxScore(null);
        setSelectedHistGame(null);

        fetch(`${API_BASE}/api/box-scores?date=${selectedDate}`)
            .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || `Error ${r.status}`)))
            .then(d => {
                const gs: HistoricalGame[] = d.games || [];
                setHistGames(gs);
                if (gs.length > 0) setSelectedHistGame(gs[0].game_id);
            })
            .catch(err => setHistError(typeof err === 'string' ? err : 'Failed to load box scores.'))
            .finally(() => setHistLoading(false));
    }, [selectedDate, isToday]);

    // ── HISTORICAL: load player-level box score for selected past game ─────
    useEffect(() => {
        if (isToday || !selectedHistGame) return;
        setHistLoading(true);
        fetch(`${API_BASE}/api/box-scores/game/${selectedHistGame}?date=${selectedDate}`)
            .then(r => r.ok ? r.json() : null)
            .then(d => { if (d) setHistBoxScore(d); })
            .catch(() => { })
            .finally(() => setHistLoading(false));
    }, [selectedHistGame, selectedDate, isToday]);

    const selectedHistData = histGames.find(g => g.game_id === selectedHistGame);
    const hasData = availableDates.includes(selectedDate);

    // ── Render ─────────────────────────────────────────────────────────────
    return (
        <div className="h-full w-full min-w-0 flex flex-col space-y-4 overflow-hidden">

            {/* ── Date picker row ────────────────────────────────────────── */}
            <div className="flex flex-wrap items-center gap-3 flex-shrink-0">
                <div className="flex items-center gap-2 text-slate-400">
                    <Calendar className="w-4 h-4 text-financial-accent" />
                    <input
                        id="box-score-date-picker"
                        type="date"
                        value={selectedDate}
                        max={getTodayStr()}
                        onChange={e => {
                            setSelectedDate(e.target.value);
                            setBoxScores(null);
                            setGames([]);
                        }}
                        className="bg-slate-800/80 border border-slate-700/60 text-slate-200 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-financial-accent/60 cursor-pointer"
                    />
                </div>

                {/* Today quick-reset */}
                {!isToday && (
                    <button
                        onClick={() => setSelectedDate(getTodayStr())}
                        className="text-xs px-3 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/20 transition-all"
                    >
                        ↩ Today
                    </button>
                )}

                {/* Data indicator */}
                {!isToday && (
                    <span className={`flex items-center gap-1.5 text-xs ${hasData ? 'text-emerald-400' : 'text-slate-500'}`}>
                        <span className={`w-2 h-2 rounded-full ${hasData ? 'bg-emerald-500' : 'bg-slate-600'}`} />
                        {hasData ? 'Saved data available' : 'No saved data'}
                    </span>
                )}

                {/* Live indicator for today */}
                {isToday && (
                    <span className="flex items-center gap-1.5 text-xs text-red-400">
                        <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                        Live Feed
                    </span>
                )}

                {/* Quick-jump buttons for last 5 saved dates */}
                {availableDates.length > 0 && !isToday && (
                    <div className="flex gap-1.5 flex-wrap ml-auto">
                        {availableDates.slice(0, 5).map(d => (
                            <button
                                key={d}
                                onClick={() => setSelectedDate(d)}
                                className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${selectedDate === d
                                        ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                                        : 'bg-slate-800/60 border-slate-700/50 text-slate-400 hover:text-slate-200 hover:border-slate-500'
                                    }`}
                            >
                                {d.slice(5)}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* ── TODAY: game selector strip ─────────────────────────────── */}
            {isToday && (
                <div className="flex gap-2.5 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-slate-700 hover:scrollbar-thumb-slate-600 flex-shrink-0">
                    {games.map(game => (
                        <button
                            key={game.game_id || game.gameId}
                            onClick={() => setSelectedGame(game.game_id || game.gameId)}
                            className={`flex-shrink-0 px-4 py-3 border rounded-xl flex flex-col items-center gap-1 transition-all min-w-[140px] ${selectedGame === (game.game_id || game.gameId)
                                    ? 'bg-indigo-900/30 border-indigo-500/50 shadow-[0_0_15px_rgba(99,102,241,0.2)]'
                                    : 'bg-slate-800/40 border-slate-700/50 hover:bg-slate-800/80 hover:border-slate-500/50 text-slate-400'
                                }`}
                        >
                            <div className="flex items-center gap-3 w-full justify-between px-1">
                                <span className={`font-black text-sm ${selectedGame === (game.game_id || game.gameId) ? 'text-white' : ''}`}>{game.away || game.away_team}</span>
                                <span className={`text-[10px] px-1.5 py-[1px] rounded font-bold uppercase tracking-wider ${game.status === 'LIVE' ? 'bg-red-500/20 text-red-400 animate-pulse' :
                                        game.status === 'FINAL' ? 'bg-slate-700/50 text-slate-400' :
                                            'bg-emerald-500/10 text-emerald-500'
                                    }`}>
                                    {game.status === 'LIVE' ? 'LIVE' : game.status === 'FINAL' ? 'FNL' : 'UP'}
                                </span>
                                <span className={`font-black text-sm ${selectedGame === (game.game_id || game.gameId) ? 'text-white' : ''}`}>{game.home || game.home_team}</span>
                            </div>
                            <div className="flex items-center justify-between w-full px-2 mt-1">
                                <span className={`font-mono text-sm ${game.away_score > game.home_score ? 'text-emerald-400 font-bold' : ''}`}>{game.away_score || '-'}</span>
                                <span className="text-slate-600 text-[10px]">vs</span>
                                <span className={`font-mono text-sm ${game.home_score > game.away_score ? 'text-emerald-400 font-bold' : ''}`}>{game.home_score || '-'}</span>
                            </div>
                        </button>
                    ))}
                </div>
            )}

            {/* ── HISTORICAL: game selector strip ───────────────────────── */}
            {!isToday && histGames.length > 0 && (
                <div className="flex gap-2.5 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-slate-700 flex-shrink-0">
                    {histGames.map(game => (
                        <button
                            key={game.game_id}
                            onClick={() => setSelectedHistGame(game.game_id)}
                            className={`flex-shrink-0 px-4 py-3 border rounded-xl flex flex-col items-center gap-1 transition-all min-w-[140px] ${selectedHistGame === game.game_id
                                    ? 'bg-emerald-900/20 border-emerald-500/40 shadow-[0_0_12px_rgba(16,185,129,0.15)]'
                                    : 'bg-slate-800/40 border-slate-700/50 hover:bg-slate-800/80 hover:border-slate-500/50 text-slate-400'
                                }`}
                        >
                            <div className="flex items-center gap-3 w-full justify-between px-1">
                                <span className={`font-black text-sm ${selectedHistGame === game.game_id ? 'text-white' : ''}`}>{game.away_team}</span>
                                <span className="text-[10px] px-1.5 py-[1px] rounded font-bold uppercase tracking-wider bg-slate-700/50 text-slate-400">FNL</span>
                                <span className={`font-black text-sm ${selectedHistGame === game.game_id ? 'text-white' : ''}`}>{game.home_team}</span>
                            </div>
                            <div className="flex items-center justify-between w-full px-2 mt-1">
                                <span className={`font-mono text-sm ${game.winner === game.away_team ? 'text-emerald-400 font-bold' : 'text-slate-400'}`}>{game.away_score}</span>
                                <span className="text-slate-600 text-[10px]">vs</span>
                                <span className={`font-mono text-sm ${game.winner === game.home_team ? 'text-emerald-400 font-bold' : 'text-slate-400'}`}>{game.home_score}</span>
                            </div>
                        </button>
                    ))}
                </div>
            )}

            {/* ── Box score tables area (scrollable) ────────────────────── */}
            <div className="flex-1 min-h-0 overflow-y-auto">

                {/* Loading */}
                {(loading || histLoading) && (
                    <div className="flex flex-col items-center justify-center p-12 bg-slate-900/30 border border-slate-800 rounded-2xl h-48">
                        <Activity className="w-8 h-8 text-indigo-400 animate-spin mb-4" />
                        <div className="text-sm font-mono text-slate-400 tracking-widest uppercase">Hydrating Telemetry...</div>
                    </div>
                )}

                {/* Historical error */}
                {!isToday && histError && !histLoading && (
                    <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                        <span className="text-lg">⚠️</span>
                        <div><div className="font-semibold mb-1">Failed to load box scores</div><div className="text-red-400/70">{histError}</div></div>
                    </div>
                )}

                {/* Historical empty */}
                {!isToday && !histLoading && !histError && histGames.length === 0 && (
                    <div className="flex flex-col items-center justify-center p-12 bg-slate-900/30 border border-slate-800 rounded-2xl text-slate-500 h-48">
                        <Focus className="w-12 h-12 mb-4 opacity-50" />
                        <p className="font-medium text-lg text-slate-400">No records for {selectedDate}</p>
                        <p className="text-sm mt-2 text-center max-w-xs">
                            {availableDates.length > 0 ? `Most recent saved date: ${availableDates[0]}` : 'This may be an NBA off day or data not yet saved.'}
                        </p>
                    </div>
                )}

                {/* Historical: show final scores only when no player-level data loaded */}
                {!isToday && !histLoading && selectedHistData && !histBoxScore && (
                    <div className="space-y-3 p-4 bg-slate-900/30 border border-slate-800 rounded-2xl">
                        <div className="text-xs text-slate-500 uppercase tracking-widest mb-2">Final Score — {selectedHistData.matchup}</div>
                        <div className="flex items-center justify-around py-6">
                            <div className={`text-center ${selectedHistData.winner === selectedHistData.away_team ? 'opacity-100' : 'opacity-50'}`}>
                                <div className={`text-4xl font-bold font-mono ${selectedHistData.winner === selectedHistData.away_team ? 'text-emerald-400' : 'text-white'}`}>{selectedHistData.away_score}</div>
                                <div className="text-sm font-bold text-slate-300 mt-1">{selectedHistData.away_team}</div>
                                {selectedHistData.winner === selectedHistData.away_team && <div className="text-[10px] text-emerald-500 mt-1 font-bold uppercase tracking-widest">WIN</div>}
                            </div>
                            <div className="text-slate-600 font-mono text-xl">@</div>
                            <div className={`text-center ${selectedHistData.winner === selectedHistData.home_team ? 'opacity-100' : 'opacity-50'}`}>
                                <div className={`text-4xl font-bold font-mono ${selectedHistData.winner === selectedHistData.home_team ? 'text-emerald-400' : 'text-white'}`}>{selectedHistData.home_score}</div>
                                <div className="text-sm font-bold text-slate-300 mt-1">{selectedHistData.home_team}</div>
                                {selectedHistData.winner === selectedHistData.home_team && <div className="text-[10px] text-emerald-500 mt-1 font-bold uppercase tracking-widest">WIN</div>}
                            </div>
                        </div>
                    </div>
                )}

                {/* Live: no data state */}
                {isToday && !loading && !boxScores && (
                    <div className="flex flex-col items-center justify-center p-12 bg-slate-900/30 border border-slate-800 rounded-2xl text-slate-500">
                        <Focus className="w-12 h-12 mb-4 opacity-50" />
                        <p className="font-medium text-lg text-slate-400">Box Score Data Unavailable</p>
                        <p className="text-sm mt-2 max-w-sm text-center">
                            Telemetry has not hydrated for this matchup yet. If the game is live, ensure Pulse Sync is active.
                        </p>
                    </div>
                )}

                {/* Live: player tables */}
                {isToday && !loading && boxScores && (
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full overflow-x-hidden">
                        {/* AWAY */}
                        <div className="flex flex-col bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl">
                            <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700/50 flex justify-between items-center">
                                <h3 className="text-lg font-black text-white tracking-widest">{boxScores.game_info?.away_team || 'AWAY'}</h3>
                                <span className="text-2xl font-mono text-emerald-400 font-bold">{boxScores.game_info?.away_score}</span>
                            </div>
                            <div className="overflow-x-auto flex-1 h-[400px] xl:h-auto overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
                                <table className="w-full text-left relative"><TableHeader /><tbody>{boxScores.away.map(renderPlayerRow)}</tbody></table>
                            </div>
                        </div>
                        {/* HOME */}
                        <div className="flex flex-col bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl">
                            <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700/50 flex justify-between items-center">
                                <h3 className="text-lg font-black text-white tracking-widest">{boxScores.game_info?.home_team || 'HOME'}</h3>
                                <span className="text-2xl font-mono text-emerald-400 font-bold">{boxScores.game_info?.home_score}</span>
                            </div>
                            <div className="overflow-x-auto flex-1 h-[400px] xl:h-auto overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
                                <table className="w-full text-left relative"><TableHeader /><tbody>{boxScores.home.map(renderPlayerRow)}</tbody></table>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export const BoxScoreViewer = () => (
    <SectionErrorBoundary fallbackMessage="BoxScore Matrix Viewer offline">
        <BoxScoreViewerContent />
    </SectionErrorBoundary>
);
