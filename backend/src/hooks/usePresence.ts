/**
 * usePresence — Phase 8 Step 8.6.2
 * ===================================
 * React hook for real-time viewer count via WebSocket presence updates.
 *
 * Usage:
 *   const viewers = usePresence('player_id', '2544');
 *   // viewers = 7
 */

import { useState, useEffect } from 'react';
import { wsClient } from '../services/wsClient';

interface PresenceUpdate {
    context_type: string;
    context_id: string;
    viewers: number;
}

export function usePresence(contextType: string, contextId: string): number {
    const [viewers, setViewers] = useState<number>(0);

    useEffect(() => {
        const unsubscribe = wsClient.on('presence_update', (data: unknown) => {
            const d = data as PresenceUpdate;
            if (d.context_type === contextType && d.context_id === contextId) {
                setViewers(d.viewers);
            }
        });
        return unsubscribe;
    }, [contextType, contextId]);

    return viewers;
}

export default usePresence;
