/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'win-blue': '#0078d4',
        'win-gray': '#f3f3f3',
        'win-dark': '#1e1e1e',
      },
      fontFamily: {
        'segoe': ['Segoe UI', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'win': '8px',
      },
      boxShadow: {
        'win': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      },
    },
  },
  plugins: [],
}