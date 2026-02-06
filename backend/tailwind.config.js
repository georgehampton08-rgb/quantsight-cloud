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
                    bg: '#0a192f',
                    accent: '#64ffda',
                    text: '#8892b0', // Slate Greyish
                    light: '#ccd6f6', // Lightest text
                }
            }
        },
    },
    plugins: [],
}
