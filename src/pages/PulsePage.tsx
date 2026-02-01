import React, { useState, useEffect } from 'react';
import './MatchupLabPage.css'; // Reusing glass card styles
import { useLiveGameStore } from '../context/LiveGameContext';

// Mobile-Ready JSON Schema (matching backend)
interface LiveGameLeader {
    playerId: string;
    name: string;
    team: string;
    pie: number;
    stats: {
        pts: number;
        reb: number;
        ast: number;
    };
}

// Reuse styles but add specific Pulse layout
const PulsePage: React.FC = () => {
    const { state: liveState } = useLiveGameStore();

    // In a real implementation, we might fetch multiple games from Firestore here.
    // For now, we visualize the single active game from our LiveGameContext
    // which effectively acts as our "Hot Store" client-side mirror.

    // Derived leaders list (mocking the backend 'leaders' array structure from context)
    const leaders: LiveGameLeader[] = Array.from(liveState.activePlayers.values())
        .map(p => ({
            playerId: p.playerId,
            name: p.name,
            team: p.team === 'home' ? 'HOME' : 'AWAY', // Map to simpler tricode in real app
            pie: p.pie,
            stats: { pts: p.points, reb: p.rebounds, ast: p.assists }
        }))
        .sort((a, b) => b.pie - a.pie)
        .slice(0, 10);

    return (
        <div className="matchup-lab-page h-full overflow-y-auto p-8">
            <header className="lab-header mb-8">
                <div className="header-content">
                    <div className="header-title">
                        <span className="lab-icon text-red-500 animate-pulse">❤️</span>
                        <h1>The Pulse</h1>
                        <span className="ai-badge bg-red-500/20 text-red-400 border border-red-500/30">
                            LIVE TELEMETRY
                        </span>
                    </div>
                </div>
            </header>

            <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">

                {/* LEFT COLUMN: Vertical Scoreboard */}
                <div className="lg:col-span-4 flex flex-col gap-6">
                    <div className="glass-card p-6 relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-red-500 to-transparent opacity-50" />

                        <div className="flex justify-between items-center mb-6">
                            <span className="text-gray-400 font-mono text-sm">GAME ID: {liveState.gameId || 'LIVE-SIM'}</span>
                            <span className="live-pill px-3 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-bold border border-red-500/30 flex items-center gap-2">
                                <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                                LIVE
                            </span>
                        </div>

                        <div className="text-center mb-8">
                            <div className="text-5xl font-bold font-mono tracking-tighter text-white mb-2">
                                {liveState.clock}
                            </div>
                            <div className="text-gray-400 text-sm tracking-widest uppercase">
                                POST-SEASON • Q{liveState.quarter}
                            </div>
                        </div>

                        <div className="flex justify-between items-center px-4 mb-8">
                            <div className="text-center">
                                <div className="text-4xl font-bold text-white mb-1">{liveState.homeScore}</div>
                                <div className="text-lg text-gray-400 font-bold">LAL</div>
                            </div>
                            <div className="text-2xl font-mono text-gray-600">vs</div>
                            <div className="text-center">
                                <div className="text-4xl font-bold text-white mb-1">{liveState.awayScore}</div>
                                <div className="text-lg text-gray-400 font-bold">DEN</div>
                            </div>
                        </div>

                        <div className="bg-white/5 rounded-lg p-4 text-center">
                            <div className="text-xs text-gray-500 uppercase mb-1">Differential</div>
                            <div className={`text-2xl font-bold font-mono ${Math.abs(liveState.homeScore - liveState.awayScore) <= 5 ? 'text-yellow-400 animate-pulse' : 'text-white'
                                }`}>
                                {Math.abs(liveState.homeScore - liveState.awayScore)} PTS
                            </div>
                        </div>
                    </div>

                    {/* Mobile-Ready JSON Preview */}
                    <div className="glass-card p-4 opacity-75">
                        <div className="text-xs text-gray-500 font-mono mb-2 uppercase border-b border-white/5 pb-2">
                            Mobile Payload Preview (JSON)
                        </div>
                        <pre className="text-[10px] text-green-400 font-mono overflow-x-auto p-2 bg-black/30 rounded">
                            {JSON.stringify({
                                gameId: liveState.gameId || "0022300123",
                                meta: {
                                    clock: liveState.clock,
                                    period: liveState.quarter,
                                    status: "LIVE"
                                },
                                score: {
                                    home: liveState.homeScore,
                                    away: liveState.awayScore,
                                    diff: liveState.homeScore - liveState.awayScore
                                }
                            }, null, 2)}
                        </pre>
                    </div>
                </div>

                {/* RIGHT COLUMN: Live Alpha Leaderboard */}
                <div className="lg:col-span-8">
                    <div className="glass-card h-full flex flex-col">
                        <div className="card-header p-6 border-b border-white/10 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <span className="text-2xl">⚡</span>
                                <h2 className="text-xl font-bold text-white">Live Alpha Leaderboard</h2>
                            </div>
                            <div className="text-xs text-gray-400 bg-white/5 px-3 py-1 rounded-full">
                                SORTED BY: <span className="text-yellow-400 font-bold">IN-GAME PIE</span>
                            </div>
                        </div>

                        <div className="p-0 overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b border-white/5 text-gray-400 text-xs uppercase tracking-wider">
                                        <th className="p-4 font-medium">Rank</th>
                                        <th className="p-4 font-medium">Player</th>
                                        <th className="p-4 font-medium">Team</th>
                                        <th className="p-4 font-medium text-right">PTS</th>
                                        <th className="p-4 font-medium text-right">REB</th>
                                        <th className="p-4 font-medium text-right">AST</th>
                                        <th className="p-4 font-medium text-right text-yellow-500">PIE %</th>
                                    </tr>
                                </thead>
                                <tbody className="text-sm">
                                    {leaders.map((leader, idx) => (
                                        <tr
                                            key={leader.playerId}
                                            className={`border-b border-white/5 hover:bg-white/5 transition-colors ${idx === 0 ? 'bg-yellow-500/10' : ''
                                                }`}
                                        >
                                            <td className="p-4 font-mono text-gray-500">#{idx + 1}</td>
                                            <td className="p-4 font-bold text-white flex items-center gap-3">
                                                {leader.name}
                                                {idx === 0 && <span className="text-yellow-400 animate-pulse">👑</span>}
                                            </td>
                                            <td className="p-4 text-gray-400">{leader.team}</td>
                                            <td className="p-4 text-right font-mono text-gray-300">{leader.stats.pts}</td>
                                            <td className="p-4 text-right font-mono text-gray-300">{leader.stats.reb}</td>
                                            <td className="p-4 text-right font-mono text-gray-300">{leader.stats.ast}</td>
                                            <td className="p-4 text-right font-mono font-bold text-yellow-400">
                                                {(leader.pie * 100).toFixed(1)}%
                                            </td>
                                        </tr>
                                    ))}
                                    {leaders.length === 0 && (
                                        <tr>
                                            <td colSpan={7} className="p-8 text-center text-gray-500">
                                                Waiting for live telemetry...
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default PulsePage;
