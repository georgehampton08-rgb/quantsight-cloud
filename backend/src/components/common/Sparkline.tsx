import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { clsx } from 'clsx';

interface SparklineProps {
    data: number[];
    height?: number;
    width?: number;
    color?: string;
}

export default function Sparkline({
    data,
    height = 40,
    width = 100,
    color = '#64ffda' // Default accent color
}: SparklineProps) {
    if (!data || data.length < 2) return null;

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1; // Avoid divide by zero

    // Calculate points
    const points = data.map((val, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((val - min) / range) * height; // Invert Y for SVG
        return `${x},${y}`;
    }).join(' ');

    // Trend Indicator
    const start = data[0];
    const end = data[data.length - 1];
    const isUp = end > start;
    const isFlat = end === start;

    return (
        <div className="flex flex-col items-end gap-1">
            <svg width={width} height={height} className="overflow-visible">
                {/* Gradient Definition */}
                <defs>
                    <linearGradient id="sparkGradient" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity="0.5" />
                        <stop offset="100%" stopColor={color} stopOpacity="0" />
                    </linearGradient>
                </defs>

                {/* Fill Area (Optional, skipping for clean line look, but good to have prepared) */}

                {/* Line */}
                <polyline
                    points={points}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="drop-shadow-md"
                />

                {/* End Dot */}
                {/* We can calculate the last point easily */}
            </svg>

            <div className={clsx("flex items-center text-[10px] font-bold gap-1",
                isUp ? "text-emerald-400" : isFlat ? "text-slate-400" : "text-red-400"
            )}>
                {isUp ? <TrendingUp size={12} /> : isFlat ? <Minus size={12} /> : <TrendingDown size={12} />}
                <span>{isUp ? '+' : ''}{end - start}</span>
            </div>
        </div>
    );
}
