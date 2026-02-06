import { ReactNode } from 'react';
import { clsx } from 'clsx';

interface MetricCardProps {
    title: string;
    value: string | number;
    subValue?: string;
    icon?: ReactNode;
    children?: ReactNode; // Slot for Sparkline or Ring
    className?: string;
    trend?: 'up' | 'down' | 'neutral'; // Optional overall trend color hint
}

export default function MetricCard({
    title,
    value,
    subValue,
    icon,
    children,
    className
}: MetricCardProps) {
    return (
        <div className={clsx(
            "relative p-4 rounded-xl border border-slate-700/50 bg-slate-800/40 backdrop-blur-md overflow-hidden transition-all duration-300 hover:border-financial-accent/30 hover:bg-slate-800/60 group",
            className
        )}>
            {/* Top Shine Effect */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-slate-500/20 to-transparent opacity-50" />

            <div className="flex justify-between items-start mb-2">
                <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">{title}</h3>
                {icon && <div className="text-slate-500 group-hover:text-financial-accent transition-colors">{icon}</div>}
            </div>

            <div className="flex justify-between items-end">
                <div>
                    <div className="text-2xl font-bold text-slate-100 tabular-nums tracking-tight">
                        {value}
                    </div>
                    {subValue && (
                        <div className="text-xs text-slate-500 mt-1 font-mono">
                            {subValue}
                        </div>
                    )}
                </div>

                {/* Visualization Slot */}
                <div className="ml-4">
                    {children}
                </div>
            </div>
        </div>
    );
}
