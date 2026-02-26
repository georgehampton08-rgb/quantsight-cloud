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
                }
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
                mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
            },
        },
    },
    plugins: [],
}
