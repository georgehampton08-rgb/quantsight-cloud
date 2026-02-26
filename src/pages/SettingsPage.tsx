import { useState } from 'react';
import { Settings, Info } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { PlayerApi } from '../services/playerApi';
import { VanguardHealthWidget } from '../components/vanguard/VanguardHealthWidget';
import { HealthDepsPanel } from '../components/settings/HealthDepsPanel';

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
        <div className="h-full overflow-y-auto p-4 sm:p-6 bg-slate-900 text-white font-sans">
            <div className="max-w-4xl mx-auto space-y-6 sm:space-y-8">

                {/* Header row with badge */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-6 sm:mb-8 mt-2">
                    <div>
                        <h2 className="text-2xl font-semibold mb-1 tracking-wide">Control Room</h2>
                        <p className="text-sm text-slate-400">System configuration and cloud parameters.</p>
                    </div>
                    <div className="self-start px-3 py-1.5 border border-emerald-500/50 rounded-md bg-transparent">
                        <span className="text-emerald-400 text-xs font-bold tracking-widest uppercase">
                            CLOUD TWIN V4.1.2
                        </span>
                    </div>
                </div>

                {/* Vanguard Health Dashboard Replacement */}
                <VanguardHealthWidget />

                {/* Health Dependencies Panel */}
                <HealthDepsPanel />

                {/* AI Configuration - Styled like target image */}
                <section className="p-6 rounded-xl border border-slate-700/50 bg-[#121b2d]">
                    <h3 className="text-xs tracking-widest text-[#2ad8a0] font-bold mb-5 uppercase">AI Configuration</h3>
                    <div className="flex items-center gap-4 p-4 rounded-lg bg-[#1a253a] border border-slate-700/30">
                        <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg bg-[#2ad8a0]/10 border border-[#2ad8a0]/30 shadow-inner">
                            <Settings className="w-6 h-6 text-[#2ad8a0]" />
                        </div>
                        <div className="flex-1">
                            <h4 className="text-[15px] font-bold text-white mb-1">Coming Soon</h4>
                            <p className="text-[13px] text-slate-300">
                                AI configuration is server-side. Per-user API keys available when auth is implemented.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Data Integration - Styled like target image */}
                <section className="p-6 rounded-xl border border-[#1e3a8a]/50 bg-[#0d162f]">
                    <h3 className="text-xs tracking-widest text-[#60a5fa] font-bold mb-5 uppercase">Data Integration</h3>
                    <div className="flex items-center gap-4 p-4 rounded-lg bg-[#14203b] border border-[#1e40af]/30">
                        <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg bg-[#3b82f6]/10 border border-[#3b82f6]/30 shadow-inner">
                            <Info className="w-6 h-6 text-[#60a5fa]" />
                        </div>
                        <div className="flex-1">
                            <h4 className="text-[15px] font-bold text-white mb-1">Coming Soon</h4>
                            <p className="text-[13px] text-slate-300">
                                Kaggle integration planned. Data sourced from NBA APIs via Cloud VPC.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Data Management Bottom Zone (Not in view of user screenshot but nice to keep) */}
                <section className="p-6 rounded-xl border border-red-900/30 bg-red-900/5 mt-10">
                    <h3 className="text-xs uppercase tracking-wider text-red-500 font-bold mb-5">Danger Zone</h3>
                    <button
                        onClick={handlePurge}
                        className="px-4 py-2 bg-red-500/10 border border-red-500/30 text-red-500 rounded-md hover:bg-red-500/20 transition-colors text-xs font-bold uppercase tracking-wider"
                    >
                        Reset Database Cache
                    </button>
                </section>

            </div>
        </div>
    );
}
