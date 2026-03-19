import { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

const Button = forwardRef(({
  children,
  variant  = 'primary',
  size     = 'md',
  loading  = false,
  disabled = false,
  className = '',
  type = 'button',
  ...props
}, ref) => {
  const base = [
    'inline-flex items-center justify-center font-medium font-sans',
    'transition-all duration-150 rounded-sm',
    'focus:outline-none focus:ring-1 focus:ring-gold focus:ring-offset-1 focus:ring-offset-base',
    'disabled:opacity-40 disabled:cursor-not-allowed',
  ].join(' ');

  const variants = {
    primary:   'bg-gold text-ink-inverse hover:bg-gold/90 active:bg-gold/80',
    secondary: 'bg-elevated text-ink border border-stroke hover:border-stroke-strong',
    danger:    'bg-danger-dim text-danger border border-danger/30 hover:bg-danger/20',
    ghost:     'bg-transparent text-ink-muted hover:text-ink hover:bg-elevated',
  };

  const sizes = {
    sm: 'text-xs px-3 py-1.5 tracking-wide',
    md: 'text-sm px-4 py-2',
    lg: 'text-xs px-5 py-2.5 tracking-widest uppercase',
  };

  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {loading && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
      {children}
    </button>
  );
});

Button.displayName = 'Button';
export default Button;
