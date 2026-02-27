import { twMerge } from 'tailwind-merge';

export type SystemStatus = 'healthy' | 'warning' | 'critical';

interface StatusLedProps {
    status: SystemStatus;
    label: string;
    className?: string;
}

export default function StatusLed({ status, label, className }: StatusLedProps) {
    const getColors = (s: SystemStatus) => {
        switch (s) {
            case 'healthy':
                return 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]';
            case 'warning':
                return 'bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)]';
            case 'critical':
                return 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]';
        }
    };

    const getAnimation = (s: SystemStatus) => {
        switch (s) {
            case 'healthy':
                return 'animate-pulse'; // Slow breathe
            case 'warning':
                return ''; // Static
            case 'critical':
                return 'animate-ping'; // Fast attention grabber (or custom flash)
        }
    };

    return (
        <div className={twMerge("flex items-center gap-1.5 sm:gap-2", className)} title={`System: ${label} is ${status}`}>
            <div className="hidden sm:flex flex-col items-end">
                <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">{label}</span>
            </div>
            <div className="relative flex h-2.5 w-2.5">
                {/* Ping animation layer for critical */}
                {status === 'critical' && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                )}
                {/* Main dot */}
                <span className={twMerge(
                    "relative inline-flex rounded-full h-2.5 w-2.5",
                    getColors(status),
                    getAnimation(status)
                )}></span>
            </div>
        </div>
    );
}
