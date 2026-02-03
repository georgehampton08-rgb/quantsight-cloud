import React, { useState, useEffect } from 'react';
import './NextDayDriftToast.css';

interface DriftAudit {
    audit_date: string;
    adjustments: {
        param: string;
        old_value: number;
        new_value: number;
        delta_pct: number;
    }[];
    trigger_game: string;
    overall_delta_pct: number;
}

interface NextDayDriftToastProps {
    autoFetch?: boolean;
    dismissAfterMs?: number;
}

const STORAGE_KEY = 'quantsight_drift_toast_dismissed';

const NextDayDriftToast: React.FC<NextDayDriftToastProps> = ({
    autoFetch = true,
    dismissAfterMs = 8000
}) => {
    const [audit, setAudit] = useState<DriftAudit | null>(null);
    const [isVisible, setIsVisible] = useState(false);
    const [isExiting, setIsExiting] = useState(false);

    useEffect(() => {
        // Check if already dismissed today
        const lastDismissed = localStorage.getItem(STORAGE_KEY);
        if (lastDismissed) {
            const dismissedDate = new Date(lastDismissed);
            const today = new Date();
            if (dismissedDate.toDateString() === today.toDateString()) {
                return; // Already dismissed today
            }
        }

        if (autoFetch) {
            fetchAudit();
        }
    }, [autoFetch]);

    const fetchAudit = async () => {
        try {
            const response = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/auto-tuner/last-audit');
            if (response.ok) {
                const data = await response.json();
                if (data && data.audit_date) {
                    setAudit(data);
                    setIsVisible(true);

                    // Auto-dismiss after timeout
                    setTimeout(() => dismiss(), dismissAfterMs);
                }
            }
        } catch (error) {
            console.log('[NextDayDrift] No audit data available');
        }
    };

    const dismiss = () => {
        setIsExiting(true);
        setTimeout(() => {
            setIsVisible(false);
            localStorage.setItem(STORAGE_KEY, new Date().toISOString());
        }, 300);
    };

    if (!isVisible || !audit) return null;

    return (
        <div className={`drift-toast ${isExiting ? 'exiting' : 'entering'}`}>
            <div className="drift-icon">🔧</div>
            <div className="drift-content">
                <div className="drift-title">Auto-Tuner Completed</div>
                <div className="drift-message">
                    Model weights adjusted by <span className="delta-value">
                        {(audit?.overall_delta_pct || 0) > 0 ? '+' : ''}{(audit?.overall_delta_pct || 0).toFixed(1)}%
                    </span> based on last night's <span className="game-ref">{audit?.trigger_game || 'unknown'}</span> results.
                </div>
                {(audit?.adjustments || []).length > 0 && (
                    <div className="drift-details">
                        {(audit?.adjustments || []).slice(0, 2).map((adj, i) => (
                            <span key={i} className="adjustment-chip">
                                {adj?.param || 'N/A'}: {(adj?.delta_pct || 0) > 0 ? '+' : ''}{(adj?.delta_pct || 0).toFixed(2)}%
                            </span>
                        ))}
                    </div>
                )}
            </div>
            <button className="drift-dismiss" onClick={dismiss}>×</button>
        </div>
    );
};

export default NextDayDriftToast;
