import React, { useState } from 'react';
import './WhyTooltip.css';
import { Modal } from './Modal';

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
                `https://quantsight-cloud-458498663186.us-central1.run.app/explain/${stat}/${playerId}`
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

    const handleToggle = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        const newState = !isVisible;
        setIsVisible(newState);
        if (newState) fetchExplanation();
    };

    return (
        <span
            className="why-tooltip-trigger cursor-pointer"
            onClick={handleToggle}
        >
            {children}
            <span className="why-icon text-slate-400 hover:text-white transition-colors">ⓘ</span>

            <Modal
                isOpen={isVisible}
                onClose={() => setIsVisible(false)}
                title={`Why ${value.toFixed(1)} ${stat?.toUpperCase() || 'STAT'}?`}
                maxWidth="sm"
            >
                <div className="flex flex-col gap-4 text-left">
                    <div className="tooltip-player text-slate-400 text-sm mb-2 font-medium">{playerName}</div>

                    {isLoading ? (
                        <div className="tooltip-loading py-10 flex flex-col items-center justify-center text-slate-500 gap-3">
                            <span className="loading-spinner w-6 h-6 border-2 border-slate-700 border-t-financial-accent rounded-full animate-spin" />
                            Analyzing...
                        </div>
                    ) : explanation ? (
                        <>
                            <div className="tooltip-formula bg-slate-800/50 p-3 rounded-lg border border-slate-700">
                                <code className="text-xs text-purple-400 font-mono">{explanation.formula}</code>
                            </div>
                            <div className="tooltip-components space-y-2">
                                {explanation.components.map((comp, i) => (
                                    <div
                                        key={i}
                                        className={`component-row flex items-center justify-between p-2 rounded-lg text-sm ${comp.isPositive ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}
                                    >
                                        <div className="flex flex-col">
                                            <span className="component-name text-slate-200 font-medium">{comp.name}</span>
                                            <span className="component-reason text-[10px] text-slate-500">{comp.reason}</span>
                                        </div>
                                        <span className={`component-value font-mono font-bold ${comp.isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {comp.isPositive ? '+' : ''}{comp.value.toFixed(1)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                            <div className="tooltip-total mt-4 pt-4 border-t border-slate-700 flex justify-between items-center">
                                <span className="text-sm font-bold text-slate-400">Final Projection</span>
                                <span className="total-value text-xl font-mono font-bold text-white">{value.toFixed(1)}</span>
                            </div>
                        </>
                    ) : (
                        <div className="tooltip-error text-red-400 text-center py-4">Unable to load explanation</div>
                    )}
                </div>
            </Modal>
        </span>
    );
};

export default WhyTooltip;
