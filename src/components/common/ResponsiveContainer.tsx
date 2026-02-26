export function ResponsiveContainer({
    children,
    className = ""
}: {
    children: React.ReactNode,
    className?: string
}) {
    return (
        <div className={`
      w-full max-w-screen-xl
      mx-auto px-3 sm:px-4 md:px-6
      lg:px-8 ${className}
    `}>
            {children}
        </div>
    );
}
