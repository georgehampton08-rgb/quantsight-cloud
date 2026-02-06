// Basic UI Components for QuantSight Dashboard
// These replace shadcn/ui imports with simple implementations

import React from 'react';

// Card Components
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
    children: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({ className = '', children, ...props }) => (
    <div className={`rounded-lg border border-slate-700 bg-slate-800/50 ${className}`} {...props}>
        {children}
    </div>
);

export const CardHeader: React.FC<CardProps> = ({ className = '', children, ...props }) => (
    <div className={`p-4 border-b border-slate-700 ${className}`} {...props}>
        {children}
    </div>
);

export const CardTitle: React.FC<CardProps> = ({ className = '', children, ...props }) => (
    <h3 className={`text-lg font-semibold ${className}`} {...props}>
        {children}
    </h3>
);

export const CardContent: React.FC<CardProps> = ({ className = '', children, ...props }) => (
    <div className={`p-4 ${className}`} {...props}>
        {children}
    </div>
);

// Button Component
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'default' | 'outline' | 'destructive' | 'ghost';
    size?: 'default' | 'sm' | 'lg';
}

export const Button: React.FC<ButtonProps> = ({
    className = '',
    variant = 'default',
    size = 'default',
    children,
    ...props
}) => {
    const baseClasses = 'inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:opacity-50';

    const variantClasses = {
        default: 'bg-blue-600 text-white hover:bg-blue-700',
        outline: 'border border-slate-600 bg-transparent hover:bg-slate-700',
        destructive: 'bg-red-600 text-white hover:bg-red-700',
        ghost: 'bg-transparent hover:bg-slate-700',
    };

    const sizeClasses = {
        default: 'px-4 py-2',
        sm: 'px-3 py-1.5 text-sm',
        lg: 'px-6 py-3 text-lg',
    };

    return (
        <button
            className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
            {...props}
        >
            {children}
        </button>
    );
};

// Input Component
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> { }

export const Input: React.FC<InputProps> = ({ className = '', ...props }) => (
    <input
        className={`w-full px-3 py-2 rounded-md border bg-slate-900 border-slate-600 text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 ${className}`}
        {...props}
    />
);

// Label Component
interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> { }

export const Label: React.FC<LabelProps> = ({ className = '', children, ...props }) => (
    <label className={`block text-sm font-medium text-slate-300 mb-1 ${className}`} {...props}>
        {children}
    </label>
);

// Select Components
interface SelectProps {
    value?: string;
    onValueChange?: (value: string) => void;
    children: React.ReactNode;
}

export const Select: React.FC<SelectProps> = ({ value, onValueChange, children }) => {
    const [isOpen, setIsOpen] = React.useState(false);

    return (
        <div className="relative">
            {React.Children.map(children, child => {
                if (React.isValidElement(child)) {
                    return React.cloneElement(child as React.ReactElement<any>, {
                        isOpen,
                        setIsOpen,
                        value,
                        onValueChange
                    });
                }
                return child;
            })}
        </div>
    );
};

interface SelectTriggerProps extends React.HTMLAttributes<HTMLButtonElement> {
    isOpen?: boolean;
    setIsOpen?: (open: boolean) => void;
    value?: string;
}

export const SelectTrigger: React.FC<SelectTriggerProps> = ({
    className = '',
    isOpen,
    setIsOpen,
    children,
    ...props
}) => (
    <button
        type="button"
        className={`w-full px-3 py-2 rounded-md border bg-slate-900 border-slate-600 text-left flex items-center justify-between ${className}`}
        onClick={() => setIsOpen?.(!isOpen)}
        {...props}
    >
        {children}
        <span className="ml-2">▼</span>
    </button>
);

export const SelectValue: React.FC<{ placeholder?: string }> = ({ placeholder }) => (
    <span>{placeholder || 'Select...'}</span>
);

interface SelectContentProps {
    children: React.ReactNode;
    isOpen?: boolean;
    setIsOpen?: (open: boolean) => void;
    onValueChange?: (value: string) => void;
}

export const SelectContent: React.FC<SelectContentProps> = ({
    children,
    isOpen,
    setIsOpen,
    onValueChange
}) => {
    if (!isOpen) return null;

    return (
        <div className="absolute z-50 w-full mt-1 bg-slate-800 border border-slate-600 rounded-md shadow-lg">
            {React.Children.map(children, child => {
                if (React.isValidElement(child)) {
                    return React.cloneElement(child as React.ReactElement<any>, {
                        onSelect: (value: string) => {
                            onValueChange?.(value);
                            setIsOpen?.(false);
                        }
                    });
                }
                return child;
            })}
        </div>
    );
};

interface SelectItemProps {
    value: string;
    children: React.ReactNode;
    onSelect?: (value: string) => void;
}

export const SelectItem: React.FC<SelectItemProps> = ({ value, children, onSelect }) => (
    <div
        className="px-3 py-2 hover:bg-slate-700 cursor-pointer"
        onClick={() => onSelect?.(value)}
    >
        {children}
    </div>
);

// Alert Components
interface AlertProps extends React.HTMLAttributes<HTMLDivElement> { }

export const Alert: React.FC<AlertProps> = ({ className = '', children, ...props }) => (
    <div className={`p-4 rounded-md border ${className}`} {...props}>
        {children}
    </div>
);

export const AlertDescription: React.FC<AlertProps> = ({ className = '', children, ...props }) => (
    <div className={`text-sm ${className}`} {...props}>
        {children}
    </div>
);
