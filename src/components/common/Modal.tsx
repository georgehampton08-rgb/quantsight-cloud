import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: React.ReactNode;
    children: React.ReactNode;
    icon?: React.ReactNode;
    /** Whether it should render as a full-screen drawer/bottom sheet on mobile */
    mobileBottomSheet?: boolean;
    maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl' | '6xl' | '7xl' | 'full';
    className?: string;
    bodyClassName?: string;
}

const maxWidthMap = {
    'sm': 'sm:max-w-sm',
    'md': 'sm:max-w-md',
    'lg': 'sm:max-w-lg',
    'xl': 'sm:max-w-xl',
    '2xl': 'sm:max-w-2xl',
    '3xl': 'sm:max-w-3xl',
    '4xl': 'sm:max-w-4xl',
    '5xl': 'sm:max-w-5xl',
    '6xl': 'sm:max-w-6xl',
    '7xl': 'sm:max-w-7xl',
    'full': 'sm:max-w-full',
};

export function Modal({
    isOpen,
    onClose,
    title,
    children,
    icon,
    mobileBottomSheet = true,
    maxWidth = '2xl',
    className = '',
    bodyClassName = '',
}: ModalProps) {
    const overlayRef = useRef<HTMLDivElement>(null);

    // Prevent background scrolling when open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        return () => {
            document.body.style.overflow = '';
        };
    }, [isOpen]);

    // Handle escape key
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const handleBackdropClick = (e: React.MouseEvent) => {
        if (e.target === overlayRef.current) onClose();
    };

    return (
        <div
            ref={overlayRef}
            onClick={handleBackdropClick}
            className="fixed inset-0 z-[2000] flex items-end sm:items-center justify-center sm:p-4 transition-all duration-300"
            style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)' }}
        >
            <div
                className={`
                    w-full ${maxWidthMap[maxWidth]} bg-slate-900 border-x border-t sm:border border-slate-700/50 
                    shadow-[0_-20px_60px_rgba(0,0,0,0.5)] sm:shadow-[0_30px_100px_rgba(0,0,0,0.8)]
                    flex flex-col overflow-hidden backdrop-blur-xl
                    transition-transform duration-300 transform
                    ${mobileBottomSheet ? 'rounded-t-3xl sm:rounded-3xl max-h-[90vh]' : 'rounded-3xl max-h-[90vh] sm:max-h-[85vh] m-4 sm:m-0'}
                    ${className}
                `}
                style={{
                    animation: 'modalSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                }}
            >
                {/* ── Header ── */}
                {title && (
                    <div className="flex items-center gap-3 px-5 sm:px-6 py-4 border-b border-slate-700/50 flex-shrink-0 bg-slate-900/80">
                        {icon && (
                            <div className="w-9 h-9 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-center flex-shrink-0">
                                {icon}
                            </div>
                        )}
                        <div className="flex-1 min-w-0">
                            {typeof title === 'string' ? (
                                <h2 className="text-white font-bold text-base truncate">{title}</h2>
                            ) : title}
                        </div>
                        <button
                            onClick={onClose}
                            className="text-slate-500 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-slate-700/80 active:bg-slate-700"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                )}

                {/* ── Scrollable Body ── */}
                <div className={`flex-1 overflow-y-auto px-5 sm:px-6 py-5 ${bodyClassName}`}>
                    {children}
                </div>

                {/* Safe area padding for standard mobile bottom bounds */}
                {mobileBottomSheet && (
                    <div className="h-6 sm:hidden bg-slate-900 absolute bottom-0 w-full pointer-events-none -mb-6" />
                )}
            </div>

            <style>{`
                @keyframes modalSlideUp {
                    from { transform: translateY(100%); opacity: 0; }
                    to { transform: translateY(0); opacity: 1; }
                }
            `}</style>
        </div>
    );
}
