/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{ts,tsx}'],
    theme: {
        extend: {
            colors: {
                base: '#05080F',
                surface: '#0D1321',
                raised: '#131C2E',
                card: '#18243A',
                border: 'rgba(255,255,255,0.07)',
                accent: '#3D7BFF',
                purple: '#7C3AED',
                win: '#10B981',
                loss: '#EF4444',
                pending: '#F59E0B',
                live: '#F43F5E',
                muted: '#4A567A',
                dim: '#8896B3',
                bright: '#C9D6F0',
            },
            fontFamily: {
                sans: ['"Inter"', 'system-ui', 'sans-serif'],
                mono: ['"JetBrains Mono"', 'monospace'],
                display: ['"Outfit"', 'system-ui', 'sans-serif'],
            },
            boxShadow: {
                card: '0 1px 3px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.04)',
                glow: '0 0 20px rgba(61,123,255,.25)',
                inner: 'inset 0 1px 0 rgba(255,255,255,.06)',
            },
        },
    },
    plugins: [],
};
