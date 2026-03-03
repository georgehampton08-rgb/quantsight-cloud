import { useState, useEffect } from 'react';
import { Settings, Info, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { PlayerApi } from '../services/playerApi';
import { VanguardHealthWidget } from '../components/vanguard/VanguardHealthWidget';
import { HealthDepsPanel } from '../components/settings/HealthDepsPanel';
import { ConfirmDialog } from '../components/common/ConfirmDialog';

interface KeyStatus {
    gemini_configured: boolean;
    kaggle: string;
}

export default function SettingsPage() {
    const { showToast } = useToast();

    const [showPurgeConfirm, setShowPurgeConfirm] = useState(false);
    const [keyStatus, setKeyStatus] = useState<KeyStatus | null>(null);
    const [keyStatusLoading, setKeyStatusLoading] = useState(true);

    // Load key status on mount
    useEffect(() => {
        PlayerApi.getKeyStatus()
            .then((data: any) => {
                setKeyStatus(data);
                setKeyStatusLoading(false);
            })
            .catch(() => {
                setKeyStatus(null);
                setKeyStatusLoading(false);
            });
    }, []);

    const refreshKeyStatus = () => {
        setKeyStatusLoading(true);
        PlayerApi.getKeyStatus()
            .then((data: any) => {
                setKeyStatus(data);
                setKeyStatusLoading(false);
            })
            .catch(() => {
                setKeyStatus(null);
                setKeyStatusLoading(false);
            });
    };

    const handlePurge = async () => {
        setShowPurgeConfirm(true);
    };

    const confirmPurge = async () => {
        showToast("Purge Initiated...", "info");
        try {
            const res: any = await PlayerApi.purgeDb();
            showToast(res?.message ?? "Cache purged successfully.", "success");
        } catch (e: any) {
            showToast(e?.message ?? "Purge Failed.", "error");
        }
    };

    return (
        <div className="h-full w-full overflow-y-auto bg-slate-900 border-x border-slate-800 flex flex-col items-center">
            <div className="w-full max-w-4xl p-4 sm:p-8 flex-none space-y-6 sm:space-y-8">

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

                {/* Vanguard Health Dashboard */}
                <VanguardHealthWidget />

                {/* Health Dependencies Panel */}
                <HealthDepsPanel />

                {/* AI Configuration — Live status */}
                <section className="p-6 rounded-xl border border-slate-700/50 bg-[#121b2d]">
                    <div className="flex items-center justify-between mb-5">
                        <h3 className="text-xs tracking-widest text-[#2ad8a0] font-bold uppercase">AI Configuration</h3>
                        <button
                            onClick={refreshKeyStatus}
                            disabled={keyStatusLoading}
                            className="text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40"
                            title="Refresh key status"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 ${keyStatusLoading ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                    <div className="flex items-center gap-4 p-4 rounded-lg bg-[#1a253a] border border-slate-700/30">
                        <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg bg-[#2ad8a0]/10 border border-[#2ad8a0]/30 shadow-inner">
                            <Settings className="w-6 h-6 text-[#2ad8a0]" />
                        </div>
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <h4 className="text-[15px] font-bold text-white">Gemini AI</h4>
                                {keyStatusLoading ? (
                                    <span className="text-slate-500 text-xs">Checking...</span>
                                ) : keyStatus?.gemini_configured ? (
                                    <span className="flex items-center gap-1 text-emerald-400 text-xs font-semibold">
                                        <CheckCircle className="w-3 h-3" /> Configured
                                    </span>
                                ) : (
                                    <span className="flex items-center gap-1 text-red-400 text-xs font-semibold">
                                        <XCircle className="w-3 h-3" /> Not configured
                                    </span>
                                )}
                            </div>
                            <p className="text-[13px] text-slate-400">
                                Keys are server-managed via Cloud Run environment variables. Contact system owner to update.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Data Integration — Accurate Kaggle status */}
                <section className="p-6 rounded-xl border border-[#1e3a8a]/50 bg-[#0d162f]">
                    <h3 className="text-xs tracking-widest text-[#60a5fa] font-bold mb-5 uppercase">Data Integration</h3>
                    <div className="flex items-center gap-4 p-4 rounded-lg bg-[#14203b] border border-[#1e40af]/30">
                        <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg bg-[#3b82f6]/10 border border-[#3b82f6]/30 shadow-inner">
                            <Info className="w-6 h-6 text-[#60a5fa]" />
                        </div>
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <h4 className="text-[15px] font-bold text-white">Kaggle</h4>
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30 uppercase tracking-wider">
                                    Server-Managed
                                </span>
                            </div>
                            <p className="text-[13px] text-slate-400">
                                Kaggle datasets are processed server-side via Cloud Run. No client-side key entry required.
                                Contact system owner for data sync requests.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Danger Zone */}
                <section className="p-6 rounded-xl border border-red-900/30 bg-red-900/5 mt-10">
                    <h3 className="text-xs uppercase tracking-wider text-red-500 font-bold mb-5">Danger Zone</h3>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-semibold text-white">Reset Database Cache</p>
                            <p className="text-xs text-slate-500 mt-0.5">Clears in-memory rate limiter and API caches. Does not affect Firestore data.</p>
                        </div>
                        <button
                            onClick={handlePurge}
                            className="px-4 py-2 bg-red-500/10 border border-red-500/30 text-red-500 rounded-md hover:bg-red-500/20 transition-colors text-xs font-bold uppercase tracking-wider whitespace-nowrap ml-4"
                        >
                            Purge Cache
                        </button>
                    </div>
                </section>

                <ConfirmDialog
                    isOpen={showPurgeConfirm}
                    onClose={() => setShowPurgeConfirm(false)}
                    onConfirm={confirmPurge}
                    title="Purge Server Cache?"
                    description="This will clear in-memory rate limiter buckets and API response caches. Firestore data is NOT affected. The system will continue operating normally."
                    confirmText="Purge Cache"
                    variant="danger"
                />

            </div>
        </div>
    );
}
