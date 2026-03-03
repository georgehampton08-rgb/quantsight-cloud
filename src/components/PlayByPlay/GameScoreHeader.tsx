import React from 'react';
import './PlayByPlay.css';

interface Props {
    homeScore: number;
    awayScore: number;
    homeTeam: string;
    awayTeam: string;
    clock: string;
    period: number;
    status: string;
}

export function GameScoreHeader({
    homeScore, awayScore, homeTeam, awayTeam, clock, period, status
}: Props) {
    return (
        <div className="game-score-header" style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '18px 20px', background: '#1e293b', borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.08)',
            boxShadow: '0 4px 15px rgba(0,0,0,0.3)'
        }}>
            <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Away</div>
                <div className="team-name" style={{ fontSize: 'clamp(14px, 3vw, 22px)', fontWeight: 'bold', color: '#fff' }}>{awayTeam}</div>
                <div className="score-val" style={{ fontSize: 'clamp(28px, 5vw, 42px)', fontWeight: '900', color: '#38bdf8', lineHeight: 1 }}>{awayScore}</div>
            </div>

            <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                {status === 'live' || status === 'in' ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', animation: 'pulse-dot 1.5s infinite' }} />
                        <span style={{ color: '#ef4444', fontWeight: 'bold', fontSize: '13px', letterSpacing: '1px' }}>LIVE</span>
                    </div>
                ) : (
                    <div style={{ color: '#64748b', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        {status === 'offline' ? 'Pre-Game' : status}
                    </div>
                )}
                <div style={{ fontSize: 'clamp(16px, 3vw, 22px)', fontWeight: 'bold', color: '#f1f5f9', fontFamily: 'monospace' }}>
                    {clock}
                </div>
                <div style={{ fontSize: '12px', color: '#94a3b8' }}>Quarter {period}</div>
            </div>

            <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Home</div>
                <div className="team-name" style={{ fontSize: 'clamp(14px, 3vw, 22px)', fontWeight: 'bold', color: '#fff' }}>{homeTeam}</div>
                <div className="score-val" style={{ fontSize: 'clamp(28px, 5vw, 42px)', fontWeight: '900', color: '#38bdf8', lineHeight: 1 }}>{homeScore}</div>
            </div>
        </div>
    );
}
