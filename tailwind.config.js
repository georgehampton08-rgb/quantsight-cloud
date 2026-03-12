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
                // Terminal Cyber-Sports base tokens
                cyber: {
                    bg:      '#060910',   // void black — page background
                    surface: '#0d1117',   // panel surface
                    border:  '#1a2332',   // structural borders
                    green:   '#00ff88',   // neon signal green — live state only
                    gold:    '#ffd000',   // high-alert gold — close games, warnings
                    red:     '#ff2d55',   // kill red — errors, disconnected
                    blue:    '#00b4ff',   // electric blue — interactive highlights
                    text:    '#c8d6e8',   // primary readable text
                    muted:   '#4a6070',   // suppressed labels
                }
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
                mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
                display: ['Rajdhani', 'Inter', 'system-ui', 'sans-serif'],
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
