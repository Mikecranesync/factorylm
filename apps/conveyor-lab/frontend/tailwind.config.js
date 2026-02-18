/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ISA-101 Industrial HMI Colors
        hmi: {
          bg: '#1a1a1a',
          panel: '#2d2d2d',
          'panel-dark': '#232323',
          'panel-light': '#3a3a3a',
          inset: '#1f1f1f',
          border: '#444444',
          // Equipment states
          off: '#4a4a4a',
          on: '#e0e0e0',
          // Text
          'text-muted': '#808080',
          'text-normal': '#b0b0b0',
          'text-active': '#ffffff',
          'text-label': '#666666',
          // Status (ISA-101)
          running: '#2d862d',
          stopped: '#4a4a4a',
          fault: '#ff0000',
          warning: '#ffd700',
          manual: '#4169e1',
          transition: '#ffd700',
          // Alarms
          'alarm-critical': '#ff0000',
          'alarm-high': '#ff8c00',
          'alarm-medium': '#ffd700',
          'alarm-low': '#00bfff',
          // Accent
          accent: '#4a90d9',
          'accent-dim': '#2a5080',
        },
        // Keep Telegram colors for fallback
        'tg-bg': 'var(--tg-theme-bg-color, #ffffff)',
        'tg-text': 'var(--tg-theme-text-color, #000000)',
        'tg-hint': 'var(--tg-theme-hint-color, #999999)',
        'tg-link': 'var(--tg-theme-link-color, #2481cc)',
        'tg-button': 'var(--tg-theme-button-color, #2481cc)',
        'tg-button-text': 'var(--tg-theme-button-text-color, #ffffff)',
        'tg-secondary-bg': 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
      },
      fontFamily: {
        mono: ['Consolas', 'Courier New', 'monospace'],
        hmi: ['Segoe UI', '-apple-system', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'lamp-pulse': 'lampPulse 0.5s ease-in-out infinite',
        'alarm-flash': 'alarmFlash 0.5s ease-in-out infinite',
        'ptt-glow': 'pttGlow 1s ease-in-out infinite',
      },
      keyframes: {
        lampPulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        alarmFlash: {
          '0%, 100%': {
            backgroundColor: '#500000',
            borderColor: '#ff0000',
          },
          '50%': {
            backgroundColor: '#800000',
            borderColor: '#ff6666',
          },
        },
        pttGlow: {
          '0%, 100%': { boxShadow: '0 2px 0 #111, 0 0 20px rgba(255,0,0,0.4)' },
          '50%': { boxShadow: '0 2px 0 #111, 0 0 40px rgba(255,0,0,0.7)' },
        },
      },
      boxShadow: {
        'hmi-panel': 'inset 1px 1px 0 rgba(255,255,255,0.05), inset -1px -1px 0 rgba(0,0,0,0.2), 2px 2px 8px rgba(0,0,0,0.3)',
        'hmi-inset': 'inset 2px 2px 4px rgba(0,0,0,0.5), inset -1px -1px 2px rgba(255,255,255,0.03)',
        'hmi-button': '0 4px 0 #1a1a1a, 0 6px 8px rgba(0,0,0,0.4)',
        'hmi-button-pressed': '0 1px 0 #1a1a1a, 0 2px 4px rgba(0,0,0,0.3)',
        'hmi-lamp-on': '0 0 15px rgba(45,134,45,0.6), 0 0 30px rgba(45,134,45,0.6)',
        'hmi-lamp-fault': '0 0 15px rgba(255,0,0,0.6), 0 0 30px rgba(255,0,0,0.6)',
      },
    },
  },
  plugins: [],
};
