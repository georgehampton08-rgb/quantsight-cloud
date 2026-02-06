import { useState } from 'react';
import { useToast } from '../context/ToastContext';
import { PlayerApi } from '../services/playerApi';
import AegisHealthDashboard from '../components/aegis/AegisHealthDashboard';

export default function SettingsPage() {
    const { showToast } = useToast();

    const handlePurge = async () => {
        if (confirm("WARNING: Start Database Purge Protocol? This cannot be undone.")) {
            showToast("Purge Initiated...", "info");
            try {
                const res = await PlayerApi.purgeDb();
                showToast(res.message, "success");
            } catch (e) {
                showToast("Purge Failed.", "error");
            }
        }
    };

    return (
        <div className="h-full overflow-y-auto p-4">
            <div className="max-w-2xl mx-auto space-y-8">
                <div className="mb-6">
                    <h2 className="text-2xl font-light text-white mb-2">Control Room</h2>
                    <p className="text-sm text-slate-400">Manage API keys and system parameters.</p>
                </div>

                {/* AI Configuration - Coming Soon */}
                <section className="p-6 rounded-xl border border-slate-700/50 bg-slate-800/30">
                    <h3 className="text-xs uppercase tracking-wider text-financial-accent font-bold mb-4">AI Configuration</h3>
                    <div className="flex items-start gap-4 p-4 rounded-lg bg-slate-900/50 border border-slate-700/30">
                        <div className="text-4xl">🔧</div>
                        <div className="flex-1">
                            <h4 className="text-sm font-semibold text-white mb-1">Coming Soon</h4>
                            <p className="text-xs text-slate-400 leading-relaxed">
                                AI configuration is currently managed server-side. Per-user API key configuration will be available in a future update when user authentication is implemented.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Data Integration - Coming Soon */}
                <section className="p-6 rounded-xl border border-blue-700/30 bg-blue-900/10">
                    <h3 className="text-xs uppercase tracking-wider text-blue-400 font-bold mb-4">Data Integration</h3>
                    <div className="flex items-start gap-4 p-4 rounded-lg bg-slate-900/50 border border-blue-700/20">
                        <div className="text-4xl">📊</div>
                        <div className="flex-1">
                            <h4 className="text-sm font-semibold text-white mb-1">Coming Soon</h4>
                            <p className="text-xs text-slate-400 leading-relaxed">
                                Kaggle integration and custom data sources are planned for a future release. All data is currently sourced from official NBA APIs.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Aegis System Status */}
                <AegisHealthDashboard />

                {/* Data Management */}
                <section className="p-6 rounded-xl border border-red-900/30 bg-red-900/5">
                    <h3 className="text-xs uppercase tracking-wider text-red-400 font-bold mb-4">Danger Zone</h3>
                    <button
                        onClick={handlePurge}
                        className="px-4 py-2 bg-red-500/10 border border-red-500/30 text-red-500 rounded hover:bg-red-500/20 transition-colors text-xs font-bold uppercase tracking-wider"
                    >
                        Reset Database Cache
                    </button>
                </section>
            </div>
        </div>
    );
}
