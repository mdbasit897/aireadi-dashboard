/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
        display: ['"Syne"', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#eef6ff',
          100: '#d9ebff',
          200: '#bcdbff',
          300: '#8dc3ff',
          400: '#57a0ff',
          500: '#2f7bff',
          600: '#1a5cf5',
          700: '#1347e1',
          800: '#163ab6',
          900: '#18368f',
        },
        slate: {
          950: '#0b0f1a',
        },
      },
    },
  },
  plugins: [],
}
