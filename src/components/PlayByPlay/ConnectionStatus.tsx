import React from 'react';

interface Props {
    isConnected: boolean;
    isReconnecting: boolean;
    error: string | null;
}

export function ConnectionStatus({ isConnected, isReconnecting, error }: Props) {
    let color = '#94a3b8'; // gray for disconnected/idle
    let text = 'Disconnected';
    let pulse = false;

    if (isConnected) {
        color = '#22c55e'; // green
        text = 'Live Feed Active';
        pulse = true;
    } else if (isReconnecting) {
        color = '#f59e0b'; // amber
        text = 'Reconnecting...';
        pulse = true;
    } else if (error) {
        color = '#ef4444'; // red
        text = `Error: ${error}`;
    }

    return (
        <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            background: 'rgba(15, 23, 42, 0.8)',
            borderRadius: '20px',
            border: `1px solid ${color}40`,
            fontSize: '12px',
            fontWeight: '600',
            color: '#f8fafc'
        }}>
            <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: color,
                boxShadow: pulse ? `0 0 8px ${color}` : 'none',
                opacity: pulse ? 1 : 0.6
            }} />
            {text}
        </div>
    );
}
