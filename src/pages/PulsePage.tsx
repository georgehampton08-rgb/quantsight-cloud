import React from 'react';
import './MatchupLabPage.css';

const PulsePage: React.FC = () => {
    return (
        <div className="matchup-lab-page h-full overflow-y-auto p-8">
            <header className="lab-header mb-8">
                <div className="header-content">
                    <div className="header-title">
                        <span className="lab-icon text-red-500 animate-pulse">❤️</span>
                        <h1>The Pulse</h1>
                        <span className="ai-badge bg-red-500/20 text-red-400 border border-red-500/30">
                            LIVE TELEMETRY
                        </span>
                    </div>
                </div>
            </header>

            <div className="max-w-7xl mx-auto">
                <div className="glass-card p-8 text-center">
                    <h2 className="text-2xl font-bold text-white mb-4">🚀 Coming Soon</h2>
                    <p className="text-gray-400 mb-6">
                        Live game telemetry will connect to your Cloud Run backend at:
                    </p>
                    <code className="text-sm text-green-400 bg-black/30 px-4 py-2 rounded block mb-6">
                        https://quantsight-cloud-458498663186.us-central1.run.app
                    </code>
                    <p className="text-gray-500 text-sm">
                        This page will display real-time player stats, PIE scores, and alpha metrics during live games.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default PulsePage;
