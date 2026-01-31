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
            const result = await window.electronAPI.checkSystemHealth();
            setHealth(result);
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
