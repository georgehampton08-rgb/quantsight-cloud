import { useState } from 'react';
import { Shield, ShieldAlert, ShieldCheck } from 'lucide-react';
import { clsx } from 'clsx';

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
        <div
            className="relative inline-block"
            onMouseEnter={() => setIsVisible(true)}
            onMouseLeave={() => setIsVisible(false)}
        >
            {children}

            {isVisible && (
                <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-4 rounded-xl border border-slate-700 bg-slate-900 shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-bottom-2">
                    <div className="flex items-center gap-3 mb-3 pb-3 border-b border-slate-800">
                        <div className={clsx("p-2 rounded-lg", statusBg, statusColor)}>
                            <Icon size={20} />
                        </div>
                        <div>
                            <div className="text-xs uppercase tracking-wider text-slate-500 font-bold">Primary Defender</div>
                            <div className="text-sm font-bold text-slate-100">{defenderName}</div>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <div className="flex justify-between items-center text-xs">
                            <span className="text-slate-400">Impact Rating</span>
                            <span className={clsx("font-bold", statusColor)}>{label}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm font-mono">
                            <span className="text-slate-400 text-xs font-sans">DFG%</span>
                            <span className="text-slate-200">{dfgPct.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between items-center text-sm font-mono">
                            <span className="text-slate-400 text-xs font-sans">DFG% vs Avg</span>
                            <span className={clsx(pctPlusminus <= 0 ? "text-emerald-400" : "text-rose-400")}>
                                {pctPlusminus > 0 ? '+' : ''}{pctPlusminus.toFixed(1)}%
                            </span>
                        </div>
                    </div>

                    <div className="mt-3 pt-3 border-t border-slate-800 text-[10px] text-slate-500 italic leading-relaxed">
                        Individual defensive field goal percentage tracking applied to simulation physics.
                    </div>

                    {/* Arrow */}
                    <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-8 border-transparent border-t-slate-700" />
                </div>
            )}
        </div>
    );
}
