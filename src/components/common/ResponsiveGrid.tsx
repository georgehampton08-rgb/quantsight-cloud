interface ResponsiveGridProps {
    children: React.ReactNode;
    cols?: {
        sm?: number;
        md?: number;
        lg?: number;
        xl?: number;
    };
    gap?: string;
    className?: string;
}

export function ResponsiveGrid({
    children,
    cols = { sm: 1, md: 2, lg: 3 },
    gap = "gap-4",
    className = ""
}: ResponsiveGridProps) {
    const colClasses = [
        cols.sm ? `grid-cols-${cols.sm}` : "grid-cols-1",
        cols.md ? `md:grid-cols-${cols.md}` : "",
        cols.lg ? `lg:grid-cols-${cols.lg}` : "",
        cols.xl ? `xl:grid-cols-${cols.xl}` : "",
    ].filter(Boolean).join(" ");

    return (
        <div className={`grid ${colClasses} ${gap} ${className}`}>
            {children}
        </div>
    );
}
