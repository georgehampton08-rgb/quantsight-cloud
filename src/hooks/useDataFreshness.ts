import { useState, useEffect } from 'react';
import { PlayerApi } from '../services/playerApi';

interface FreshnessState {
    status: 'fresh' | 'stale' | 'live' | 'checking';
    lastUpdated: string;
    source: 'cached' | 'live';
    needsRefresh: boolean;
}

export function useDataFreshness(playerId: string, initialLastUpdated: string) {
    const [freshness, setFreshness] = useState<FreshnessState>({
        status: 'fresh',
        lastUpdated: initialLastUpdated,
        source: 'cached',
        needsRefresh: false
    });
    const [isRefreshing, setIsRefreshing] = useState(false);

    // Background freshness check
    useEffect(() => {
        const checkFreshness = async () => {
            try {
                // Check if data is >2 days old
                const lastDate = new Date(initialLastUpdated);
                const now = new Date();
                const daysDiff = Math.floor((now.getTime() - lastDate.getTime()) / (1000 * 60 * 60 * 24));

                if (daysDiff > 2) {
                    setFreshness(prev => ({
                        ...prev,
                        status: 'stale',
                        needsRefresh: true
                    }));
                }
            } catch (error) {
                console.error('[Freshness Check] Error:', error);
            }
        };

        // Run check after brief delay to not block initial render
        const timer = setTimeout(checkFreshness, 500);
        return () => clearTimeout(timer);
    }, [playerId, initialLastUpdated]);

    const forceRefresh = async (playerName: string) => {
        setIsRefreshing(true);
        setFreshness(prev => ({ ...prev, status: 'checking' }));

        try {
            const result = await PlayerApi.forceRefresh(playerId, playerName, freshness.lastUpdated);

            // Null safety: handle case where API returns null or malformed response
            if (!result || typeof result !== 'object') {
                console.warn('[Force Refresh] Received null or invalid response');
                setFreshness(prev => ({ ...prev, status: 'stale' }));
                return;
            }

            if (result.status === 'LIVE_UPDATED') {
                setFreshness({
                    status: 'live',
                    lastUpdated: result.new_last_game || result.new_stats?.date || new Date().toISOString().split('T')[0],
                    source: 'live',
                    needsRefresh: false
                });
            } else if (result.status === 'API_ERROR') {
                console.error('[Force Refresh] API Error:', result.message);
                setFreshness(prev => ({ ...prev, status: 'stale' }));
            } else {
                // No new data, but mark as fresh since we just checked
                setFreshness(prev => ({
                    ...prev,
                    status: 'fresh',
                    needsRefresh: false
                }));
            }
        } catch (error) {
            console.error('[Force Refresh] Error:', error);
            setFreshness(prev => ({ ...prev, status: 'stale' }));
        } finally {
            setIsRefreshing(false);
        }
    };

    return {
        freshness,
        isRefreshing,
        forceRefresh
    };
}
