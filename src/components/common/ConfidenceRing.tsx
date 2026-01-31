import { motion } from 'framer-motion';
import { twMerge } from 'tailwind-merge';

interface ConfidenceRingProps {
    score: number; // 0 to 100
    size?: number;
    strokeWidth?: number;
}

export default function ConfidenceRing({
    score,
    size = 60,
    strokeWidth = 6
}: ConfidenceRingProps) {
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (score / 100) * circumference;

    // Color Logic
    const getColor = (val: number) => {
        if (val >= 70) return 'text-emerald-400';
        if (val >= 40) return 'text-yellow-400';
        return 'text-red-500';
    };

    const colorClass = getColor(score);

    return (
        <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
            {/* Background Ring */}
            <svg width={size} height={size} className="transform -rotate-90">
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    fill="transparent"
                    className="text-slate-700 opacity-30"
                />
                {/* Progress Ring */}
                <motion.circle
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    fill="transparent"
                    strokeDasharray={circumference}
                    strokeLinecap="round"
                    className={twMerge("drop-shadow-[0_0_4px_rgba(0,0,0,0.5)]", colorClass)}
                />
            </svg>

            {/* Centered Text */}
            <div className={twMerge("absolute text-xs font-bold", colorClass)}>
                {score}%
            </div>
        </div>
    );
}
