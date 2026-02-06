import React, { useState, useEffect, useCallback } from 'react';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface ConnectionStatusProps {
    checkInterval?: number;  // ms between health checks
    apiUrl?: string;
    showLabel?: boolean;
    className?: string;
}

type ConnectionState = 'connected' | 'degraded' | 'disconnected' | 'checking';

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
    checkInterval = 30000,
    apiUrl = 'https://quantsight-cloud-458498663186.us-central1.run.app/health',
    showLabel = true,
    className = ''
}) => {
    const [status, setStatus] = useState<ConnectionState>('checking');
    const [lastCheck, setLastCheck] = useState<Date | null>(null);
    const [retryCount, setRetryCount] = useState(0);

    const checkConnection = useCallback(async () => {
        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 5000);

            const response = await fetch(apiUrl, {
                signal: controller.signal,
                cache: 'no-store'
            });
            clearTimeout(timeout);

            if (response.ok) {
                const data = await response.json();
                // Check if backend reports degraded state
                if (data.status === 'degraded') {
                    setStatus('degraded');
                } else {
                    setStatus('connected');
                }
                setRetryCount(0);
            } else {
                setStatus('degraded');
            }
        } catch (error) {
            setStatus('disconnected');
            setRetryCount(prev => prev + 1);
        }
        setLastCheck(new Date());
    }, [apiUrl]);

    useEffect(() => {
        checkConnection();
        const interval = setInterval(checkConnection, checkInterval);
        return () => clearInterval(interval);
    }, [checkConnection, checkInterval]);

    const handleRetry = () => {
        setStatus('checking');
        checkConnection();
    };

    const statusConfig = {
        connected: {
            icon: <Wifi size={14} />,
            color: 'text-emerald-400',
            bgColor: 'bg-emerald-500/20',
            label: 'Connected'
        },
        degraded: {
            icon: <Wifi size={14} />,
            color: 'text-yellow-400',
            bgColor: 'bg-yellow-500/20',
            label: 'Degraded'
        },
        disconnected: {
            icon: <WifiOff size={14} />,
            color: 'text-red-400',
            bgColor: 'bg-red-500/20',
            label: 'Disconnected'
        },
        checking: {
            icon: <RefreshCw size={14} className="animate-spin" />,
            color: 'text-slate-400',
            bgColor: 'bg-slate-500/20',
            label: 'Checking...'
        }
    };

    const config = statusConfig[status];

    return (
        <div
            className={`inline-flex items-center gap-2 px-2 py-1 rounded-full ${config.bgColor} ${className}`}
            title={`Last check: ${lastCheck?.toLocaleTimeString() || 'Never'}`}
        >
            <span className={config.color}>{config.icon}</span>

            {showLabel && (
                <span className={`text-xs font-medium ${config.color}`}>
                    {config.label}
                </span>
            )}

            {status === 'disconnected' && retryCount > 2 && (
                <button
                    onClick={handleRetry}
                    className="ml-1 text-xs text-red-300 hover:text-red-200 underline"
                >
                    Retry
                </button>
            )}
        </div>
    );
};

export default ConnectionStatus;
