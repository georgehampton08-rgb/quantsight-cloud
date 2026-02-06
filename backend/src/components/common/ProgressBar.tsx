import { motion, AnimatePresence } from 'framer-motion';
import { useProgress } from '../../context/ProgressContext';

export default function ProgressBar() {
    const { state } = useProgress();

    return (
        <AnimatePresence>
            {state.isActive && (
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    className="absolute top-0 left-0 right-0 z-50 flex flex-col items-center pointer-events-none"
                >
                    {/* The Bar */}
                    <div className="w-full h-1 bg-slate-800">
                        <motion.div
                            className={`h-full ${state.error ? 'bg-red-500' : 'bg-gradient-to-r from-financial-accent to-emerald-400'}`}
                            animate={{ width: `${state.progress}%` }}
                            transition={{ ease: "easeInOut" }}
                        />
                    </div>

                    {/* The Label */}
                    <motion.div
                        className={`
                    mt-2 px-4 py-1.5 rounded-full text-xs font-mono font-bold backdrop-blur-md border shadow-lg
                    ${state.error
                                ? 'bg-red-900/80 border-red-500 text-red-200'
                                : 'bg-slate-900/80 border-financial-accent/30 text-financial-accent'
                            }
                `}
                        layout
                    >
                        {state.error ? `ERROR: ${state.error}` : state.message}
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
