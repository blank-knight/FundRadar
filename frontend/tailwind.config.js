/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: '#000000', card: '#0d0d0d', hover: '#161616', border: '#333333' },
        accent: { DEFAULT: '#00d4aa', dim: '#00d4aa22' },
        muted: '#a6a6a6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'serif'],
      },
    },
  },
  plugins: [],
}
