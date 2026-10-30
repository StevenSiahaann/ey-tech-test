/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ey: {
          yellow: '#ffe600',
          dark: '#2e2e38',
          light: '#f4f4f4',
          border: '#d1d1d1',
          hoverDark: '#444452',
          lightYellow: '#fffdf0',
        }
      }
    },
  },
  plugins: [],
}
