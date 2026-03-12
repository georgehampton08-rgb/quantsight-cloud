import { useState, useEffect } from 'react';
import { Settings, Info, CheckCircle, XCircle, RefreshCw, Lock } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import { PlayerApi } from '../services/playerApi';
import { VanguardHealthWidget } from '../components/vanguard/VanguardHealthWidget';
import { HealthDepsPanel } from '../components/settings/HealthDepsPanel';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import CornerBrackets from '../components/common/CornerBrackets';

interface KeyStatus {
    gemini_configured: boolean;
    kaggle: string;
}

export default function SettingsPage() {
    const { showToast } = useToast();
    const { user } = useAuth();

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
        <div className="h-full w-full overflow-y-auto bg-cyber-bg border-x border-cyber-border flex flex-col items-center font-sans relative z-10">
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                 style={{
                   backgroundImage: 'linear-gradient(#00ff88 1px, transparent 1px), linear-gradient(90deg, #00ff88 1px, transparent 1px)',
                   backgroundSize: '32px 32px',
                 }} />
            <div className="w-full max-w-4xl p-4 sm:p-8 flex-none space-y-6 sm:space-y-8 relative z-10">

                {/* Header row with badge */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-6 sm:mb-8 mt-2">
                    <div>
                        <h2 className="text-2xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text mb-1 flex items-center gap-3">
                            <Settings className="w-6 h-6 text-cyber-blue" />
                            Control Room
                        </h2>
                        <p className="text-[10px] text-cyber-muted tracking-[0.2em] font-mono mt-2 uppercase">System configuration and cloud parameters.</p>
                    </div>
                    <div className="self-start px-3 py-1.5 border border-cyber-green/50 rounded-none bg-cyber-green/5">
                        <span className="text-cyber-green text-xs font-mono tracking-widest uppercase">
                            CLOUD TWIN V4.1.2
                        </span>
                    </div>
                </div>

                {/* Vanguard Health Dashboard */}
                <VanguardHealthWidget />

                {/* Health Dependencies Panel */}
                <HealthDepsPanel />

                {/* AI Configuration — Live status */}
                <section className="p-6 rounded-none border border-cyber-border bg-cyber-surface relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <div className="flex items-center justify-between mb-5 relative z-10">
                        <h3 className="text-[10px] tracking-[0.2em] text-cyber-gold font-display font-700 uppercase">AI Configuration</h3>
                        <button
                            onClick={refreshKeyStatus}
                            disabled={keyStatusLoading}
                            className="text-cyber-muted hover:text-cyber-text transition-colors disabled:opacity-40"
                            title="Refresh key status"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 ${keyStatusLoading ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                    <div className="flex items-center gap-4 p-4 rounded-none bg-white/[0.02] border border-cyber-border/50 relative z-10">
                        <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-none bg-cyber-gold/10 border border-cyber-gold/30">
                            <Settings className="w-6 h-6 text-cyber-gold" />
                        </div>
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <h4 className="text-sm font-display font-600 tracking-widest uppercase text-cyber-text">Gemini AI</h4>
                                {keyStatusLoading ? (
                                    <span className="text-cyber-muted font-mono text-[9px] uppercase tracking-widest">Checking...</span>
                                ) : keyStatus?.gemini_configured ? (
                                    <span className="flex items-center gap-1 text-cyber-green text-[9px] font-mono uppercase tracking-widest">
                                        <CheckCircle className="w-3 h-3" /> Configured
                                    </span>
                                ) : (
                                    <span className="flex items-center gap-1 text-cyber-red text-[9px] font-mono uppercase tracking-widest">
                                        <XCircle className="w-3 h-3" /> Not configured
                                    </span>
                                )}
                            </div>
                            <p className="text-[10px] font-mono text-cyber-muted uppercase tracking-wider">
                                Keys are server-managed via Cloud Run environment variables. Contact system owner to update.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Data Integration — Accurate Kaggle status */}
                <section className="p-6 rounded-none border border-cyber-border bg-cyber-surface relative shadow-none" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <h3 className="text-[10px] tracking-[0.2em] text-cyber-blue font-display font-700 mb-5 uppercase relative z-10">Data Integration</h3>
                    <div className="flex items-center gap-4 p-4 rounded-none bg-white/[0.02] border border-cyber-border/50 relative z-10">
                        <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-none bg-cyber-blue/10 border border-cyber-blue/30">
                            <Info className="w-6 h-6 text-cyber-blue" />
                        </div>
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <h4 className="text-sm font-display font-600 tracking-widest uppercase text-cyber-text">Kaggle</h4>
                                <span className="px-2 py-0.5 rounded-none text-[9px] font-mono bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/30 uppercase tracking-widest">
                                    Server-Managed
                                </span>
                            </div>
                            <p className="text-[10px] font-mono text-cyber-muted uppercase tracking-wider">
                                Kaggle datasets are processed server-side via Cloud Run. No client-side key entry required.
                                Contact system owner for data sync requests.
                            </p>
                        </div>
                    </div>
                </section>

                {/* Danger Zone — only shown to signed-in users (backend still enforces admin role) */}
                {user ? (
                    <section className="p-6 rounded-none border border-cyber-red/30 bg-cyber-red/5 mt-10 relative">
                        <CornerBrackets />
                        <h3 className="text-[10px] uppercase tracking-[0.2em] text-cyber-red font-display font-700 mb-5 relative z-10">Danger Zone</h3>
                        <div className="flex items-center justify-between relative z-10">
                            <div>
                                <h4 className="text-sm font-display font-600 tracking-widest uppercase text-cyber-text mb-1">Reset Database Cache</h4>
                                <p className="text-[10px] font-mono text-cyber-muted uppercase tracking-wider max-w-[200px] sm:max-w-none">Clears in-memory rate limiter and API caches. Does not affect Firestore data.</p>
                            </div>
                            <button
                                onClick={handlePurge}
                                className="px-4 py-2 bg-cyber-red/10 border border-cyber-red hover:bg-cyber-red/20 text-cyber-red rounded-none transition-colors text-xs font-display font-600 uppercase tracking-widest whitespace-nowrap ml-4"
                            >
                                Purge Cache
                            </button>
                        </div>
                    </section>
                ) : (
                    <section className="p-6 rounded-none border border-cyber-border/50 bg-cyber-surface mt-10 flex items-center justify-center gap-3 text-cyber-muted relative">
                        <Lock className="w-4 h-4 flex-shrink-0" />
                        <p className="text-[10px] font-mono uppercase tracking-widest">Administrative controls are hidden. Sign in via the Vanguard page to access them.</p>
                    </section>
                )}

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
