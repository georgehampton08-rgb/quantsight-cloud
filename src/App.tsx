import { HashRouter } from 'react-router-dom'
import { Component, ErrorInfo, ReactNode } from 'react'
import { HealthProvider } from './context/HealthContext'
import { ProgressProvider } from './context/ProgressContext'
import { ToastProvider } from './context/ToastContext'
import { OrbitalProvider } from './context/OrbitalContext'
import ProgressBar from './components/common/ProgressBar'
import ToastContainer from './components/common/ToastContainer'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import MainCanvas from './components/MainCanvas'

// Top-level error boundary
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
    constructor(props: { children: ReactNode }) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('[APP ERROR BOUNDARY]', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex items-center justify-center h-screen bg-financial-bg text-financial-text">
                    <div className="text-center p-8 max-w-md">
                        <h1 className="text-2xl font-bold mb-4 text-red-500">QuantSight Initialization Error</h1>
                        <p className="mb-4">The app encountered an error during startup.</p>
                        <p className="text-sm text-gray-400 mb-4">{this.state.error?.message}</p>
                        <button
                            onClick={() => window.location.reload()}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded"
                        >
                            Reload App
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

function App() {
    return (
        <ErrorBoundary>
            <HashRouter>
                <OrbitalProvider>
                    <HealthProvider>
                        <ProgressProvider>
                            <ToastProvider>
                                <div className="flex h-screen w-screen bg-financial-bg text-financial-text overflow-hidden relative">
                                    <ProgressBar />
                                    <ToastContainer />

                                    {/* IPC Verification / Dev Mode Tag */}
                                    <div className="fixed bottom-1 right-1 text-xs text-opacity-20 text-white pointer-events-none z-50">
                                        QS-DASH-V1
                                    </div>

                                    <Sidebar />

                                    <div className="flex flex-col flex-1 h-full relative">
                                        <TopBar />
                                        <MainCanvas />
                                    </div>
                                </div>
                            </ToastProvider>
                        </ProgressProvider>
                    </HealthProvider>
                </OrbitalProvider>
            </HashRouter>
        </ErrorBoundary>
    )
}

export default App
