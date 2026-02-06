import { AlertTriangle, Flame, Activity } from 'lucide-react';
import { clsx } from 'clsx';

interface GameModeIndicatorProps {
    blowoutPct: number;
    clutchPct: number;
}

export default function GameModeIndicator({
    blowoutPct,
    clutchPct
}: GameModeIndicatorProps) {
    // if blowoutPct > 0.3 -> "Blowout Risk" (Yellow)
    // if clutchPct > 0.4 -> "Clutch Game" (Purple/Red)

    let label = "Standard Game";
    let Icon = Activity;
    let colorClass = "bg-slate-800 text-slate-400 border-slate-700";
    let prob = "";

    if (clutchPct >= 0.4) {
        label = "Clutch Game";
        Icon = Flame;
        colorClass = "bg-purple-500/20 text-purple-400 border-purple-500/30";
        prob = `${Math.round(clutchPct * 100)}%`;
    } else if (blowoutPct >= 0.3) {
        label = "Blowout Risk";
        Icon = AlertTriangle;
        colorClass = "bg-amber-500/20 text-amber-400 border-amber-500/30";
        prob = `${Math.round(blowoutPct * 100)}%`;
    }

    return (
        <div className={clsx(
            "flex items-center gap-2 px-2 py-1 rounded-md border text-[10px] font-bold uppercase tracking-widest transition-all",
            colorClass
        )}>
            <Icon size={12} className="animate-pulse" />
            <span>{label}</span>
            {prob && <span className="opacity-60">{prob}</span>}
        </div>
    );
}
