/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        tier: {
          A: '#16a34a',
          B: '#2563eb',
          C: '#d97706',
          D: '#9ca3af',
        },
      },
    },
  },
  plugins: [],
}
