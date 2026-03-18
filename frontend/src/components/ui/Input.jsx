import { forwardRef } from 'react';
import { AlertCircle } from 'lucide-react';

/**
 * Input Component - Standardized text input with error states
 * 
 * Features:
 * - Consistent border and focus ring
 * - Error state with icon
 * - Label support
 * - Helper text
 */

const Input = forwardRef(({
  label,
  error,
  helperText,
  className = '',
  id,
  ...props
}, ref) => {
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;
  
  // Base input styles
  const baseStyles = 'w-full px-4 py-2 text-base text-neutral-900 bg-white border rounded-md transition-all duration-200 ease-in-out placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-offset-0 disabled:bg-neutral-100 disabled:cursor-not-allowed';
  
  // State-dependent styles
  const stateStyles = error
    ? 'border-error-DEFAULT focus:border-error-DEFAULT focus:ring-error-light'
    : 'border-neutral-300 focus:border-primary-500 focus:ring-primary-500/30';
  
  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-sm font-medium text-neutral-700 mb-1.5"
        >
          {label}
        </label>
      )}
      
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          className={`${baseStyles} ${stateStyles} ${error ? 'pr-10' : ''} ${className}`}
          {...props}
        />
        
        {error && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
            <AlertCircle className="h-5 w-5 text-error-DEFAULT" />
          </div>
        )}
      </div>
      
      {(error || helperText) && (
        <p className={`mt-1.5 text-sm ${error ? 'text-error-DEFAULT' : 'text-neutral-500'}`}>
          {error || helperText}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;
