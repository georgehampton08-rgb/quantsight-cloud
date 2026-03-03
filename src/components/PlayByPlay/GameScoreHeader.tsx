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
        <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '20px', background: '#1e293b', borderRadius: '12px',
            marginBottom: '20px', border: '1px solid rgba(255,255,255,0.1)',
            boxShadow: '0 4px 15px rgba(0,0,0,0.3)'
        }}>
            <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase' }}>Away</div>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fff' }}>{awayTeam}</div>
                <div style={{ fontSize: '42px', fontWeight: '900', color: '#38bdf8' }}>{awayScore}</div>
            </div>

            <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                {status === 'live' || status === 'in' ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', animation: 'pulse 1.5s infinite' }} />
                        <span style={{ color: '#ef4444', fontWeight: 'bold', fontSize: '14px', letterSpacing: '1px' }}>LIVE</span>
                    </div>
                ) : (
                    <div style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '8px', textTransform: 'uppercase' }}>
                        {status}
                    </div>
                )}
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#f1f5f9', fontFamily: 'monospace' }}>
                    {clock}
                </div>
                <div style={{ fontSize: '14px', color: '#cbd5e1', marginTop: '4px' }}>
                    Quarter {period}
                </div>
            </div>

            <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase' }}>Home</div>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fff' }}>{homeTeam}</div>
                <div style={{ fontSize: '42px', fontWeight: '900', color: '#38bdf8' }}>{homeScore}</div>
            </div>
        </div>
    );
}
