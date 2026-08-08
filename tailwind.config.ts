import type { Config } from 'tailwindcss'

export default {
  content: ['./src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f5f7fa',
          100: '#eef2f6',
          200: '#dfe5ec',
          300: '#ccd5e0',
          400: '#aebac9',
          500: '#8793a2',
          600: '#748093',
          700: '#526176',
          800: '#354052',
          900: '#1a2535',
          950: '#17202a',
        },
        primary: {
          50: '#eef3ff',
          100: '#dce5f5',
          200: '#b9c9e9',
          300: '#8ca8e4',
          400: '#7690c7',
          500: '#3767d6',
          600: '#315cae',
          700: '#345287',
        },
        danger: {
          DEFAULT: '#c95454',
          light: '#fff3f3',
          border: '#e0baba',
          dark: '#b33f3f',
        },
        success: {
          DEFAULT: '#1f8a78',
          light: '#add2c9',
        },
        warning: {
          DEFAULT: '#d18b26',
          light: '#ead8b8',
          bg: '#fff9ed',
        },
      },
      fontFamily: {
        sans: ['Lato', '"Microsoft YaHei"', '"PingFang SC"', 'sans-serif'],
        mono: ['Consolas', '"Microsoft YaHei Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
