/**
 * NexusHealthPanel Component
 * Displays Nexus Hub system health with cooldown alerts
 */

import React from 'react';
import { useNexusHealth } from '../../hooks/useNexusHealth';
import './NexusHealthPanel.css';

export const NexusHealthPanel: React.FC = () => {
    const {
        health,
        loading,
        error,
        lastUpdated,
        getStatusSummary,
        isInCooldown
    } = useNexusHealth({
        refreshInterval: 30000,
        autoRefresh: true
    });

    const summary = getStatusSummary();

    if (loading && !health) {
        return (
            <div className="nexus-health-panel loading">
                <div className="spinner"></div>
                <span>Loading Nexus status...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="nexus-health-panel error">
                <div className="error-icon">⚠️</div>
                <div className="error-message">
                    <strong>Nexus Hub Offline</strong>
                    <p>{error}</p>
                </div>
            </div>
        );
    }

    if (!health) return null;

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'healthy': return '✓';
            case 'degraded': return '◐';
            case 'critical': return '⚠';
            case 'down': return '✗';
            case 'cooldown': return '⏸';
            default: return '?';
        }
    };

    const getStatusClass = (status: string) => {
        return `status-${status.toLowerCase()}`;
    };

    const activeCooldowns = Object.entries(health.cooldowns || {});

    return (
        <div className={`nexus-health-panel ${getStatusClass(summary.status)}`}>
            {/* Header */}
            <div className="panel-header">
                <div className="status-badge">
                    <span className="status-icon">{getStatusIcon(summary.status)}</span>
                    <span className="status-text">{summary.status.toUpperCase()}</span>
                </div>
                <div className="last-updated">
                    {lastUpdated && (
                        <span>Updated {new Date(lastUpdated).toLocaleTimeString()}</span>
                    )}
                </div>
            </div>

            {/* Summary Stats */}
            <div className="summary-stats">
                <div className="stat healthy">
                    <span className="stat-value">{summary.healthy}</span>
                    <span className="stat-label">Healthy</span>
                </div>
                <div className="stat degraded">
                    <span className="stat-value">{summary.degraded}</span>
                    <span className="stat-label">Degraded</span>
                </div>
                <div className="stat down">
                    <span className="stat-value">{summary.down}</span>
                    <span className="stat-label">Down</span>
                </div>
                <div className="stat cooldown">
                    <span className="stat-value">{summary.cooldown}</span>
                    <span className="stat-label">Cooldown</span>
                </div>
            </div>

            {/* Cooldown Alerts */}
            {activeCooldowns.length > 0 && (
                <div className="cooldown-alerts">
                    <div className="alert-header">
                        <span className="alert-icon">⏸</span>
                        <span className="alert-title">Active Cooldowns</span>
                    </div>
                    <div className="cooldown-list">
                        {activeCooldowns.map(([service, until]) => (
                            <div key={service} className="cooldown-item">
                                <span className="service-name">{service}</span>
                                <span className="cooldown-time">
                                    Until {new Date(until).toLocaleTimeString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Service Status Grid */}
            <div className="service-grid">
                {/* Core Services */}
                <div className="service-section">
                    <h4>Core Services</h4>
                    {Object.entries(health.core).map(([name, svc]) => (
                        <div key={name} className={`service-row ${getStatusClass(svc.status)}`}>
                            <span className="service-icon">{getStatusIcon(svc.status)}</span>
                            <span className="service-name">{name.replace(/_/g, ' ')}</span>
                            {svc.response_time_ms && (
                                <span className="response-time">{svc.response_time_ms}ms</span>
                            )}
                        </div>
                    ))}
                </div>

                {/* External Services */}
                <div className="service-section">
                    <h4>External APIs</h4>
                    {Object.entries(health.external).map(([name, svc]) => (
                        <div key={name} className={`service-row ${getStatusClass(svc.status)}`}>
                            <span className="service-icon">{getStatusIcon(svc.status)}</span>
                            <span className="service-name">{name.replace(/_/g, ' ')}</span>
                            {isInCooldown(name) && (
                                <span className="cooldown-badge">⏸ Cooldown</span>
                            )}
                            {svc.error_count > 0 && (
                                <span className="error-count">{svc.error_count} errors</span>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* System Info */}
            <div className="system-info">
                <div className="info-item">
                    <span className="info-label">Nexus Hub</span>
                    <span className="info-value">v1.0.0</span>
                </div>
                <div className="info-item">
                    <span className="info-label">Mode</span>
                    <span className="info-value">Advisory</span>
                </div>
            </div>
        </div>
    );
};

export default NexusHealthPanel;
