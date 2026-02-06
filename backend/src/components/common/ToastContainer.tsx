import { motion, AnimatePresence } from 'framer-motion';
import { Toast, useToast } from '../../context/ToastContext';
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react';

export default function ToastContainer() {
    const { toasts, removeToast } = useToast();

    return (
        <div className="fixed bottom-6 right-6 flex flex-col gap-3 z-[60] pointer-events-none">
            <AnimatePresence>
                {toasts.map(toast => (
                    <HolographicToast key={toast.id} toast={toast} onDismiss={() => removeToast(toast.id)} />
                ))}
            </AnimatePresence>
        </div>
    );
}

function HolographicToast({ toast, onDismiss }: { toast: Toast, onDismiss: () => void }) {
    const getStyles = () => {
        switch (toast.type) {
            case 'success': return 'border-emerald-500/50 bg-emerald-900/40 text-emerald-200 shadow-[0_0_15px_rgba(16,185,129,0.3)]';
            case 'error': return 'border-red-500/50 bg-red-900/40 text-red-200 shadow-[0_0_15px_rgba(239,68,68,0.3)]';
            default: return 'border-blue-500/50 bg-blue-900/40 text-blue-200 shadow-[0_0_15px_rgba(59,130,246,0.3)]';
        }
    };

    const getIcon = () => {
        switch (toast.type) {
            case 'success': return <CheckCircle size={18} />;
            case 'error': return <AlertCircle size={18} />;
            default: return <Info size={18} />;
        }
    };

    return (
        <motion.div
            layout
            initial={{ opacity: 0, x: 100, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
            className={`
        pointer-events-auto w-80 p-4 rounded-lg border backdrop-blur-md flex items-start gap-3
        ${getStyles()}
      `}
        >
            <div className="mt-0.5 shrink-0">{getIcon()}</div>
            <div className="flex-1 text-sm font-medium leading-tight pt-0.5">{toast.message}</div>
            <button onClick={onDismiss} className="opacity-50 hover:opacity-100 transition-opacity">
                <X size={14} />
            </button>
        </motion.div>
    );
}
