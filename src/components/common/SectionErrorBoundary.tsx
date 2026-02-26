import React from 'react';

interface ErrorBoundaryProps {
    children: React.ReactNode;
    fallbackMessage?: string;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

export class SectionErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error("SectionErrorBoundary caught an error:", error, errorInfo);
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="p-6 rounded-xl border border-slate-700/50 bg-slate-800/20 text-center">
                    <div className="text-3xl mb-3">⚠️</div>
                    <div className="text-slate-300 font-bold mb-2">
                        {this.props.fallbackMessage || "This section failed to load"}
                    </div>
                    <div className="text-xs text-slate-500 font-mono mb-4 break-words">
                        {this.state.error?.message || "Unknown error"}
                    </div>
                    <button
                        onClick={this.handleRetry}
                        className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-sm transition-colors border border-slate-700"
                    >
                        Retry
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
