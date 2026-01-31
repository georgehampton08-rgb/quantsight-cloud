import { useState } from 'react';
import { useToast } from '../context/ToastContext';
import { PlayerApi } from '../services/playerApi';
import AegisHealthDashboard from '../components/aegis/AegisHealthDashboard';

export default function SettingsPage() {
    const [apiKey, setApiKey] = useState('**********************');

    // Kaggle State
    const [kaggleUser, setKaggleUser] = useState('');
    const [kaggleKey, setKaggleKey] = useState('');

    const [isVerifying, setIsVerifying] = useState(false);
    const [isSyncing, setIsSyncing] = useState(false);

    const { showToast } = useToast();

    const handleSave = async () => {
        setIsVerifying(true);
        showToast("Initiating Handshake...", "info");
        try {
            const res = await PlayerApi.saveKeys(apiKey);
            if (res.status === 'success') {
                showToast(res.message, "success");
            } else {
                showToast(res.message, "error");
            }
        } catch (e) {
            showToast("Network Link Failed.", "error");
        } finally {
            setIsVerifying(false);
        }
    };

    const handleSaveKaggle = async () => {
        if (!kaggleUser || !kaggleKey) {
            showToast("Missing Credentials.", "error");
            return;
        }
        try {
            const res = await PlayerApi.saveKaggleKeys(kaggleUser, kaggleKey);
            showToast(res.message, "success");
        } catch (e) {
            showToast("Failed to save credentials.", "error");
        }
    };

    const handleSyncKaggle = async () => {
        setIsSyncing(true);
        showToast("Requesting Dataset Pull...", "info");
        try {
            const res = await PlayerApi.syncKaggle();
            if (res.status === 'success') {
                showToast("Download Complete!", "success");
            } else {
                showToast(`Sync Failed: ${res.message}`, "error");
            }
        } catch (e) {
            showToast("Sync Network Error.", "error");
        } finally {
            setIsSyncing(false);
        }
    };

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

                {/* Key Vault */}
                <section className="p-6 rounded-xl border border-slate-700/50 bg-slate-800/30">
                    <h3 className="text-xs uppercase tracking-wider text-financial-accent font-bold mb-4">Secure Key Vault</h3>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs text-slate-500 mb-1">GEMINI_API_KEY</label>
                            <input
                                type="password"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 focus:border-financial-accent focus:ring-1 focus:ring-financial-accent outline-none font-mono"
                            />
                        </div>
                        <button
                            onClick={handleSave}
                            disabled={isVerifying}
                            className={`px-4 py-2 border rounded transition-colors text-xs font-bold uppercase tracking-wider flex items-center gap-2
                            ${isVerifying
                                    ? 'bg-slate-800 border-slate-600 text-slate-400 cursor-wait'
                                    : 'bg-financial-accent/10 border-financial-accent/30 text-financial-accent hover:bg-financial-accent/20'
                                }
                        `}
                        >
                            {isVerifying ? (
                                <>
                                    <span className="animate-spin h-3 w-3 border-2 border-slate-400 border-t-transparent rounded-full"></span>
                                    Verifying Protocol...
                                </>
                            ) : (
                                "Save & Verify Keys"
                            )}
                        </button>
                    </div>
                </section>

                {/* Kaggle Link */}
                <section className="p-6 rounded-xl border border-blue-700/30 bg-blue-900/10">
                    <h3 className="text-xs uppercase tracking-wider text-blue-400 font-bold mb-4">Kaggle Data Link</h3>

                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">Username</label>
                                <input
                                    type="text"
                                    placeholder="kaggle_user"
                                    value={kaggleUser}
                                    onChange={(e) => setKaggleUser(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-slate-500 mb-1">API Key</label>
                                <input
                                    type="password"
                                    placeholder="••••••••••••"
                                    value={kaggleKey}
                                    onChange={(e) => setKaggleKey(e.target.value)}
                                    className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-sm text-slate-200 outline-none"
                                />
                            </div>
                        </div>

                        <div className="flex gap-4">
                            <button
                                onClick={handleSaveKaggle}
                                className="px-4 py-2 border border-blue-500/30 text-blue-400 rounded hover:bg-blue-500/10 text-xs font-bold uppercase tracking-wider transition-colors"
                            >
                                Save Credentials
                            </button>
                            <button
                                onClick={handleSyncKaggle}
                                disabled={isSyncing}
                                className={`px-4 py-2 rounded text-xs font-bold uppercase tracking-wider transition-colors flex items-center gap-2
                                ${isSyncing
                                        ? 'bg-blue-900 text-blue-400 cursor-wait'
                                        : 'bg-blue-600 text-white hover:bg-blue-500'}
                            `}
                            >
                                {isSyncing ? 'Downloading...' : 'Download Latest Dataset'}
                            </button>
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
