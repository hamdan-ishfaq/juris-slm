// colors.js - Professional color palette for enterprise-grade UI
// NO purple gradients, NO glowing effects, NO generic "startup" colors

export const colors = {
  // Primary palette - Navy & Slate (Professional, trustworthy)
  primary: {
    50: '#f0f4f8',
    100: '#d9e2ec',
    200: '#bcccdc',
    300: '#9fb3c8',
    400: '#829ab1',
    500: '#627d98',  // Main primary
    600: '#486581',
    700: '#334e68',
    800: '#243b53',
    900: '#102a43',
  },
  
  // Neutral - Slate & Gray (Clean, professional)
  neutral: {
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a',
    950: '#020617',
  },
  
  // Semantic colors
  success: {
    light: '#10b981',
    DEFAULT: '#059669',
    dark: '#047857',
  },
  
  warning: {
    light: '#f59e0b',
    DEFAULT: '#d97706',
    dark: '#b45309',
  },
  
  error: {
    light: '#ef4444',
    DEFAULT: '#dc2626',
    dark: '#b91c1c',
  },
  
  info: {
    light: '#3b82f6',
    DEFAULT: '#2563eb',
    dark: '#1d4ed8',
  },
  
  // Surface colors (for cards, panels)
  surface: {
    base: '#ffffff',
    elevated: '#f8fafc',
    overlay: 'rgba(15, 23, 42, 0.75)',
  },
  
  // Text colors
  text: {
    primary: '#0f172a',
    secondary: '#475569',
    tertiary: '#94a3b8',
    inverse: '#ffffff',
    disabled: '#cbd5e1',
  },
  
  // Border colors
  border: {
    light: '#e2e8f0',
    DEFAULT: '#cbd5e1',
    dark: '#94a3b8',
    focus: '#627d98',  // Primary 500
  },
};
