/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                financial: {
                    bg: '#0b1120',      // Deep midnight — richer than before
                    accent: '#00e5a0',  // Electric green — sports energy
                    text: '#94a3b8',    // Clean slate
                    light: '#e2e8f0',   // High contrast light
                },
                // Sports-forward accent scale
                qs: {
                    green: '#00e5a0',
                    blue: '#3b82f6',
                    cyan: '#22d3ee',
                    gold: '#f59e0b',
                    red: '#ef4444',
                    purple: '#a78bfa',
                },
                // High-End Professional UI base tokens (Zinc based dark mode)
                pro: {
                    bg:      '#09090b',   // zinc-950
                    surface: '#18181b',   // zinc-900
                    border:  '#27272a',   // zinc-800
                    primary: '#3b82f6',   // blue-500
                    success: '#10b981',   // emerald-500
                    warning: '#f59e0b',   // amber-500
                    danger:  '#ef4444',   // red-500
                    text:    '#fafafa',   // zinc-50
                    muted:   '#a1a1aa',   // zinc-400
                    highlight: '#3f3f46', // zinc-700
                }
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
                mono: ['JetBrains Mono', 'Fira Code', 'SFMono-Regular', 'monospace'],
                display: ['Inter', 'system-ui', 'sans-serif'], // Dropping Rajdhani for professional Inter
            },
            keyframes: {
                'scan-line': {
                    '0%': { transform: 'translateY(-100%)' },
                    '100%': { transform: 'translateY(100vh)' }
                },
                'signal-pulse': {
                    '0%, 100%': { boxShadow: '0 0 0 0 rgba(0,255,136,0)' },
                    '50%': { boxShadow: '0 0 10px 4px rgba(0,255,136,0.4)' }
                },
                'data-flicker': {
                    '0%, 100%': { opacity: '1' },
                    '40%': { opacity: '0.85' },
                    '60%': { opacity: '0.95' }
                },
                'stagger-reveal': {
                    '0%': { transform: 'translateY(8px)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' }
                }
            },
            animation: {
                'scan-line': 'scan-line 4s linear infinite',
                'signal-pulse': 'signal-pulse 2s ease-in-out infinite',
                'data-flicker': 'data-flicker 3s ease-in-out infinite',
                'stagger-reveal': 'stagger-reveal 0.2s cubic-bezier(0.2,0,0,1) forwards'
            }
        },
    },
    plugins: [],
}
