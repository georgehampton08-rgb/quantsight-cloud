import React, { useState, useEffect } from 'react';
import './FreshnessHalo.css';

interface FreshnessHaloProps {
    lastUpdated: string | Date | null;  // ISO timestamp
    dataSource?: string;
    showSyncButton?: boolean;
    onSync?: () => Promise<void>;
    size?: 'small' | 'medium' | 'large';
}

type FreshnessLevel = 'fresh' | 'stale' | 'critical';

const getFreshnessLevel = (lastUpdated: Date | null): FreshnessLevel => {
    if (!lastUpdated) return 'critical';

    const now = new Date();
    const ageHours = (now.getTime() - lastUpdated.getTime()) / (1000 * 60 * 60);

    if (ageHours < 2) return 'fresh';
    if (ageHours < 24) return 'stale';
    return 'critical';
};

const getAgeLabel = (lastUpdated: Date | null): string => {
    if (!lastUpdated) return 'Never synced';

    const now = new Date();
    const diffMs = now.getTime() - lastUpdated.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
};

const FreshnessHalo: React.FC<FreshnessHaloProps> = ({
    lastUpdated,
    dataSource,
    showSyncButton = true,
    onSync,
    size = 'medium'
}) => {
    const [isSyncing, setIsSyncing] = useState(false);
    const [timestamp, setTimestamp] = useState<Date | null>(null);
    const [ageLabel, setAgeLabel] = useState('');
    const [freshnessLevel, setFreshnessLevel] = useState<FreshnessLevel>('fresh');

    useEffect(() => {
        if (lastUpdated) {
            const date = typeof lastUpdated === 'string' ? new Date(lastUpdated) : lastUpdated;
            setTimestamp(date);
        } else {
            setTimestamp(null);
        }
    }, [lastUpdated]);

    // Update age label every minute, and freshness level every 5 minutes
    useEffect(() => {
        const updateAge = () => {
            setAgeLabel(getAgeLabel(timestamp));
            setFreshnessLevel(getFreshnessLevel(timestamp));
        };

        updateAge();
        const ageInterval = setInterval(updateAge, 60000); // UI update every 1m
        const freshnessInterval = setInterval(updateAge, 5 * 60 * 1000); // Freshness check every 5m

        return () => {
            clearInterval(ageInterval);
            clearInterval(freshnessInterval);
        };
    }, [timestamp]);

    const handleSync = async () => {
        if (!onSync || isSyncing) return;

        setIsSyncing(true);
        try {
            await onSync();
            setTimestamp(new Date());
        } catch (error) {
            console.error('[FreshnessHalo] Sync failed:', error);
        } finally {
            setIsSyncing(false);
        }
    };

    const isStale = freshnessLevel !== 'fresh';

    return (
        <div className={`freshness-halo-container ${size}`}>
            <div className={`freshness-halo ${freshnessLevel} ${isStale ? 'glow-amber' : ''}`}>
                <div className="halo-ring" />
                <div className="halo-content">
                    <span className="halo-icon">
                        {freshnessLevel === 'fresh' && '✓'}
                        {freshnessLevel === 'stale' && '⚠'}
                        {freshnessLevel === 'critical' && '!'}
                    </span>
                </div>
            </div>

            <div className="freshness-info">
                {dataSource && <span className="data-source">{dataSource}</span>}
                <span className={`age-label ${freshnessLevel}`}>{ageLabel}</span>
            </div>

            {showSyncButton && isStale && (
                <button
                    className={`sync-button ${freshnessLevel === 'critical' ? 'pulse-attention' : 'subtle'} ${isSyncing ? 'syncing' : ''} ${isStale ? 'animate-glow' : ''}`}
                    onClick={handleSync}
                    disabled={isSyncing}
                >
                    {isSyncing ? (
                        <>
                            <span className="sync-spinner" />
                            Syncing...
                        </>
                    ) : (
                        <>🔄 {freshnessLevel === 'critical' ? 'Sync Data' : 'Refresh'}</>
                    )}
                </button>
            )}
        </div>
    );
};

export default FreshnessHalo;
