import React, { Component, ReactNode } from 'react';
import './ErrorBoundaryWithFallback.css';

interface Props {
    children: ReactNode;
    fallbackType?: 'default' | 'defense' | 'api' | 'data';
    onRetry?: () => void;
}

interface State {
    hasError: boolean;
    error: Error | null;
    retryCount: number;
    isRetrying: boolean;
}

const FALLBACK_MESSAGES: Record<string, { title: string; message: string; icon: string }> = {
    default: {
        title: 'Something went wrong',
        message: 'We encountered an unexpected issue. Please try again.',
        icon: '🔧'
    },
    defense: {
        title: 'Defensive data is resting',
        message: 'Using league-average constants for now. Stats may be less precise.',
        icon: '🏀'
    },
    api: {
        title: 'The engine is warming up',
        message: 'Our servers are taking a quick breather. Please try again in a moment.',
        icon: '⚡'
    },
    data: {
        title: 'Data currently unavailable',
        message: 'We\'re using cached projections. Fresh data coming soon!',
        icon: '📊'
    }
};

class ErrorBoundaryWithFallback extends Component<Props, State> {
    private retryTimeouts: NodeJS.Timeout[] = [];

    constructor(props: Props) {
        super(props);
        this.state = {
            hasError: false,
            error: null,
            retryCount: 0,
            isRetrying: false
        };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('[ErrorBoundary] Caught error:', error, errorInfo);

        // Auto-retry with exponential backoff
        this.scheduleRetry();
    }

    componentWillUnmount() {
        this.retryTimeouts.forEach(t => clearTimeout(t));
    }

    scheduleRetry = () => {
        const { retryCount } = this.state;
        const delays = [1000, 2000, 4000, 8000]; // Exponential backoff

        if (retryCount < delays.length) {
            const delay = delays[retryCount];
            console.log(`[ErrorBoundary] Auto-retry in ${delay}ms (attempt ${retryCount + 1})`);

            const timeout = setTimeout(() => {
                this.handleRetry();
            }, delay);

            this.retryTimeouts.push(timeout);
        }
    };

    handleRetry = () => {
        this.setState(prev => ({
            hasError: false,
            error: null,
            isRetrying: true,
            retryCount: prev.retryCount + 1
        }));

        setTimeout(() => {
            this.setState({ isRetrying: false });
            this.props.onRetry?.();
        }, 500);
    };

    render() {
        const { hasError, error, retryCount, isRetrying } = this.state;
        const { children, fallbackType = 'default' } = this.props;

        if (isRetrying) {
            return (
                <div className="error-boundary-fallback retrying">
                    <span className="retry-spinner" />
                    <span>Reconnecting...</span>
                </div>
            );
        }

        if (hasError) {
            const fallback = FALLBACK_MESSAGES[fallbackType];
            const canRetry = retryCount < 4;

            return (
                <div className="error-boundary-fallback">
                    <div className="fallback-icon">{fallback.icon}</div>
                    <h3 className="fallback-title">{fallback.title}</h3>
                    <p className="fallback-message">{fallback.message}</p>

                    {canRetry && (
                        <button
                            className="retry-button"
                            onClick={this.handleRetry}
                        >
                            🔄 Try Again
                        </button>
                    )}

                    {retryCount > 0 && (
                        <span className="retry-count">
                            Retry {retryCount}/4
                        </span>
                    )}

                    {process.env.NODE_ENV === 'development' && error && (
                        <details className="error-details">
                            <summary>Technical Details</summary>
                            <pre>{error.message}</pre>
                        </details>
                    )}
                </div>
            );
        }

        return children;
    }
}

export default ErrorBoundaryWithFallback;
