import React from 'react';
import { Modal } from './Modal';
import { AlertCircle } from 'lucide-react';

interface ConfirmDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    title: string;
    description: string;
    confirmText?: string;
    cancelText?: string;
    variant?: 'danger' | 'warning' | 'info';
}

export function ConfirmDialog({
    isOpen,
    onClose,
    onConfirm,
    title,
    description,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    variant = 'danger'
}: ConfirmDialogProps) {
    const handleConfirm = () => {
        onConfirm();
        onClose();
    };

    const variantColors = {
        danger: 'bg-red-500 hover:bg-red-600 focus:ring-red-500',
        warning: 'bg-amber-500 hover:bg-amber-600 focus:ring-amber-500',
        info: 'bg-blue-500 hover:bg-blue-600 focus:ring-blue-500',
    };

    const iconColors = {
        danger: 'text-red-500 bg-red-500/10 border-red-500/20',
        warning: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
        info: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            maxWidth="sm"
            mobileBottomSheet={false}
            className="sm:rounded-xl bg-slate-900 border border-slate-700/50"
        >
            <div className="flex flex-col items-center text-center">
                <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-6 border ${iconColors[variant]}`}>
                    <AlertCircle className="w-8 h-8" />
                </div>

                <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-slate-400 mb-8">{description}</p>

                <div className="flex flex-col sm:flex-row gap-3 w-full">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2.5 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 font-semibold hover:bg-slate-700 hover:text-white transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500"
                    >
                        {cancelText}
                    </button>
                    <button
                        onClick={handleConfirm}
                        className={`flex-1 px-4 py-2.5 rounded-lg text-white font-semibold transition-colors focus:outline-none focus:ring-2 ${variantColors[variant]}`}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </Modal>
    );
}
