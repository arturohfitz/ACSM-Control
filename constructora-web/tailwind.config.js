/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        acsm: {
          ink: '#162130',
          green: '#1d5f9f',
          'green-hover': '#164a7d',
          teal: '#4f8fc8',
          line: '#b7c9da',
          canvas: '#081321',
          active: '#dceaf7',
          paper: '#e8f1f8',
          field: '#ffffff',
          muted: '#4f6278',
          amber: '#7c8da1',
          gold: '#d8e7f7',
          sidebar: '#081321',
          'sidebar-line': '#1c314d',
          'sidebar-muted': '#c5d4e6',
        },
      },
      boxShadow: {
        panel: '0 28px 70px rgba(4, 20, 44, 0.24), 0 1px 0 rgba(255,255,255,0.8) inset',
      },
    },
  },
  plugins: [],
}
