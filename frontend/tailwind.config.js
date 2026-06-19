/**
 * tailwind.config.js — Tema visual de SmartSack alineado con la identidad
 * web de Smurfit Kappa (Bags Division): fondo claro con acentos navy/azul,
 * superficies blancas y tipografía geométrica.
 *
 *   #08B2FF  Pantone 306 C  → accent / acción / botones
 *   #00205B  Pantone 281 C  → header / texto principal / branding
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#f4f7fb',
          surface: '#ffffff',
          elevated: '#ffffff',
          line: '#dbe4ee',
          softline: '#eef2f8',
        },
        ink: {
          high: '#00205B',
          mid: '#475569',
          low: '#64748b',
          mute: '#94a3b8',
          inverse: '#f4f7fb',
        },
        accent: {
          DEFAULT: '#08B2FF',
          soft: '#0086c4',
          glow: '#0096dc',
          ink: '#00205B',
        },
        brand: {
          primary: '#00205B',
          accent: '#08B2FF',
          deep: '#001a4d',
        },
        state: {
          running: '#16a34a',
          stopped: '#dc2626',
          maintenance: '#ea580c',
          idle: '#64748b',
        },
        machine: {
          running: '#16a34a',
          stopped: '#dc2626',
          maintenance: '#ea580c',
          idle: '#64748b',
        },
      },
      fontFamily: {
        sans: ['"Space Grotesk"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: {
        widest2: '0.18em',
      },
      boxShadow: {
        'soft':         '0 1px 2px rgba(0,32,91,0.06), 0 8px 24px rgba(0,32,91,0.05)',
        'card':         '0 1px 0 rgba(255,255,255,0.6) inset, 0 1px 2px rgba(0,32,91,0.05)',
        'glow-brand':   '0 0 0 1px rgba(8,178,255,0.45),  0 0 18px rgba(8,178,255,0.18)',
        'glow-emerald': '0 0 0 1px rgba(22,163,74,0.45),  0 0 16px rgba(22,163,74,0.18)',
        'glow-rose':    '0 0 0 1px rgba(220,38,38,0.45),  0 0 16px rgba(220,38,38,0.18)',
        'glow-amber':   '0 0 0 1px rgba(234,88,12,0.45),  0 0 16px rgba(234,88,12,0.18)',
        'glow-slate':   '0 0 0 1px rgba(100,116,139,0.40),0 0 14px rgba(100,116,139,0.15)',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.55 },
        },
        'fade-in-up': {
          '0%': { opacity: 0, transform: 'translateY(6px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        'flash-emerald': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(22,163,74,0)', backgroundColor: '#ffffff' },
          '20%, 60%': { boxShadow: '0 0 0 6px rgba(22,163,74,0.45), 0 0 28px rgba(22,163,74,0.55)', backgroundColor: '#f0fdf4' },
        },
        'flash-rose': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(220,38,38,0)', backgroundColor: '#ffffff' },
          '20%, 60%': { boxShadow: '0 0 0 6px rgba(220,38,38,0.45), 0 0 28px rgba(220,38,38,0.55)', backgroundColor: '#fef2f2' },
        },
        'flash-amber': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(234,88,12,0)', backgroundColor: '#ffffff' },
          '20%, 60%': { boxShadow: '0 0 0 6px rgba(234,88,12,0.45), 0 0 28px rgba(234,88,12,0.55)', backgroundColor: '#fff7ed' },
        },
        'flash-slate': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(100,116,139,0)', backgroundColor: '#ffffff' },
          '20%, 60%': { boxShadow: '0 0 0 6px rgba(100,116,139,0.40), 0 0 24px rgba(100,116,139,0.45)', backgroundColor: '#f8fafc' },
        },
        'flash-brand': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(8,178,255,0)', backgroundColor: '#ffffff' },
          '20%, 60%': { boxShadow: '0 0 0 6px rgba(8,178,255,0.45), 0 0 28px rgba(8,178,255,0.55)', backgroundColor: '#ecf8ff' },
        },
        'beacon': {
          '0%, 100%': { transform: 'scale(1)', opacity: 1 },
          '50%': { transform: 'scale(1.18)', opacity: 0.7 },
        },
      },
      animation: {
        'pulse-soft': 'pulse-soft 1.6s ease-in-out infinite',
        'fade-in-up': 'fade-in-up 220ms ease-out',
        'beacon':     'beacon 1.4s ease-in-out infinite',
        'flash-emerald': 'flash-emerald 1.4s ease-in-out 2',
        'flash-rose':    'flash-rose 1.4s ease-in-out 2',
        'flash-amber':   'flash-amber 1.4s ease-in-out 2',
        'flash-slate':   'flash-slate 1.4s ease-in-out 2',
        'flash-brand':   'flash-brand 1.4s ease-in-out 2',
      },
    },
  },
  safelist: [
    'animate-flash-emerald',
    'animate-flash-rose',
    'animate-flash-amber',
    'animate-flash-slate',
    'animate-flash-brand',
  ],
  plugins: [],
};
