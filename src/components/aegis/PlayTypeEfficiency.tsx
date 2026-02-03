import { useEffect, useState } from 'react';

interface PlayType {
    play_type: string;
    ppp: number;
    frequency: number;
    possessions: number;
    percentile: number;
    tier: 'elite' | 'above_average' | 'average' | 'poor';
}

interface PlayTypeData {
    player_id: string;
    player_name: string;
    season: string;
    play_types: PlayType[];
}

interface Props {
    playerId: string;
}

const tierColors: Record<string, { bg: string; text: string; bar: string }> = {
    elite: { bg: 'rgba(34, 197, 94, 0.15)', text: '#22c55e', bar: '#22c55e' },
    above_average: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6', bar: '#3b82f6' },
    average: { bg: 'rgba(234, 179, 8, 0.15)', text: '#eab308', bar: '#eab308' },
    poor: { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444', bar: '#ef4444' }
};

const playTypeLabels: Record<string, string> = {
    'Isolation': '🎯 Isolation',
    'PnR Ball-Handler': '🏀 Pick & Roll',
    'Transition': '⚡ Transition',
    'Spot-Up': '🎪 Spot-Up',
    'Post-Up': '💪 Post-Up',
    'Off-Screen': '🔄 Off-Screen',
    'Hand-Off': '🤝 Hand-Off',
    'Cut': '✂️ Cut',
    'Putbacks': '🔁 Putback',
    'Misc': '📊 Misc'
};

export default function PlayTypeEfficiency({ playerId }: Props) {
    const [data, setData] = useState<PlayTypeData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!playerId) return;

        const fetchPlayTypes = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await fetch(`https://quantsight-cloud-458498663186.us-central1.run.app/players/${playerId}/play-types`);
                if (!res.ok) {
                    throw new Error('No play type data available');
                }
                const result = await res.json();
                setData(result);
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Failed to load');
            } finally {
                setLoading(false);
            }
        };

        fetchPlayTypes();
    }, [playerId]);

    if (loading) {
        return (
            <div className="play-type-efficiency loading">
                <div className="spinner" />
                <span>Loading play types...</span>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="play-type-efficiency error">
                <span>⚠️ {error || 'No data available'}</span>
            </div>
        );
    }

    // Find max PPP for bar scaling
    const maxPPP = Math.max(...data.play_types.map(pt => pt.ppp), 1.5);

    return (
        <div className="play-type-efficiency">
            <div className="header">
                <h3>📊 Play Type Efficiency</h3>
                <span className="season">{data.season}</span>
            </div>

            <div className="play-types-grid">
                {data.play_types.map((pt, index) => {
                    const colors = tierColors[pt.tier] || tierColors.average;
                    const barWidth = (pt.ppp / maxPPP) * 100;
                    const label = playTypeLabels[pt.play_type] || pt.play_type;

                    return (
                        <div
                            key={`${index}-${pt.play_type}`}
                            className="play-type-row"
                            style={{ backgroundColor: colors.bg }}
                        >
                            <div className="play-type-info">
                                <span className="play-type-name">{label}</span>
                                <span className="frequency" title="Usage frequency">
                                    {pt.frequency.toFixed(1)}%
                                </span>
                            </div>

                            <div className="bar-container">
                                <div
                                    className="bar"
                                    style={{
                                        width: `${barWidth}%`,
                                        backgroundColor: colors.bar
                                    }}
                                />
                            </div>

                            <div className="stats">
                                <span className="ppp" style={{ color: colors.text }}>
                                    {pt.ppp.toFixed(2)} PPP
                                </span>
                                <span
                                    className="percentile"
                                    style={{
                                        backgroundColor: colors.bar,
                                        color: '#fff'
                                    }}
                                >
                                    {pt.percentile.toFixed(0)}%ile
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="legend">
                <span className="legend-item elite">● Elite (75th+)</span>
                <span className="legend-item above">● Above Avg (50-74)</span>
                <span className="legend-item avg">● Average (25-49)</span>
                <span className="legend-item poor">● Poor (&lt;25)</span>
            </div>

            <style>{`
                .play-type-efficiency {
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    border-radius: 12px;
                    padding: 20px;
                    color: #fff;
                }
                
                .play-type-efficiency.loading,
                .play-type-efficiency.error {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 12px;
                    min-height: 200px;
                    color: #888;
                }
                
                .spinner {
                    width: 24px;
                    height: 24px;
                    border: 3px solid #333;
                    border-top-color: #3b82f6;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                }
                
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 16px;
                }
                
                .header h3 {
                    margin: 0;
                    font-size: 18px;
                    font-weight: 600;
                }
                
                .season {
                    font-size: 12px;
                    color: #888;
                    background: rgba(255,255,255,0.1);
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                
                .play-types-grid {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                
                .play-type-row {
                    display: grid;
                    grid-template-columns: 140px 1fr 120px;
                    gap: 12px;
                    align-items: center;
                    padding: 10px 12px;
                    border-radius: 8px;
                    transition: transform 0.2s;
                }
                
                .play-type-row:hover {
                    transform: translateX(4px);
                }
                
                .play-type-info {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                }
                
                .play-type-name {
                    font-size: 13px;
                    font-weight: 500;
                }
                
                .frequency {
                    font-size: 11px;
                    color: #888;
                }
                
                .bar-container {
                    height: 8px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 4px;
                    overflow: hidden;
                }
                
                .bar {
                    height: 100%;
                    border-radius: 4px;
                    transition: width 0.5s ease-out;
                }
                
                .stats {
                    display: flex;
                    gap: 8px;
                    align-items: center;
                    justify-content: flex-end;
                }
                
                .ppp {
                    font-size: 13px;
                    font-weight: 600;
                }
                
                .percentile {
                    font-size: 10px;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-weight: 600;
                }
                
                .legend {
                    display: flex;
                    gap: 16px;
                    justify-content: center;
                    margin-top: 16px;
                    padding-top: 12px;
                    border-top: 1px solid rgba(255,255,255,0.1);
                }
                
                .legend-item {
                    font-size: 11px;
                    color: #888;
                }
                
                .legend-item.elite { color: #22c55e; }
                .legend-item.above { color: #3b82f6; }
                .legend-item.avg { color: #eab308; }
                .legend-item.poor { color: #ef4444; }
            `}</style>
        </div>
    );
}
