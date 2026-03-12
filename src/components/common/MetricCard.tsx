import { ReactNode } from 'react';
import { clsx } from 'clsx';
import CornerBrackets from './CornerBrackets';

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
            "relative p-5 bg-cyber-surface transition-colors duration-100 hover:border-cyber-green group",
            className
        )} style={{ border: '1px solid #1a2332' }}>
            {/* Top Shine Effect */}
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/8 to-transparent pointer-events-none" />
            
            <CornerBrackets />

            <div className="flex justify-between items-start mb-2 relative z-10">
                <h3 className="text-[10px] font-display font-600 uppercase tracking-[0.12em] text-cyber-muted">{title}</h3>
                {icon && <div className="text-cyber-muted group-hover:text-cyber-green transition-colors duration-100">{icon}</div>}
            </div>

            <div className="flex justify-between items-end relative z-10">
                <div>
                    <div className="text-2xl font-mono font-bold text-cyber-text tabular-nums tracking-tight group-hover:text-white transition-colors duration-100">
                        {value}
                    </div>
                    {subValue && (
                        <div className="text-[10px] text-cyber-muted mt-1 font-mono tabular-nums tracking-tight">
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
