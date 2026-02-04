import { motion } from 'framer-motion';

interface ProbabilityGaugeProps {
    hitProbability: number;
    impliedOdds: number;
}

export default function ProbabilityGauge({ hitProbability, impliedOdds }: ProbabilityGaugeProps) {
    return (
        <div className="p-6 rounded-xl border border-slate-700/50 bg-slate-800/40 backdrop-blur-md">
            <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-6">Probability Matrix</h3>

            <div className="space-y-6">
                {/* Hit Probability */}
                <div>
                    <div className="flex justify-between text-sm mb-2">
                        <span className="text-slate-300">Model Probability</span>
                        <span className="font-bold text-financial-accent">{hitProbability}%</span>
                    </div>
                    <div className="h-3 bg-slate-700/50 rounded-full overflow-hidden">
                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${hitProbability}%` }}
                            transition={{ duration: 1, ease: 'easeOut' }}
                            className="h-full bg-gradient-to-r from-emerald-500 to-financial-accent rounded-full"
                        />
                    </div>
                </div>

                {/* Implied Odds */}
                <div>
                    <div className="flex justify-between text-sm mb-2">
                        <span className="text-slate-300">Implied Odds</span>
                        <span className="font-bold text-slate-400">{impliedOdds}%</span>
                    </div>
                    <div className="h-3 bg-slate-700/50 rounded-full overflow-hidden relative">
                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${impliedOdds}%` }}
                            transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
                            className="h-full bg-slate-500 rounded-full"
                        />
                        {/* Edge Indicator */}
                        {hitProbability > impliedOdds && (
                            <div
                                className="absolute top-0 bottom-0 bg-emerald-500/30 border-l border-emerald-400 dashed"
                                style={{ left: `${impliedOdds}%`, width: `${hitProbability - impliedOdds}%` }}
                            >
                                <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] text-emerald-400 font-bold">
                                    +{(hitProbability - impliedOdds).toFixed(1)}% EDGE
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
