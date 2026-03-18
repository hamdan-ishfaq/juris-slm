// typography.js - Strict type scale and hierarchy
// Enforces consistent sizing, weight, and line-height

export const typography = {
  // Font families
  fontFamily: {
    sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
    mono: ['JetBrains Mono', 'Monaco', 'Consolas', 'monospace'],
  },
  
  // Font sizes - Strict scale (no magic numbers)
  fontSize: {
    xs: ['0.75rem', { lineHeight: '1rem' }],      // 12px
    sm: ['0.875rem', { lineHeight: '1.25rem' }],  // 14px
    base: ['1rem', { lineHeight: '1.5rem' }],     // 16px (body text)
    lg: ['1.125rem', { lineHeight: '1.75rem' }],  // 18px
    xl: ['1.25rem', { lineHeight: '1.75rem' }],   // 20px
    '2xl': ['1.5rem', { lineHeight: '2rem' }],    // 24px (h3)
    '3xl': ['1.875rem', { lineHeight: '2.25rem' }], // 30px (h2)
    '4xl': ['2.25rem', { lineHeight: '2.5rem' }],   // 36px (h1)
    '5xl': ['3rem', { lineHeight: '1' }],           // 48px (hero)
  },
  
  // Font weights - Consistent hierarchy
  fontWeight: {
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },
  
  // Line heights
  lineHeight: {
    none: '1',
    tight: '1.2',   // Headings
    snug: '1.375',
    normal: '1.5',  // Body text
    relaxed: '1.625',
    loose: '2',
  },
  
  // Letter spacing
  letterSpacing: {
    tighter: '-0.05em',
    tight: '-0.025em',
    normal: '0',
    wide: '0.025em',
    wider: '0.05em',
  },
};

// Pre-composed text styles for common use cases
export const textStyles = {
  // Headings
  h1: 'text-4xl font-bold leading-tight text-text-primary',
  h2: 'text-3xl font-bold leading-tight text-text-primary',
  h3: 'text-2xl font-semibold leading-tight text-text-primary',
  h4: 'text-xl font-semibold leading-snug text-text-primary',
  h5: 'text-lg font-semibold leading-snug text-text-primary',
  h6: 'text-base font-semibold leading-snug text-text-primary',
  
  // Body text
  bodyLarge: 'text-lg font-normal leading-relaxed text-text-primary',
  body: 'text-base font-normal leading-normal text-text-primary',
  bodySmall: 'text-sm font-normal leading-normal text-text-secondary',
  
  // UI text
  label: 'text-sm font-medium leading-none text-text-primary',
  caption: 'text-xs font-normal leading-tight text-text-tertiary',
  overline: 'text-xs font-medium leading-tight uppercase tracking-wider text-text-secondary',
  
  // Special
  mono: 'font-mono text-sm leading-relaxed',
  code: 'font-mono text-sm bg-neutral-100 px-1.5 py-0.5 rounded',
};
