import { createContext, useContext, useState, ReactNode } from 'react';

interface ProgressState {
    isActive: boolean;
    message: string;
    progress: number; // 0-100 (visual only mostly)
    error?: string;
}

interface ProgressContextType {
    state: ProgressState;
    startProcess: (message: string) => void;
    updateMessage: (message: string) => void;
    complete: () => void;
    fail: (error: string) => void;
}

const ProgressContext = createContext<ProgressContextType | undefined>(undefined);

export const ProgressProvider = ({ children }: { children: ReactNode }) => {
    const [state, setState] = useState<ProgressState>({
        isActive: false,
        message: '',
        progress: 0,
    });

    const startProcess = (message: string) => {
        setState({ isActive: true, message, progress: 10 }); // Start at 10%
    };

    const updateMessage = (message: string) => {
        // Increment visual progress randomly for "aliveness" or logic
        setState(prev => ({
            ...prev,
            message,
            progress: Math.min(prev.progress + 20, 90) // Cap at 90 until complete
        }));
    };

    const complete = () => {
        setState(prev => ({ ...prev, progress: 100 }));
        setTimeout(() => {
            setState({ isActive: false, message: '', progress: 0 });
        }, 800);
    };

    const fail = (error: string) => {
        setState(prev => ({ ...prev, error }));
        // Stick around to show error
    };

    return (
        <ProgressContext.Provider value={{ state, startProcess, updateMessage, complete, fail }}>
            {children}
        </ProgressContext.Provider>
    );
};

export const useProgress = () => {
    const context = useContext(ProgressContext);
    if (!context) throw new Error("useProgress must be used within a ProgressProvider");
    return context;
};
