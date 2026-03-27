/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#00d2ff',
        positive: '#00b09b',
        negative: '#ff6b6b',
        neutral: '#667eea',
        hot: {
          start: '#ffc107',
          end: '#ff9800'
        }
      },
      backgroundImage: {
        'gradient-dark': 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
      }
    },
  },
  plugins: [],
}
