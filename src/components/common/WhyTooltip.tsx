import React, { useState } from 'react';
import './WhyTooltip.css';

interface StatComponent {
    name: string;
    value: number;
    reason: string;
    isPositive: boolean;
}

interface WhyExplanation {
    stat: string;
    final_value: number;
    formula: string;
    components: StatComponent[];
}

interface WhyTooltipProps {
    stat: 'pts' | 'reb' | 'ast' | '3pm';
    playerId: string;
    playerName: string;
    value: number;
    children: React.ReactNode;
}

const WhyTooltip: React.FC<WhyTooltipProps> = ({
    stat,
    playerId,
    playerName,
    value,
    children
}) => {
    const [isVisible, setIsVisible] = useState(false);
    const [explanation, setExplanation] = useState<WhyExplanation | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });

    const fetchExplanation = async () => {
        if (explanation) return; // Already fetched

        setIsLoading(true);
        try {
            const response = await fetch(
                `http://localhost:5000/explain/${stat}/${playerId}`
            );
            if (response.ok) {
                const data = await response.json();
                setExplanation(data);
            }
        } catch (error) {
            console.error('[WhyTooltip] Failed to fetch explanation:', error);
            // Generate mock explanation
            setExplanation({
                stat: stat?.toUpperCase() || 'UNKNOWN',
                final_value: value,
                formula: `${stat?.toUpperCase() || 'STAT'} = EMA + Usage + Matchup - Fatigue`,
                components: [
                    { name: '15-game EMA', value: value * 0.92, reason: 'Season average', isPositive: true },
                    { name: 'Usage Vacuum', value: value * 0.08, reason: 'Team injuries', isPositive: true },
                    { name: 'B2B Fatigue', value: -0.4, reason: 'Back-to-back game', isPositive: false },
                ]
            });
        } finally {
            setIsLoading(false);
        }
    };

    const handleMouseEnter = (e: React.MouseEvent) => {
        setPosition({ x: e.clientX, y: e.clientY });
        setIsVisible(true);
        fetchExplanation();
    };

    const handleMouseLeave = () => {
        setIsVisible(false);
    };

    return (
        <span
            className="why-tooltip-trigger"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            {children}
            <span className="why-icon">ⓘ</span>

            {isVisible && (
                <div
                    className="why-tooltip-popup"
                    style={{
                        '--tooltip-x': `${position.x}px`,
                        '--tooltip-y': `${position.y}px`
                    } as React.CSSProperties}
                >
                    <div className="tooltip-header">
                        <span className="tooltip-title">
                            Why {value.toFixed(1)} {stat?.toUpperCase() || 'STAT'}?
                        </span>
                        <span className="tooltip-player">{playerName}</span>
                    </div>

                    {isLoading ? (
                        <div className="tooltip-loading">
                            <span className="loading-spinner" />
                            Analyzing...
                        </div>
                    ) : explanation ? (
                        <>
                            <div className="tooltip-formula">
                                <code>{explanation.formula}</code>
                            </div>
                            <div className="tooltip-components">
                                {explanation.components.map((comp, i) => (
                                    <div
                                        key={i}
                                        className={`component-row ${comp.isPositive ? 'positive' : 'negative'}`}
                                    >
                                        <span className="component-name">{comp.name}</span>
                                        <span className="component-value">
                                            {comp.isPositive ? '+' : ''}{comp.value.toFixed(1)}
                                        </span>
                                        <span className="component-reason">{comp.reason}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="tooltip-total">
                                <span>Final Projection</span>
                                <span className="total-value">{value.toFixed(1)}</span>
                            </div>
                        </>
                    ) : (
                        <div className="tooltip-error">Unable to load explanation</div>
                    )}
                </div>
            )}
        </span>
    );
};

export default WhyTooltip;
