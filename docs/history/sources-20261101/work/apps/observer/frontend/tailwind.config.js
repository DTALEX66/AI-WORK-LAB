/** @type {import('tailwindcss').Config} */
// UI_TOKENS (20260921): theme colors are CSS variables so Dark/Light actually
// invert (index.css defines the values; the numeric source of truth is
// src/theme/tokens.ts, asserted by src/theme/tokens.test.ts). The six accent
// colors use the channel form `rgb(var(--X-rgb) / <alpha-value>)` so Tailwind
// alpha modifiers (bg-success/10, border-error/20, …) resolve at runtime in
// BOTH themes. Surfaces read plain vars. Shape/depth/motion come from the
// B10/L4/L6 authority (radius 4/10/16/22, shadow, blur 18px,
// transitionDuration fast120/base180/modal220/drawer280/emphasis420).
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--color-bg)',
        sidebar: 'var(--color-sidebar)',
        panel: 'var(--color-panel)',
        panel2: 'var(--color-panel2)',
        border: 'var(--color-border)',
        ink: 'var(--color-ink)',
        muted: 'var(--color-muted)',
        primary: 'rgb(var(--primary-rgb) / <alpha-value>)',
        secondary: 'rgb(var(--secondary-rgb) / <alpha-value>)',
        'secondary-ink': 'rgb(var(--secondary-ink-rgb) / <alpha-value>)',
        success: 'rgb(var(--success-rgb) / <alpha-value>)',
        warning: 'rgb(var(--warning-rgb) / <alpha-value>)',
        error: 'rgb(var(--error-rgb) / <alpha-value>)',
        info: 'rgb(var(--info-rgb) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'Microsoft YaHei', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      boxShadow: {
        glow: 'var(--shadow)',
        card: '0 4px 24px rgba(0, 0, 0, 0.25)',
      },
      transitionDuration: {
        fast: '120ms',
        base: '180ms',
        modal: '220ms',
        drawer: '280ms',
        emphasis: '420ms',
      },
    },
  },
  plugins: [],
};
