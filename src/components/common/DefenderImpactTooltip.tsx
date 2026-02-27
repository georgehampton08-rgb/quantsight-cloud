import { useState } from 'react';
import { Shield, ShieldAlert, ShieldCheck } from 'lucide-react';
import { clsx } from 'clsx';
import { Modal } from './Modal';

interface DefenderImpactTooltipProps {
    defenderName: string;
    dfgPct: number;
    pctPlusminus: number;
    children: React.ReactNode;
}

export default function DefenderImpactTooltip({
    defenderName,
    dfgPct,
    pctPlusminus,
    children
}: DefenderImpactTooltipProps) {
    const [isVisible, setIsVisible] = useState(false);

    // Delta < -3 -> Elite Defender (ShieldCheck, Green)
    // Delta < 0 -> Above Avg (Shield, Blue)
    // Delta > 3 -> Weak Defender (ShieldAlert, Red)
    let statusColor = 'text-slate-400';
    let statusBg = 'bg-slate-800';
    let label = 'Average Defender';
    let Icon = Shield;

    if (pctPlusminus <= -3) {
        statusColor = 'text-emerald-400';
        statusBg = 'bg-emerald-500/10';
        label = 'Lockdown Defender';
        Icon = ShieldCheck;
    } else if (pctPlusminus < 0) {
        statusColor = 'text-blue-400';
        statusBg = 'bg-blue-500/10';
        label = 'Above Average';
        Icon = Shield;
    } else if (pctPlusminus >= 3) {
        statusColor = 'text-rose-400';
        statusBg = 'bg-rose-500/10';
        label = 'Exploitable Matchup';
        Icon = ShieldAlert;
    }

    return (
        <span
            className="relative inline-flex items-center cursor-pointer"
            onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsVisible(!isVisible);
            }}
        >
            {children}

            <Modal
                isOpen={isVisible}
                onClose={() => setIsVisible(false)}
                title="Defender Impact"
                maxWidth="sm"
            >
                <div className="flex flex-col text-left">
                    <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-700/50">
                        <div className={clsx("p-3 rounded-xl border", statusBg, statusColor)}>
                            <Icon size={24} />
                        </div>
                        <div>
                            <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-1">Primary Defender</div>
                            <div className="text-lg font-bold text-slate-100">{defenderName}</div>
                        </div>
                    </div>

                    <div className="space-y-4 px-2">
                        <div className="flex justify-between items-center text-sm">
                            <span className="text-slate-400 font-medium">Impact Rating</span>
                            <span className={clsx("font-bold px-3 py-1 bg-slate-800 rounded-md border border-slate-700", statusColor)}>{label}</span>
                        </div>
                        <div className="flex justify-between items-center text-base font-mono bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                            <span className="text-slate-400 text-sm font-sans font-medium">DFG%</span>
                            <span className="text-slate-200 font-bold">{dfgPct.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between items-center text-base font-mono bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                            <span className="text-slate-400 text-sm font-sans font-medium">DFG% vs Avg</span>
                            <span className={clsx("font-bold", pctPlusminus <= 0 ? "text-emerald-400" : "text-rose-400")}>
                                {pctPlusminus > 0 ? '+' : ''}{pctPlusminus.toFixed(1)}%
                            </span>
                        </div>
                    </div>

                    <div className="mt-8 p-4 bg-slate-800/30 rounded-xl border border-slate-700/30 text-xs text-slate-500 italic leading-relaxed text-center">
                        <Shield className="w-4 h-4 mx-auto mb-2 opacity-50" />
                        Individual defensive field goal percentage tracking applied to simulation physics.
                    </div>
                </div>
            </Modal>
        </span>
    );
}
