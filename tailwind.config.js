import { colors } from './src/theme/colors.js';
import { spacing, borderRadius, boxShadow, transitionTimingFunction, transitionDuration, zIndex } from './src/theme/index.js';

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: { ...colors },
      fontFamily: {
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
        sans: ['"DM Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      spacing,
      borderRadius,
      boxShadow,
      transitionTimingFunction,
      transitionDuration,
      zIndex,
    },
  },
  plugins: [],
}
