import React, { useState, useEffect } from 'react';
import './ProgressiveLoadingSkeleton.css';

interface ProgressStep {
    id: string;
    label: string;
    status: 'pending' | 'loading' | 'complete';
    duration?: number;
}

interface ProgressiveLoadingSkeletonProps {
    isLoading: boolean;
    simulationId?: string;
    estimatedDuration?: number; // in ms, default 4100
    onComplete?: () => void;
}

const DEFAULT_STEPS: ProgressStep[] = [
    { id: 'dfg', label: 'Fetching DFG% for matchup defenders...', status: 'pending', duration: 800 },
    { id: 'usage', label: 'Loading Usage Vacuum redistribution...', status: 'pending', duration: 600 },
    { id: 'pace', label: 'Calculating pace-adjusted stats...', status: 'pending', duration: 500 },
    { id: 'friction', label: 'Applying defensive friction physics...', status: 'pending', duration: 700 },
    { id: 'sim', label: 'Running 500-game Crucible simulation...', status: 'pending', duration: 1500 },
];

const ProgressiveLoadingSkeleton: React.FC<ProgressiveLoadingSkeletonProps> = ({
    isLoading,
    simulationId,
    estimatedDuration = 4100,
    onComplete
}) => {
    const [steps, setSteps] = useState<ProgressStep[]>(DEFAULT_STEPS);
    const [currentStepIndex, setCurrentStepIndex] = useState(0);
    const [timeRemaining, setTimeRemaining] = useState(estimatedDuration);
    const [overallProgress, setOverallProgress] = useState(0);

    // Reset when loading starts
    useEffect(() => {
        if (isLoading) {
            setSteps(DEFAULT_STEPS.map(s => ({ ...s, status: 'pending' })));
            setCurrentStepIndex(0);
            setTimeRemaining(estimatedDuration);
            setOverallProgress(0);
        }
    }, [isLoading, estimatedDuration]);

    // Animate through steps
    useEffect(() => {
        if (!isLoading) return;

        const stepTimer = setTimeout(() => {
            if (currentStepIndex < steps.length) {
                setSteps(prev => prev.map((step, idx) => {
                    if (idx < currentStepIndex) return { ...step, status: 'complete' };
                    if (idx === currentStepIndex) return { ...step, status: 'loading' };
                    return step;
                }));

                // Move to next step after duration
                const currentStep = steps[currentStepIndex];
                setTimeout(() => {
                    setCurrentStepIndex(prev => prev + 1);
                    setSteps(prev => prev.map((s, idx) =>
                        idx === currentStepIndex ? { ...s, status: 'complete' } : s
                    ));
                }, currentStep.duration || 500);
            }
        }, 100);

        return () => clearTimeout(stepTimer);
    }, [isLoading, currentStepIndex, steps]);

    // Countdown timer
    useEffect(() => {
        if (!isLoading || timeRemaining <= 0) return;

        const interval = setInterval(() => {
            setTimeRemaining(prev => Math.max(0, prev - 100));
            setOverallProgress(prev => Math.min(100, prev + (100 / (estimatedDuration / 100))));
        }, 100);

        return () => clearInterval(interval);
    }, [isLoading, timeRemaining, estimatedDuration]);

    // Notify completion
    useEffect(() => {
        if (overallProgress >= 100 && onComplete) {
            onComplete();
        }
    }, [overallProgress, onComplete]);

    if (!isLoading) return null;

    return (
        <div className="progressive-skeleton">
            <div className="skeleton-header">
                <div className="skeleton-icon pulse-ring">🔮</div>
                <div className="skeleton-title">
                    <h3>Crucible Simulation Running</h3>
                    <span className="simulation-id">{simulationId && `ID: ${simulationId}`}</span>
                </div>
            </div>

            <div className="progress-steps">
                {steps.map((step, idx) => (
                    <div
                        key={step.id}
                        className={`progress-step ${step.status}`}
                    >
                        <div className="step-indicator">
                            {step.status === 'complete' && '✓'}
                            {step.status === 'loading' && <span className="spinner-mini" />}
                            {step.status === 'pending' && (idx + 1)}
                        </div>
                        <span className="step-label">{step.label}</span>
                    </div>
                ))}
            </div>

            <div className="overall-progress">
                <div className="progress-bar-container">
                    <div
                        className="progress-bar-fill"
                        style={{ width: `${overallProgress}%` }}
                    />
                </div>
                <div className="progress-stats">
                    <span className="progress-percent">{Math.round(overallProgress)}%</span>
                    <span className="time-remaining">
                        ~{(timeRemaining / 1000).toFixed(1)}s remaining
                    </span>
                </div>
            </div>

            <div className="skeleton-grid">
                {[1, 2, 3, 4].map(i => (
                    <div key={i} className="skeleton-card shimmer">
                        <div className="skeleton-line short" />
                        <div className="skeleton-line" />
                        <div className="skeleton-line medium" />
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ProgressiveLoadingSkeleton;
