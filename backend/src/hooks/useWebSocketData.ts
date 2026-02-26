/**
 * useWebSocketData — Phase 8 Step 8.6.2
 * ========================================
 * React hook for consuming typed WebSocket event data.
 *
 * Usage:
 *   const leaderData = useWebSocketData<LeadersPayload>('leaders_update');
 *   const gameData = useWebSocketData<GamePayload>('game_update');
 */

import { useState, useEffect } from 'react';
import { wsClient } from '../services/wsClient';

export function useWebSocketData<T>(eventType: string): T | null {
    const [data, setData] = useState<T | null>(null);

    useEffect(() => {
        const unsubscribe = wsClient.on(eventType, (d) => {
            setData(d as T);
        });
        return unsubscribe;
    }, [eventType]);

    return data;
}

export default useWebSocketData;
