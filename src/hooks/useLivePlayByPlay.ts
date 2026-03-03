import { useState, useEffect, useRef, useCallback } from 'react';
import { ApiContract } from '../api/client';
import { API_BASE } from '../config/apiConfig';

export interface PlayEvent {
    playId: string;
    sequenceNumber: number;
    eventType: string;
    description: string;
    period: number;
    clock: string;
    homeScore: number;
    awayScore: number;
    teamId?: string;
    teamTricode?: string;
    primaryPlayerId?: string;
    primaryPlayerName?: string;
    secondaryPlayerId?: string;
    secondaryPlayerName?: string;
    involvedPlayers?: string[];
    isScoringPlay: boolean;
    isShootingPlay: boolean;
    pointsValue: number;
    shotDistance?: number;
    shotArea?: string;
    shotResult?: 'Made' | 'Missed';
    coordinateX?: number;
    coordinateY?: number;
}

export function useLivePlayByPlay(gameId: string | null) {
    const [plays, setPlays] = useState<PlayEvent[]>([]);
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [isReconnecting, setIsReconnecting] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const eventSourceRef = useRef<EventSource | null>(null);
    const retryTimeoutRef = useRef<any>(null);

    // 1. Initial Hydration
    const fetchCachedPlays = useCallback(async (id: string) => {
        try {
            const res = await ApiContract.executeWeb<{ plays: PlayEvent[] }>({
                path: `v1/games/${id}/plays?limit=1000`
            });
            if (res && res.plays) {
                setPlays(res.plays);
            }
        } catch (err) {
            console.error("Failed to hydrate PBP:", err);
        }
    }, []);

    // 2. SSE Connection Management
    const connectSSE = useCallback((id: string) => {
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }

        // Use robust connection from config
        const baseUrl = API_BASE.replace(/\/+$/, '');
        const sseUrl = `${baseUrl}/v1/games/${id}/stream`;

        const es = new EventSource(sseUrl);
        eventSourceRef.current = es;

        setIsReconnecting(true);

        es.onopen = () => {
            setIsConnected(true);
            setIsReconnecting(false);
            setError(null);
        };

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'connection') {
                    console.log(`PBP SSE Connected for ${data.gameId}`);
                } else if (data.type === 'plays_update' && data.plays) {
                    // Append new plays and deduplicate by sequenceNumber
                    setPlays(prev => {
                        const existingSeq = new Set(prev.map(p => p.sequenceNumber));
                        const newValid = (data.plays as PlayEvent[]).filter(p => !existingSeq.has(p.sequenceNumber));
                        if (newValid.length === 0) return prev;
                        return [...prev, ...newValid].sort((a, b) => a.sequenceNumber - b.sequenceNumber);
                    });
                }
            } catch (e) {
                // usually heartbeat messages ": heartbeat" throw JSON.parse errors, ignore them
            }
        };

        es.onerror = () => {
            setIsConnected(false);
            setIsReconnecting(true);
            es.close();

            // Exponential backoff or simple retry
            retryTimeoutRef.current = setTimeout(() => {
                if (id) connectSSE(id);
            }, 5000);
        };

    }, []);

    useEffect(() => {
        if (!gameId) {
            setPlays([]);
            setIsConnected(false);
            return;
        }

        // Reset state for new game
        setPlays([]);
        setError(null);

        // Initial load
        fetchCachedPlays(gameId).then(() => {
            // Connect to stream after hydration
            connectSSE(gameId);
        });

        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
            if (retryTimeoutRef.current) {
                clearTimeout(retryTimeoutRef.current);
            }
        };
    }, [gameId, fetchCachedPlays, connectSSE]);

    return { plays, isConnected, isReconnecting, error };
}
