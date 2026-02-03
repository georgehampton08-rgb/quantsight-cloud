import { useState, useCallback } from 'react';

interface CrucibleResult {
    home_team_stats: Record<string, any>;
    away_team_stats: Record<string, any>;
    final_score: [number, number];
    was_clutch: boolean;
    was_blowout: boolean;
    key_events: string[];
    execution_time_ms: number;
}

interface SimulationProgress {
    percent: number;
    message: string;
    step: string;
}

interface UseCrucibleSimulationReturn {
    runSimulation: (homeTeam: string, awayTeam: string, numGames?: number) => Promise<void>;
    progress: SimulationProgress | null;
    results: CrucibleResult | null;
    isRunning: boolean;
    error: Error | null;
    reset: () => void;
}

export function useCrucibleSimulation(): UseCrucibleSimulationReturn {
    const [isRunning, setIsRunning] = useState(false);
    const [progress, setProgress] = useState<SimulationProgress | null>(null);
    const [results, setResults] = useState<CrucibleResult | null>(null);
    const [error, setError] = useState<Error | null>(null);

    const reset = useCallback(() => {
        setIsRunning(false);
        setProgress(null);
        setResults(null);
        setError(null);
    }, []);

    const runSimulation = useCallback(async (
        homeTeam: string,
        awayTeam: string,
        numGames: number = 500
    ) => {
        reset();
        setIsRunning(true);

        try {
            // Use EventSource for SSE progress updates
            const response = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/matchup-lab/crucible-sim', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    home_team: homeTeam,
                    away_team: awayTeam,
                    num_simulations: numGames
                })
            });

            if (!response.ok) {
                throw new Error(`Simulation failed: ${response.statusText}`);
            }

            // Handle streaming response
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (reader) {
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));

                                if (data.type === 'progress') {
                                    setProgress({
                                        percent: data.percent,
                                        message: data.message,
                                        step: data.step
                                    });
                                } else if (data.type === 'complete') {
                                    setResults(data.results);
                                    setProgress({ percent: 100, message: 'Complete!', step: 'done' });
                                }
                            } catch (e) {
                                console.warn('[Crucible] Parse error:', e);
                            }
                        }
                    }
                }
            } else {
                // Fallback: non-streaming response
                const data = await response.json();
                setResults(data);
            }

        } catch (err) {
            setError(err as Error);
            console.error('[Crucible] Simulation error:', err);
        } finally {
            setIsRunning(false);
        }
    }, [reset]);

    return {
        runSimulation,
        progress,
        results,
        isRunning,
        error,
        reset
    };
}

export default useCrucibleSimulation;
