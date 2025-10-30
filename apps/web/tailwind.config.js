/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f5f5f5',
          dark: '#0f172a'
        },
        neutral: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827'
        },
        accent: {
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca'
        },
        success: {
          500: '#22c55e'
        },
        danger: {
          500: '#ef4444'
        }
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif']
      },
      borderRadius: {
        xl: '1rem'
      }
    }
  },
  plugins: []
};
