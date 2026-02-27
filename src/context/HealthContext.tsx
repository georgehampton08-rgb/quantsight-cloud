import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { SystemStatus } from '../components/common/StatusLed';

interface HealthState {
    nba: SystemStatus;
    gemini: SystemStatus;
    database: SystemStatus;
}

interface HealthContextType {
    health: HealthState;
    checkHealth: () => Promise<void>;
}

const HealthContext = createContext<HealthContextType | undefined>(undefined);



export const HealthProvider = ({ children }: { children: ReactNode }) => {
    const [health, setHealth] = useState<HealthState>({
        nba: 'warning', // Initial state
        gemini: 'warning',
        database: 'warning'
    });

    const checkHealth = async () => {
        try {
            const API_BASE = import.meta.env.VITE_API_URL || 'https://quantsight-cloud-458498663186.us-central1.run.app';

            // Measure API latency
            const startTime = performance.now();
            const response = await fetch(`${API_BASE}/health`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            const latency = performance.now() - startTime;

            if (!response.ok) {
                throw new Error(`Health check failed: ${response.status}`);
            }

            const data = await response.json();

            // Determine status based on latency and response
            const getLatencyStatus = (ms: number): SystemStatus => {
                if (ms < 1500) return 'healthy';      // Good: < 1500ms
                if (ms < 3000) return 'warning';      // OK: 1500-3000ms
                return 'critical';                    // Bad: > 3000ms
            };

            const getLatencyOverride = (backendStatus: SystemStatus, ms: number): SystemStatus => {
                // If backend is already warning/critical, keep it
                if (backendStatus !== 'healthy') return backendStatus;
                // Otherwise only downgrade if latency is bad
                if (ms > 3000) return 'warning';
                return 'healthy';
            };

            setHealth({
                nba: getLatencyOverride(data.nba_api as SystemStatus || 'warning', latency),
                gemini: data.gemini as SystemStatus || 'warning',
                database: getLatencyOverride(data.database as SystemStatus || 'critical', latency)
            });

        } catch (error) {
            console.error("Health check failed:", error);
            setHealth({ nba: 'critical', gemini: 'critical', database: 'critical' });
        }
    };

    // Poll every 30s
    useEffect(() => {
        checkHealth(); // Initial check
        const interval = setInterval(checkHealth, 30000);
        return () => clearInterval(interval);
    }, []);

    return (
        <HealthContext.Provider value={{ health, checkHealth }}>
            {children}
        </HealthContext.Provider>
    );
};

export const useHealth = () => {
    const context = useContext(HealthContext);
    if (!context) throw new Error("useHealth must be used within a HealthProvider");
    return context;
};
