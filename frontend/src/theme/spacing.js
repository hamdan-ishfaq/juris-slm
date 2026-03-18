// spacing.js - Consistent spacing scale
// Base unit: 0.25rem (4px) - All spacing must use this scale

export const spacing = {
  0: '0',
  0.5: '0.125rem',  // 2px
  1: '0.25rem',     // 4px
  1.5: '0.375rem',  // 6px
  2: '0.5rem',      // 8px
  2.5: '0.625rem',  // 10px
  3: '0.75rem',     // 12px
  3.5: '0.875rem',  // 14px
  4: '1rem',        // 16px
  5: '1.25rem',     // 20px
  6: '1.5rem',      // 24px
  7: '1.75rem',     // 28px
  8: '2rem',        // 32px
  9: '2.25rem',     // 36px
  10: '2.5rem',     // 40px
  12: '3rem',       // 48px
  14: '3.5rem',     // 56px
  16: '4rem',       // 64px
  20: '5rem',       // 80px
  24: '6rem',       // 96px
  32: '8rem',       // 128px
  40: '10rem',      // 160px
  48: '12rem',      // 192px
  56: '14rem',      // 224px
  64: '16rem',      // 256px
};

// Border radius - Consistent across all components
export const borderRadius = {
  none: '0',
  sm: '0.25rem',   // 4px - Small elements (badges, tags)
  DEFAULT: '0.5rem', // 8px - Default (buttons, inputs)
  md: '0.5rem',    // 8px - Alias for default
  lg: '0.75rem',   // 12px - Cards, panels
  xl: '1rem',      // 16px - Large containers
  '2xl': '1.5rem', // 24px - Hero sections
  full: '9999px',  // Circular (avatars, pills)
};

// Shadows - Subtle, diffused (NO harsh shadows)
export const boxShadow = {
  // Elevation levels
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  DEFAULT: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  
  // Special
  inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
  none: 'none',
  
  // Focus ring (for accessibility)
  focus: '0 0 0 3px rgba(98, 125, 152, 0.3)',  // primary-500 with alpha
};

// Transitions - Professional easing curves
export const transitionTimingFunction = {
  DEFAULT: 'cubic-bezier(0.4, 0, 0.2, 1)',  // ease-in-out
  linear: 'linear',
  in: 'cubic-bezier(0.4, 0, 1, 1)',         // ease-in
  out: 'cubic-bezier(0, 0, 0.2, 1)',        // ease-out
  'in-out': 'cubic-bezier(0.4, 0, 0.2, 1)', // ease-in-out
};

export const transitionDuration = {
  75: '75ms',
  100: '100ms',
  150: '150ms',
  200: '200ms',
  300: '300ms',
  500: '500ms',
  700: '700ms',
  1000: '1000ms',
};

// Z-index layers - Predictable stacking
export const zIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1100,
  fixed: 1200,
  modalBackdrop: 1300,
  modal: 1400,
  popover: 1500,
  tooltip: 1600,
};
