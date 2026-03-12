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
            "relative p-5 bg-pro-surface transition-colors duration-100 hover:border-emerald-500 group",
            className
        )} >
            {/* Top Shine Effect */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/8 to-transparent pointer-events-none" />
            
            

            <div className="flex justify-between items-start mb-2 relative z-10">
                <h3 className="text-xs font-medium font-semibold uppercase tracking-normal text-pro-muted">{title}</h3>
                {icon && <div className="text-pro-muted group-hover:text-emerald-500 transition-colors duration-100">{icon}</div>}
            </div>

            <div className="flex justify-between items-end relative z-10">
                <div>
                    <div className="text-2xl font-mono font-bold text-pro-text tabular-nums tracking-tight group-hover:text-white transition-colors duration-100">
                        {value}
                    </div>
                    {subValue && (
                        <div className="text-xs text-pro-muted mt-1 font-mono tabular-nums tracking-tight">
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
