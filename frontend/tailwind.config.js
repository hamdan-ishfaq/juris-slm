/** @type {import('tailwindcss').Config} */
import { colors, typography, spacing, borderRadius, boxShadow, transitionTimingFunction, transitionDuration, zIndex } from './src/theme/index.js';

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ...colors,
        // Aliases for easier usage
        'text-primary': colors.text.primary,
        'text-secondary': colors.text.secondary,
        'text-tertiary': colors.text.tertiary,
      },
      fontFamily: typography.fontFamily,
      fontSize: typography.fontSize,
      fontWeight: typography.fontWeight,
      lineHeight: typography.lineHeight,
      letterSpacing: typography.letterSpacing,
      spacing: spacing,
      borderRadius: borderRadius,
      boxShadow: boxShadow,
      transitionTimingFunction: transitionTimingFunction,
      transitionDuration: transitionDuration,
      zIndex: zIndex,
    },
  },
  plugins: [],
}
