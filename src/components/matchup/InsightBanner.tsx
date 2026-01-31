import { twMerge } from 'tailwind-merge';
import { AlertTriangle, CheckCircle, Info } from 'lucide-react';

interface InsightBannerProps {
    text: string;
    type: 'success' | 'warning' | 'neutral';
}

export default function InsightBanner({ text, type }: InsightBannerProps) {
    const getStyles = () => {
        switch (type) {
            case 'success': return 'border-emerald-500/30 bg-emerald-900/20 text-emerald-300';
            case 'warning': return 'border-yellow-500/30 bg-yellow-900/20 text-yellow-300';
            default: return 'border-slate-500/30 bg-slate-800/50 text-slate-300';
        }
    };

    const getIcon = () => {
        switch (type) {
            case 'success': return <CheckCircle size={16} />;
            case 'warning': return <AlertTriangle size={16} />;
            default: return <Info size={16} />;
        }
    };

    return (
        <div className={twMerge(
            "flex items-center gap-3 p-3 rounded-md border backdrop-blur-sm mb-4 animate-in slide-in-from-top-2 duration-500",
            getStyles()
        )}>
            <div className="shrink-0">{getIcon()}</div>
            <div className="text-sm font-medium tracking-wide">
                <span className="opacity-70 text-xs uppercase mr-2 font-bold tracking-widest">Aegis Insight:</span>
                {text}
            </div>
        </div>
    );
}
