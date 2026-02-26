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
    circuitOpen: boolean;
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
        retryCount: 0,
        circuitOpen: false
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

                eventSource.onopen = null;
                eventSource.onmessage = null;
                eventSource.onerror = null;
                eventSource.close();
                eventSourceRef.current = null;

                // Auto-reconnect with exponential backoff
                if (autoReconnect) {
                    setState(prev => {
                        if (prev.circuitOpen) return prev; // Do not retry if circuit is open

                        if (prev.retryCount < maxRetries) {
                            const delay = reconnectInterval * Math.pow(2, prev.retryCount);
                            console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${prev.retryCount + 1})`);

                            reconnectTimeoutRef.current = setTimeout(connect, delay);
                            return { ...prev, retryCount: prev.retryCount + 1 };
                        }

                        // Circuit Breaker triggers
                        console.error('[SSE] Max retries reached, circuit breaker opened');
                        return { ...prev, circuitOpen: true };
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
            reconnectTimeoutRef.current = null;
        }
        if (eventSourceRef.current) {
            // Sever all event handlers before closing to prevent ghost emissions during teardown
            eventSourceRef.current.onopen = null;
            eventSourceRef.current.onmessage = null;
            eventSourceRef.current.onerror = null;
            eventSourceRef.current.close();
            eventSourceRef.current = null;
        }
        setState(prev => ({
            isConnected: false,
            isConnecting: false,
            error: null,
            retryCount: 0,
            circuitOpen: prev.circuitOpen
        }));
    }, []);

    useEffect(() => {
        // Only auto-connect if document is visible
        if (!document.hidden && !state.circuitOpen) {
            connect();
        }

        const handleVisibilityChange = () => {
            if (document.hidden) {
                console.log('[SSE Visibility Constraint] Document hidden, pausing stream resource');
                disconnect();
            } else {
                console.log('[SSE Visibility Constraint] Document visible, resuming stream resource');
                // Using connect directly here is fine; the effect unmount will disconnect it
                // Make sure we only connect if circuit isn't blown
                setState(prev => {
                    if (!prev.circuitOpen) connect();
                    return prev;
                });
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            disconnect();
        };
    }, [connect, disconnect, state.circuitOpen]);

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

    const pulseBase = import.meta.env?.VITE_PULSE_API_URL || 'https://quantsight-pulse-458498663186.us-central1.run.app';

    const { isConnected, error } = useServerSentEvents({
        url: simulationId
            ? `${pulseBase}/events/simulation/${simulationId}`
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
