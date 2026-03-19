import { forwardRef } from 'react';
import { AlertCircle } from 'lucide-react';

const Input = forwardRef(({
  label,
  error,
  helperText,
  className = '',
  id,
  ...props
}, ref) => {
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;

  const base = [
    'w-full px-3 py-2 text-sm text-ink bg-base border rounded-sm',
    'font-sans transition-all duration-150',
    'placeholder:text-ink-faint',
    'focus:outline-none focus:ring-1',
    'disabled:bg-elevated disabled:cursor-not-allowed disabled:opacity-50',
  ].join(' ');

  const state = error
    ? 'border-danger focus:border-danger focus:ring-danger/30'
    : 'border-stroke focus:border-stroke-focus focus:ring-gold/20';

  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-mono text-ink-muted uppercase tracking-widest mb-1.5"
        >
          {label}
        </label>
      )}

      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          className={`${base} ${state} ${error ? 'pr-9' : ''} ${className}`}
          {...props}
        />
        {error && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
            <AlertCircle className="h-4 w-4 text-danger" />
          </div>
        )}
      </div>

      {(error || helperText) && (
        <p className={`mt-1.5 text-xs font-mono ${error ? 'text-danger' : 'text-ink-muted'}`}>
          {error || helperText}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';
export default Input;
