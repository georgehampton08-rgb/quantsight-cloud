import { clsx } from 'clsx';
import { Coffee, Zap, Timer } from 'lucide-react';

interface FatigueBreakdownChipProps {
    isB2B: boolean;
    daysRest: number;
    modifier: number;
}

export default function FatigueBreakdownChip({
    isB2B,
    daysRest,
    modifier
}: FatigueBreakdownChipProps) {
    let statusColor = 'bg-slate-700 text-slate-300';
    let label = 'Standard';
    let Icon = Timer;

    if (isB2B) {
        statusColor = 'bg-rose-500/20 text-rose-400 border-rose-500/30';
        label = 'Back-to-Back';
        Icon = Timer;
    } else if (daysRest >= 3) {
        statusColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
        label = 'Well Rested';
        Icon = Zap;
    } else {
        statusColor = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
        label = `${daysRest} Days Rest`;
        Icon = Coffee;
    }

    const modSign = modifier >= 0 ? '+' : '';

    return (
        <div className={clsx(
            "flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-semibold backdrop-blur-sm transition-all hover:scale-105",
            statusColor
        )}>
            <Icon size={14} />
            <span>{label}</span>
            <span className="opacity-60 ml-1">({modSign}{Math.round(modifier * 100)}%)</span>
        </div>
    );
}
