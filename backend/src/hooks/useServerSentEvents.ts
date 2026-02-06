import { useState, useEffect, useCallback, useRef } from 'react';

interface SSEOptions {
    url: string;
    onMessage?: (data: any) => void;
    onError?: (error: Event) => void;
    onOpen?: () => void;
    autoReconnect?: boolean;
    reconnectInterval?: number;
    maxRetries?: number;
}

interface SSEState {
    isConnected: boolean;
    isConnecting: boolean;
    error: Error | null;
    retryCount: number;
}

export function useServerSentEvents(options: SSEOptions) {
    const {
        url,
        onMessage,
        onError,
        onOpen,
        autoReconnect = true,
        reconnectInterval = 3000,
        maxRetries = 5
    } = options;

    const [state, setState] = useState<SSEState>({
        isConnected: false,
        isConnecting: false,
        error: null,
        retryCount: 0
    });

    const eventSourceRef = useRef<EventSource | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    const connect = useCallback(() => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        setState(prev => ({ ...prev, isConnecting: true, error: null }));

        try {
            const eventSource = new EventSource(url);
            eventSourceRef.current = eventSource;

            eventSource.onopen = () => {
                setState(prev => ({
                    ...prev,
                    isConnected: true,
                    isConnecting: false,
                    retryCount: 0
                }));
                onOpen?.();
            };

            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    onMessage?.(data);
                } catch {
                    onMessage?.(event.data);
                }
            };

            eventSource.onerror = (error) => {
                setState(prev => ({
                    ...prev,
                    isConnected: false,
                    isConnecting: false,
                    error: new Error('SSE connection failed')
                }));
                onError?.(error);

                eventSource.close();
                eventSourceRef.current = null;

                // Auto-reconnect with exponential backoff
                if (autoReconnect) {
                    setState(prev => {
                        if (prev.retryCount < maxRetries) {
                            const delay = reconnectInterval * Math.pow(2, prev.retryCount);
                            console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${prev.retryCount + 1})`);

                            reconnectTimeoutRef.current = setTimeout(connect, delay);
                            return { ...prev, retryCount: prev.retryCount + 1 };
                        }
                        console.error('[SSE] Max retries reached');
                        return prev;
                    });
                }
            };

        } catch (error) {
            setState(prev => ({
                ...prev,
                isConnecting: false,
                error: error as Error
            }));
        }
    }, [url, onMessage, onError, onOpen, autoReconnect, reconnectInterval, maxRetries]);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
        }
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setState({
            isConnected: false,
            isConnecting: false,
            error: null,
            retryCount: 0
        });
    }, []);

    useEffect(() => {
        connect();
        return () => disconnect();
    }, [connect, disconnect]);

    return {
        ...state,
        connect,
        disconnect
    };
}

// Simplified hook for simulation progress
export function useSimulationProgress(simulationId: string | null) {
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState<string>('');
    const [results, setResults] = useState<any>(null);

    const { isConnected, error } = useServerSentEvents({
        url: simulationId
            ? `https://quantsight-cloud-458498663186.us-central1.run.app/events/simulation/${simulationId}`
            : '',
        onMessage: (data) => {
            if (data.type === 'progress') {
                setProgress(data.percent);
                setStatus(data.message);
            } else if (data.type === 'complete') {
                setProgress(100);
                setResults(data.results);
            }
        }
    });

    return { progress, status, results, isConnected, error };
}

export default useServerSentEvents;
